import streamlit as st
import pandas as pd
import plotly.express as px

# --- CONFIGURAZIONE PAGINA ---
st.set_page_config(page_title="DSS Mobilità Comuni", page_icon="🚗", layout="wide")
st.title("🚗 DSS Comuni: Supporto Decisionale Tecnologie H2/EV")

# --- 1. CARICAMENTO DEL FILE EXCEL ---
st.sidebar.header("📁 Caricamento Database")
uploaded_file = st.sidebar.file_uploader("Carica il file Excel", type=["xlsx"])

if uploaded_file:
    try:
        xl = pd.ExcelFile(uploaded_file)
        fogli_disponibili = xl.sheet_names

        # --- 2. SELEZIONE CATEGORIA ---
        categoria_utente = st.sidebar.selectbox(
            "Quale categoria vuoi analizzare?", 
            ["AUTO", "CAMION", "AUTOBUS URBANO", "AUTOBUS EXTRAURBANO"]
        )

        nome_foglio = next((f for f in fogli_disponibili if f.upper() == categoria_utente), None)
        if not nome_foglio:
            st.error(f"Foglio '{categoria_utente}' non trovato.")
            st.stop()

        # --- 3. LETTURA COSTI FUEL (B20:C26) ---
        df_fuel_raw = pd.read_excel(uploaded_file, sheet_name=nome_foglio, usecols="B:C", skiprows=19, nrows=7, header=None)
        
        st.sidebar.divider()
        st.sidebar.header("⚡ Costi Carburante [€/kWh]")
        costi_input = {}
        for i, row in df_fuel_raw.iterrows():
            label = str(row[0])
            valore_excel = float(row[1]) if pd.notnull(row[1]) else 0.0
            costi_input[label] = st.sidebar.number_input(label, value=valore_excel, format="%.3f")

        # --- 4. LETTURA TABELLA DATI ---
        df_full = pd.read_excel(uploaded_file, sheet_name=nome_foglio, header=None)

        # MAPPATURA AGGIORNATA (BASATA SUI TUOI FEEDBACK)
        # Riga 5 di Excel = Indice 4 di Pandas
        # Colonna C = Indice 2 (Tecnologia)
        # Colonna F = Indice 5 (Consumo)
        # Colonna O = Indice 14 (WtT)
        # Colonna P = Indice 15 (TtW)
        # Colonna X = Indice 23 (CAPEX Anno)
        # Colonna Y = Indice 24 (OPEX Maint Anno)
        
        df_clean = df_full.iloc[4:11, [2, 5, 14, 15, 23, 24]].copy()
        df_clean.columns = ["Tecnologia", "Consumo_kWh_km", "WtT", "TtW", "CAPEX_Anno", "Maint_Anno"]

        # Funzione di pulizia numeri (gestisce testi, virgole e formati Excel sporchi)
        def clean_numeric(x):
            if pd.isna(x): return 0.0
            s = str(x).replace('€', '').replace('%', '').replace(' ', '')
            if ',' in s and '.' in s: s = s.replace('.', '').replace(',', '.')
            elif ',' in s: s = s.replace(',', '.')
            try: return float(s)
            except: return 0.0

        for col in ["Consumo_kWh_km", "WtT", "TtW", "CAPEX_Anno", "Maint_Anno"]:
            df_clean[col] = df_clean[col].apply(clean_numeric)

        # Filtro Tecnologie
        tecnologie_target = ["Benzina", "Diesel", "Elettrico rete", "Elettrico autoprodotto", 
                             "Idrogeno Grigio", "Idrogeno rete", "Idrogeno autoprodotto"]
        df_display = df_clean[df_clean["Tecnologia"].astype(str).str.contains('|'.join(tecnologie_target), na=False, case=False)].copy()

        # --- 5. PARAMETRI E CALCOLI ---
        st.sidebar.divider()
        km_annui = st.sidebar.slider("Percorrenza Annua (km/anno)", 5000, 100000, 15000)
        KM_RIF = 15000 

        def calcola_simulazione(row):
            tec = str(row["Tecnologia"])
            # Cerca il costo fuel corrispondente
            prezzo_fuel = 0.20
            for k, v in costi_input.items():
                if k.lower() in tec.lower():
                    prezzo_fuel = v
                    break
            
            fuel_annuo = row["Consumo_kWh_km"] * km_annui * prezzo_fuel
            manut_annua = (row["Maint_Anno"] / KM_RIF) * km_annui
            capex_annuo = row["CAPEX_Anno"] # Ammortamento annuo
            co2_tot = ((row["WtT"] + row["TtW"]) / KM_RIF) * km_annui
            
            return pd.Series([fuel_annuo, manut_annua, capex_annuo, co2_tot])

        df_display[['Fuel_S', 'Manut_S', 'CAPEX_S', 'CO2_S']] = df_display.apply(calcola_simulazione, axis=1)
        df_display["TCO_Annuo"] = df_display['Fuel_S'] + df_display['Manut_S'] + df_display['CAPEX_S']

        # --- 6. GRAFICI ---
        col1, col2 = st.columns(2)
        with col1:
            st.subheader("💰 Composizione TCO Annuo (€/anno)")
            df_p = df_display.melt(id_vars="Tecnologia", value_vars=['Fuel_S', 'Manut_S', 'CAPEX_S'], 
                                   var_name="Voce", value_name="Euro")
            df_p["Voce"] = df_p["Voce"].replace({'Fuel_S': 'Carburante', 'Manut_S': 'Manutenzione', 'CAPEX_S': 'Quota Veicolo'})
            fig = px.bar(df_p, x="Tecnologia", y="Euro", color="Voce", barmode='stack',
                         color_discrete_map={'Carburante': '#EF553B', 'Manutenzione': '#FECB52', 'Quota Veicolo': '#636EFA'})
            st.plotly_chart(fig, use_container_width=True)

        with col2:
            st.subheader("🌱 Emissioni CO2 WtW (kg/anno)")
            fig_co2 = px.bar(df_display, x="Tecnologia", y="CO2_S", color="Tecnologia")
            st.plotly_chart(fig_co2, use_container_width=True)

        st.subheader("📋 Tabella Riepilogativa")
        st.dataframe(df_display[["Tecnologia", "TCO_Annuo", "Fuel_S", "CO2_S"]].style.format(precision=2))

    except Exception as e:
        st.error(f"Errore tecnico: {e}")
        st.info("Controlla il file: 'Diesel' deve essere nella riga 5, colonna C.")

else:
    st.info("👋 Carica il file Excel per iniziare l'analisi.")
