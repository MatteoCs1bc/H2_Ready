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

        # --- 3. LETTURA COSTI FUEL (C20:C26) ---
        df_fuel_raw = pd.read_excel(uploaded_file, sheet_name=nome_foglio, usecols="B:C", skiprows=19, nrows=7, header=None)
        
        st.sidebar.divider()
        st.sidebar.header("⚡ Costi Carburante [€/kWh]")
        
        costi_input = {}
        for i, row in df_fuel_raw.iterrows():
            label = str(row[0])
            valore_excel = float(row[1]) if pd.notnull(row[1]) else 0.0
            costi_input[label] = st.sidebar.number_input(label, value=valore_excel, format="%.3f")

        # --- 4. LETTURA TABELLA OUTPUT (Benzina in B5) ---
        # Leggiamo tutto senza header per mappare noi le colonne
        df_full = pd.read_excel(uploaded_file, sheet_name=nome_foglio, header=None)
        
        # In base alla tua struttura:
        # Colonna B (indice 1) -> Tecnologia
        # Colonna E (indice 4) -> Consumo [kWh/km]
        # Colonna N (indice 13) -> Emissioni WtT [kgCO2/anno]
        # Colonna O (indice 14) -> Emissioni TtW [kgCO2/anno]
        # Colonna X (indice 23) -> OPEx Maintenance [€/anno]
        # Colonna Y (indice 24) -> CAPEx [€/anno] (Quota ammortamento)
        # Colonna Z (indice 25) -> CAPEx [€] (Prezzo acquisto totale)
        
        df_clean = df_full.iloc[4:12, [1, 4, 13, 14, 23, 24, 25]].copy()
        df_clean.columns = ["Tecnologia", "Consumo_kWh_km", "WtT", "TtW", "Maint_Anno", "CAPEX_Anno", "Prezzo_Acquisto"]

        # Pulizia numeri: via simboli valuta e conversioni
        def clean_val(x):
            if pd.isna(x): return 0.0
            x = str(x).replace('€', '').replace('%', '').replace(' ', '').replace('.', '').replace(',', '.')
            try: return float(x)
            except: return 0.0

        for col in ["Consumo_kWh_km", "WtT", "TtW", "Maint_Anno", "CAPEX_Anno", "Prezzo_Acquisto"]:
            df_clean[col] = df_clean[col].apply(clean_val)

        # Filtro tecnologie
        tecnologie_target = ["Benzina", "Diesel", "Elettrico rete", "Elettrico autoprodotto", 
                             "Idrogeno Grigio", "Idrogeno rete", "Idrogeno autoprodotto"]
        df_display = df_clean[df_clean["Tecnologia"].isin(tecnologie_target)].copy()

        # --- 5. PARAMETRI E CALCOLI ---
        st.sidebar.divider()
        km_annui = st.sidebar.slider("Percorrenza Annua (km/anno)", 5000, 100000, 15000)
        KM_RIF = 15000 # Riferimento per scalare manutenzione e CO2

        def calcola_simulazione(row):
            tec = row["Tecnologia"]
            prezzo_fuel = costi_input.get(tec, 0.20)
            
            fuel_annuo = row["Consumo_kWh_km"] * km_annui * prezzo_fuel
            manut_annua = (row["Maint_Anno"] / KM_RIF) * km_annui
            capex_annuo = row["CAPEX_Anno"] # Resta l'ammortamento calcolato in Excel
            co2_tot = ((row["WtT"] + row["TtW"]) / KM_RIF) * km_annui
            
            return pd.Series([fuel_annuo, manut_annua, capex_annuo, co2_tot])

        df_display[['Fuel_S', 'Manut_S', 'CAPEX_S', 'CO2_S']] = df_display.apply(calcola_simulazione, axis=1)
        df_display["TCO_Annuo"] = df_display['Fuel_S'] + df_display['Manut_S'] + df_display['CAPEX_S']

        # --- 6. GRAFICI ---
        c1, c2 = st.columns(2)
        
        with c1:
            st.subheader("💰 TCO Annuo")
            df_p = df_display.melt(id_vars="Tecnologia", value_vars=['Fuel_S', 'Manut_S', 'CAPEX_S'], 
                                   var_name="Voce", value_name="Euro")
            fig = px.bar(df_p, x="Tecnologia", y="Euro", color="Voce", barmode='stack',
                         color_discrete_map={'Fuel_S': '#FF4B4B', 'Manut_S': '#FFA421', 'CAPEX_S': '#0068C9'})
            st.plotly_chart(fig, use_container_width=True)

        with c2:
            st.subheader("🌱 Emissioni CO2 WtW")
            fig_co2 = px.bar(df_display, x="Tecnologia", y="CO2_S", color="Tecnologia",
                             title="kg CO2 / anno")
            st.plotly_chart(fig_co2, use_container_width=True)

        st.subheader("📋 Tabella Riepilogativa")
        st.dataframe(df_display[["Tecnologia", "TCO_Annuo", "Fuel_S", "CO2_S"]].style.format(precision=2))

    except Exception as e:
        st.error(f"Errore tecnico: {e}")
        st.info("Controlla che le colonne dell'Excel corrispondano alla mappatura fornita.")

else:
    st.info("👋 Carica il file Excel per iniziare l'analisi.")
