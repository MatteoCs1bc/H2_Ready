import streamlit as st
import pandas as pd
import plotly.express as px

# --- CONFIGURAZIONE PAGINA ---
st.set_page_config(page_title="DSS Mobilità Comuni", page_icon="🚗", layout="wide")
st.title("🚗 DSS Comuni: Supporto Decisionale")

# --- 1. CARICAMENTO ---
uploaded_file = st.sidebar.file_uploader("Carica il file Excel", type=["xlsx"])

if uploaded_file:
    try:
        xl = pd.ExcelFile(uploaded_file)
        
        # --- 2. SELEZIONE CATEGORIA ---
        categoria_utente = st.sidebar.selectbox("Categoria", ["AUTO", "CAMION", "AUTOBUS URBANO", "AUTOBUS EXTRAURBANO"])
        # Cerchiamo il foglio ignorando maiuscole/minuscole
        nome_foglio = next((f for f in xl.sheet_names if f.upper() == categoria_utente), xl.sheet_names[0])
        
        # Leggiamo il foglio senza header per avere il controllo totale sulle coordinate
        df_raw = pd.read_excel(uploaded_file, sheet_name=nome_foglio, header=None)

        # --- 3. RICERCA DINAMICA DELLA TABELLA (PUNTO DI ANCORAGGIO) ---
        # Cerchiamo la riga che contiene "Benzina" nella colonna B (indice 1)
        # Limitiamo la ricerca alle prime 15 righe per non confonderci con i costi fuel sotto
        anchor_row = None
        for i in range(len(df_raw)):
            if i > 15: break # Sicurezza: non andare oltre la riga 15
            cell_value = str(df_raw.iloc[i, 1]).strip().lower()
            if cell_value == "benzina":
                anchor_row = i
                break
        
        if anchor_row is None:
            st.error("❌ Non ho trovato 'Benzina' nella colonna B entro la riga 15. Controlla il foglio.")
            # Mostriamo cosa vede Python per aiutare il debug
            st.write("Cosa vede Python nelle prime righe (Colonna B):")
            st.write(df_raw.iloc[:15, 1])
            st.stop()

        # --- 4. ESTRAZIONE DATI CON OFFSET (Basati sulla tua struttura) ---
        # Tecnologia: Colonna B (1)
        # Consumo: Colonna E (4)
        # WtT: Colonna N (13)
        # TtW: Colonna O (14)
        # CAPEX Anno: Colonna Y (24) -> Tu hai detto colonna 23 o 24, correggiamo qui se serve
        # Maint Anno: Colonna X (23) 
        
        # Estraiamo 7 righe a partire dall'ancora trovata
        indices_colonne = [1, 4, 13, 14, 23, 24] 
        df_clean = df_raw.iloc[anchor_row:anchor_row+7, indices_colonne].copy()
        df_clean.columns = ["Tecnologia", "Consumo_kWh_km", "WtT", "TtW", "Maint_Anno", "CAPEX_Anno"]

        # Pulizia numeri (gestisce virgole, € e spazi)
        def to_num(x):
            if pd.isna(x): return 0.0
            s = str(x).replace('€', '').replace(' ', '').replace(',', '.')
            try: return float(s)
            except: return 0.0

        for c in ["Consumo_kWh_km", "WtT", "TtW", "Maint_Anno", "CAPEX_Anno"]:
            df_clean[c] = df_clean[c].apply(to_num)

        # --- 5. LETTURA COSTI FUEL (B20:C26) ---
        # Cerchiamo la riga "COSTI FUEL" per sicurezza o usiamo il fisso 19
        df_fuel = pd.read_excel(uploaded_file, sheet_name=nome_foglio, usecols="B:C", skiprows=19, nrows=7, header=None)
        
        st.sidebar.divider()
        st.sidebar.header("⚡ Modifica Costi Fuel [€/kWh]")
        costi_input = {}
        for _, row in df_fuel.iterrows():
            label = str(row[0])
            val_def = to_num(row[1])
            costi_input[label] = st.sidebar.number_input(label, value=val_def, format="%.3f")

        # --- 6. SIMULAZIONE ---
        st.sidebar.divider()
        km_annui = st.sidebar.slider("Percorrenza Annua (km)", 5000, 100000, 15000)
        KM_RIF = 15000 
        
        def simulate(row):
            t = str(row["Tecnologia"])
            # Associazione costo fuel dinamica
            p_fuel = 0.20
            for k, v in costi_input.items():
                if k.lower() in t.lower():
                    p_fuel = v
                    break
            
            fuel = row["Consumo_kWh_km"] * km_annui * p_fuel
            maint = (row["Maint_Anno"] / KM_RIF) * km_annui
            capex = row["CAPEX_Anno"] # Quota fissa
            co2 = ((row["WtT"] + row["TtW"]) / KM_RIF) * km_annui
            return pd.Series([fuel, maint, capex, co2])

        df_clean[['Fuel_S', 'Manut_S', 'CAPEX_S', 'CO2_S']] = df_clean.apply(simulate, axis=1)
        df_clean["TCO"] = df_clean['Fuel_S'] + df_clean['Manut_S'] + df_clean['CAPEX_S']

        # --- 7. GRAFICI ---
        c1, c2 = st.columns(2)
        with c1:
            st.subheader("💰 TCO Annuo Personalizzato")
            df_p = df_clean.melt(id_vars="Tecnologia", value_vars=['CAPEX_S', 'Manut_S', 'Fuel_S'], 
                                 var_name="Voce", value_name="Euro")
            fig = px.bar(df_p, x="Tecnologia", y="Euro", color="Voce", barmode='stack',
                         color_discrete_map={'Fuel_S': '#EF553B', 'Manut_S': '#FECB52', 'CAPEX_S': '#636EFA'})
            st.plotly_chart(fig, use_container_width=True)
        
        with c2:
            st.subheader("🌱 Emissioni CO2 (WtW)")
            st.plotly_chart(px.bar(df_clean, x="Tecnologia", y="CO2_S", color="Tecnologia"), use_container_width=True)

        st.subheader("📋 Riepilogo")
        st.dataframe(df_clean[["Tecnologia", "TCO", "Fuel_S", "CO2_S"]].style.format(precision=2), use_container_width=True)

    except Exception as e:
        st.error(f"⚠️ Errore: {e}")
else:
    st.info("👋 Carica il file Excel per iniziare.")
