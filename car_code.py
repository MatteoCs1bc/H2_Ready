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
        nome_foglio = next((f for f in xl.sheet_names if f.upper() == categoria_utente), xl.sheet_names[0])
        
        # Leggiamo il foglio "puro"
        df_raw = pd.read_excel(uploaded_file, sheet_name=nome_foglio, header=None)

        # --- 3. RICERCA "BLINDATA" NELLE PRIME 11 RIGHE ---
        # Cerchiamo solo nella colonna B (indice 1) tra le prime 11 righe
        target_row = None
        for i in range(0, 11): 
            valore = str(df_raw.iloc[i, 1]).strip().lower()
            if valore == "benzina":
                target_row = i
                break
        
        if target_row is None:
            st.error("Non ho trovato 'Benzina' nella colonna B entro la riga 11. Controlla il foglio.")
            st.stop()

        # --- 4. ESTRAZIONE DATI (OFFSET DALLA RIGA TROVATA) ---
        # Tecnologia: Colonna B (1)
        # Consumo: Colonna E (4)
        # Emissioni WtT: Colonna N (13)
        # Emissioni TtW: Colonna O (14)
        # OPEx Maint: Colonna X (23)
        # CAPEx Anno: Colonna Y (24)
        
        df_clean = df_raw.iloc[target_row:target_row+7, [1, 4, 13, 14, 23, 24]].copy()
        df_clean.columns = ["Tecnologia", "Consumo_kWh_km", "WtT", "TtW", "Maint_Anno", "CAPEX_Anno"]

        # Pulizia numeri
        def to_num(x):
            if pd.isna(x): return 0.0
            s = str(x).replace('€', '').replace(' ', '').replace(',', '.')
            try: return float(s)
            except: return 0.0

        for c in df_clean.columns[1:]:
            df_clean[c] = df_clean[c].apply(to_num)

        # --- 5. LETTURA COSTI FUEL (B20:C26) ---
        # Leggiamo i costi carburante dall'Excel per usarli come default nella sidebar
        df_fuel = pd.read_excel(uploaded_file, sheet_name=nome_foglio, usecols="B:C", skiprows=19, nrows=7, header=None)
        
        st.sidebar.divider()
        st.sidebar.header("⚡ Modifica Costi Fuel [€/kWh]")
        costi_input = {}
        for _, row in df_fuel.iterrows():
            label = str(row[0])
            val_def = to_num(row[1])
            costi_input[label] = st.sidebar.number_input(label, value=val_def, format="%.3f")

        # --- 6. SIMULAZIONE DINAMICA ---
        st.sidebar.divider()
        km_annui = st.sidebar.slider("Percorrenza Annua (km)", 5000, 100000, 15000)
        KM_RIF = 15000 
        
        def simulate(row):
            t = str(row["Tecnologia"])
            # Associazione costo fuel (cerca corrispondenza tra tecnologia e etichetta sidebar)
            p_fuel = 0.20
            for k, v in costi_input.items():
                if k.lower() in t.lower():
                    p_fuel = v
                    break
            
            # Calcoli scalati sui KM scelti dall'utente
            fuel = row["Consumo_kWh_km"] * km_annui * p_fuel
            maint = (row["Maint_Anno"] / KM_RIF) * km_annui
            capex = row["CAPEX_Anno"] # Resta fisso (ammortamento annuo)
            co2 = ((row["WtT"] + row["TtW"]) / KM_RIF) * km_annui
            
            return pd.Series([fuel, maint, capex, co2])

        df_clean[['Fuel_S', 'Manut_S', 'CAPEX_S', 'CO2_S']] = df_clean.apply(simulate, axis=1)
        df_clean["TCO"] = df_clean['Fuel_S'] + df_clean['Manut_S'] + df_clean['CAPEX_S']

        # --- 7. OUTPUT GRAFICO ---
        c1, c2 = st.columns(2)
        with c1:
            st.subheader("💰 Composizione TCO Annuo")
            df_p = df_clean.melt(id_vars="Tecnologia", value_vars=['CAPEX_S', 'Manut_S', 'Fuel_S'], 
                                   var_name="Voce", value_name="Euro")
            df_p["Voce"] = df_p["Voce"].replace({'CAPEX_S': 'Quota Veicolo (CAPEX)', 'Manut_S': 'Manutenzione', 'Fuel_S': 'Carburante'})
            
            fig = px.bar(df_p, x="Tecnologia", y="Euro", color="Voce", barmode='stack',
                         color_discrete_map={'Carburante': '#EF553B', 'Manutenzione': '#FECB52', 'Quota Veicolo (CAPEX)': '#636EFA'})
            st.plotly_chart(fig, use_container_width=True)
        
        with c2:
            st.subheader("🌱 Emissioni CO2 Well-to-Wheel")
            fig_co2 = px.bar(df_clean, x="Tecnologia", y="CO2_S", color="Tecnologia", labels={'CO2_S': 'kg/anno'})
            st.plotly_chart(fig_co2, use_container_width=True)

        st.subheader("📋 Analisi Numerica")
        st.dataframe(df_clean[["Tecnologia", "TCO", "Fuel_S", "CO2_S"]].style.format(precision=2), use_container_width=True)

    except Exception as e:
        st.error(f"Errore durante l'elaborazione: {e}")
else:
    st.info("👋 Carica il file Excel per visualizzare il DSS.")
