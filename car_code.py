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

        # --- 2. SCELTA DELLA CATEGORIA ---
        categoria_utente = st.sidebar.selectbox(
            "Quale categoria vuoi analizzare?", 
            ["AUTO", "CAMION", "AUTOBUS URBANO", "AUTOBUS EXTRAURBANO"]
        )

        nome_foglio = next((f for f in fogli_disponibili if f.upper() == categoria_utente), None)

        if not nome_foglio:
            st.error(f"Foglio '{categoria_utente}' non trovato. Fogli presenti: {fogli_disponibili}")
            st.stop()

        # --- 3. LETTURA COSTI FUEL (C20:C26) ---
        # Leggiamo i nomi dalla colonna B (indice 1) e i valori dalla C (indice 2)
        df_fuel_raw = pd.read_excel(uploaded_file, sheet_name=nome_foglio, usecols="B:C", skiprows=19, nrows=7, header=None)
        
        st.sidebar.divider()
        st.sidebar.header("⚡ Costi Carburante [€/kWh]")
        
        costi_input = {}
        for i, row in df_fuel_raw.iterrows():
            label = str(row[0]) # Colonna B
            valore_excel = float(row[1]) if pd.notnull(row[1]) else 0.0
            costi_input[label] = st.sidebar.number_input(label, value=valore_excel, format="%.3f")

        # --- 4. LETTURA TABELLA OUTPUT (Benzina in B5) ---
        # Leggiamo il blocco dati. Usiamo header=None per gestire noi le colonne via posizione
        df_output = pd.read_excel(uploaded_file, sheet_name=nome_foglio, skiprows=4, header=None)
        
        # Pulizia: teniamo solo le colonne che ci servono in base alla posizione nell'immagine che hai mandato
        # Col 1 (B): Tecnologia
        # Col 4 (E): Consumo [kWh/km]
        # Col 13 (N): CO2 WtW [kgCO2/anno]
        # Col 17 (R): OPEx Maintenance [€/anno]
        # Col 18 (S): CAPEx [€/anno]
        
        df_clean = df_output[[1, 4, 13, 17, 18]].copy()
        df_clean.columns = ["Tecnologia", "Consumo_kWh_km", "CO2_Annua", "Manutenzione_Annua_Excel", "CAPEX_Annuo_Excel"]

        # Filtriamo le tecnologie
        tecnologie_target = ["Benzina", "Diesel", "Elettrico rete", "Elettrico autoprodotto", 
                             "Idrogeno Grigio", "Idrogeno rete", "Idrogeno autoprodotto"]
        df_display = df_clean[df_clean["Tecnologia"].isin(tecnologie_target)].copy()

        # Convertiamo tutto in numeri
        for c in ["Consumo_kWh_km", "CO2_Annua", "Manutenzione_Annua_Excel", "CAPEX_Annuo_Excel"]:
            df_display[c] = pd.to_numeric(df_display[c].astype(str).str.replace(',', '.'), errors='coerce')

        # --- 5. PARAMETRI DI SIMULAZIONE ---
        st.sidebar.divider()
        km_annui = st.sidebar.slider("Percorrenza Annua (km/anno)", 5000, 100000, 15000)
        
        # --- 6. CALCOLO DINAMICO TCO ---
        # Poiché l'Excel ha già i costi annui basati su 15.000km (immagino), li riproporzioniamo
        KM_RIFERIMENTO = 15000 

        def calcola_voci(row):
            tec = row["Tecnologia"]
            costo_unitario_fuel = costi_input.get(tec, 0.20)
            
            # Calcolo Fuel: Consumo * km * prezzo scelto
            fuel_annuo = row["Consumo_kWh_km"] * km_annui * costo_unitario_fuel
            # Manutenzione: Scalata sui nuovi km
            manut_annua = (row["Manutenzione_Annua_Excel"] / KM_RIFERIMENTO) * km_annui
            # CAPEX: Resta fisso (è l'ammortamento annuo del veicolo)
            capex_annuo = row["CAPEX_Annuo_Excel"]
            
            return pd.Series([fuel_annuo, manut_annua, capex_annuo])

        df_display[['Fuel_Simulato', 'Manut_Simulata', 'CAPEX_Simulato']] = df_display.apply(calcola_voci, axis=1)
        df_display["TCO_Annuo"] = df_display['Fuel_Simulato'] + df_display['Manut_Simulata'] + df_display['CAPEX_Simulato']
        df_display["CO2_Simulata"] = (df_display["CO2_Annua"] / KM_RIFERIMENTO) * km_annui

        # --- 7. GRAFICI ---
        col_sx, col_dx = st.columns(2)
        
        with col_sx:
            st.subheader("💰 Composizione Costo Annuo (TCO)")
            df_plot = df_display.melt(id_vars="Tecnologia", value_vars=['Fuel_Simulato', 'Manut_Simulata', 'CAPEX_Simulato'], 
                                      var_name="Voce di Costo", value_name="Euro")
            fig_tco = px.bar(df_plot, x="Tecnologia", y="Euro", color="Voce di Costo", barmode='stack')
            st.plotly_chart(fig_tco, use_container_width=True)

        with col_dx:
            st.subheader("🌱 Impatto Ambientale (kg CO2/anno)")
            fig_co2 = px.bar(df_display, x="Tecnologia", y="CO2_Simulata", color="Tecnologia")
            st.plotly_chart(fig_co2, use_container_width=True)

        st.subheader("📋 Riepilogo Risultati")
        st.dataframe(df_display[["Tecnologia", "TCO_Annuo", "Fuel_Simulato", "CO2_Simulata"]].style.format(precision=2))

    except Exception as e:
        st.error(f"Errore tecnico: {e}")
        st.info("Verifica che nel foglio la tabella inizi effettivamente con 'Benzina' alla riga 5 e le colonne siano nell'ordine previsto.")

else:
    st.info("👋 Carica il file Excel per visualizzare il DSS.")
