import streamlit as st
import pandas as pd
import plotly.express as px

st.set_page_config(page_title="DSS Mobilità Comuni", page_icon="🚗", layout="wide")
st.title("🚗 DSS Comuni: Confronto Tecnologie")

# --- 1. CARICAMENTO DEL FILE EXCEL ---
st.sidebar.header("📁 Caricamento Dati")
uploaded_file = st.sidebar.file_uploader("Carica il file Excel", type=["xlsx"])

if uploaded_file:
    try:
        # --- 2. SCELTA DELLA CATEGORIA E LETTURA FOGLIO ---
        st.sidebar.header("🚌 Seleziona Flotta")
        categoria_scelta = st.sidebar.selectbox(
            "Quale categoria vuoi analizzare?", 
            ["AUTO", "CAMION", "AUTOBUS URBANO", "AUTOBUS EXTRAURBANO"]
        )

        # Assumiamo che la tabella di sintesi si trovi nel foglio omonimo (es. foglio "AUTO")
        # Invece di usare le lettere, leggiamo tutto il foglio saltando le prime righe di "titolo"
        # Hai detto che "Benzina" è in B5. Quindi saltiamo le prime 3 righe per avere le intestazioni pulite.
        df_raw = pd.read_excel(uploaded_file, sheet_name=categoria_scelta.title(), skiprows=3)
        
        # Eliminiamo colonne e righe completamente vuote per pulire la tabella
        df_raw = df_raw.dropna(how='all', axis=1).dropna(how='all', axis=0)

        with st.expander("🛠️ DEBUG: Guarda come Python vede le colonne di questo foglio"):
            st.write("Cerca qui i nomi esatti delle colonne per il Consumo [kWh/km], Emissioni, CAPEx e OPEx:")
            st.write(df_raw.columns.tolist())

        # --- 3. MAPPATURA COLONNE (Da aggiornare con i nomi dal Debugger!) ---
        # Poiché la tabella è complessa, qui metterai i nomi esatti (anche gli "Unnamed") 
        # che vedi nel debugger per estrarre i dati base.
        COL_TECNOLOGIA = "Unnamed: 1" # La colonna B dove ci sono i nomi (Benzina, Diesel...)
        COL_CONSUMO_KWH = "Consumo"   # Il consumo in kWh/km
        COL_EMISSIONI = "WtW - [kgCO2/anno]" # Emissioni Well-to-Wheel
        COL_CAPEX = "CAPEx" # Costo di acquisto
        COL_OPEX_MANUT = "OPEx Maintenance" # Costo manutenzione al km (es. 0,080)

        # Filtriamo solo le righe che contengono i nomi delle tecnologie che ci interessano
        tecnologie_valide = ["Benzina", "Diesel", "Elettrico rete", "Elettrico autoprodotto", 
                             "Idrogeno Grigio", "Idrogeno rete", "Idrogeno autoprodotto"]
        
        df_sintesi = df_raw[df_raw[COL_TECNOLOGIA].isin(tecnologie_valide)].copy()
        
        # Rinominiamo per comodità
        df_sintesi.columns = ["Tecnologia", "Consumo_kWh_km", "CO2_Base", "CAPEX_Base", "Manutenzione_km"]
        # Forziamo a numeri pulendo eventuali virgole
        for col in ["Consumo_kWh_km", "CO2_Base", "CAPEX_Base", "Manutenzione_km"]:
            df_sintesi[col] = pd.to_numeric(df_sintesi[col].astype(str).str.replace(',', '.'), errors='coerce')


        # --- 4. SIDEBAR: COSTI FUEL ESATTI ---
        st.sidebar.divider()
        st.sidebar.header("⚡ Costi Fuel [€/kWh]")
        
        costo_benzina = st.sidebar.number_input("Benzina", value=0.22, format="%.2f")
        costo_diesel = st.sidebar.number_input("Diesel", value=0.18, format="%.2f")
        costo_elc_rete = st.sidebar.number_input("Elettrico rete", value=0.31, format="%.2f")
        costo_elc_auto = st.sidebar.number_input("Elettrico autoprodotto", value=0.24, format="%.2f")
        costo_h2_grigio = st.sidebar.number_input("Idrogeno grigio", value=0.06, format="%.2f")
        costo_h2_rete = st.sidebar.number_input("Idrogeno rete (elettrolisi)", value=0.60, format="%.2f")
        costo_h2_verde = st.sidebar.number_input("Idrogeno Verde (PV)", value=0.45, format="%.2f")

        st.sidebar.divider()
        st.sidebar.header("⚙️ Parametri Flotta")
        km_annui = st.sidebar.slider("Percorrenza Annua (km/anno)", min_value=5000, max_value=80000, value=15000)
        lifetime = st.sidebar.slider("Anni di utilizzo (Ammortamento)", min_value=1, max_value=20, value=10)

        # --- 5. MOTORE DI CALCOLO ---
        # Dizionario per mappare la tecnologia al costo fuel scelto nella sidebar
        mappa_costi_fuel = {
            "Benzina": costo_benzina,
            "Diesel": costo_diesel,
            "Elettrico rete": costo_elc_rete,
            "Elettrico autoprodotto": costo_elc_auto,
            "Idrogeno Grigio": costo_h2_grigio,
            "Idrogeno rete": costo_h2_rete,
            "Idrogeno autoprodotto": costo_h2_verde
        }

        df_sintesi["Costo_Fuel_kWh"] = df_sintesi["Tecnologia"].map(mappa_costi_fuel)

        # Calcoliamo i costi aggiornati in base ai km scelti dall'utente
        df_sintesi["Costo_Carburante_Annuo"] = df_sintesi["Consumo_kWh_km"] * km_annui * df_sintesi["Costo_Fuel_kWh"]
        df_sintesi["Manutenzione_Annua"] = df_sintesi["Manutenzione_km"] * km_annui
        df_sintesi["CAPEX_Annuo"] = df_sintesi["CAPEX_Base"] / lifetime
        
        # TCO Totale
        df_sintesi["TCO_Annuo"] = df_sintesi["CAPEX_Annuo"] + df_sintesi["Costo_Carburante_Annuo"] + df_sintesi["Manutenzione_Annua"]

        # Proporzioniamo la CO2 (se il dato base è calcolato su un "anno tipo", lo scaliamo sui nuovi km)
        # Supponiamo che il dato base nel tuo Excel fosse calcolato su 15.000 km
        KM_BASE_EXCEL = 15000 
        df_sintesi["CO2_Annua_Calcolata"] = (df_sintesi["CO2_Base"] / KM_BASE_EXCEL) * km_annui

        # --- 6. VISUALIZZAZIONE ---
        st.subheader("📊 Analisi TCO Annuo")
        
        df_melted = pd.melt(df_sintesi, id_vars=['Tecnologia'], 
                            value_vars=['CAPEX_Annuo', 'Costo_Carburante_Annuo', 'Manutenzione_Annua'],
                            var_name='Voce di Costo', value_name='Euro')
        
        fig_tco = px.bar(df_melted, x="Tecnologia", y="Euro", color="Voce di Costo", title="Composizione del Costo", barmode='stack')
        st.plotly_chart(fig_tco, use_container_width=True)

        st.subheader("📑 Dati di Sintesi Dinamici")
        st.dataframe(df_sintesi[["Tecnologia", "TCO_Annuo", "Costo_Carburante_Annuo", "CO2_Annua_Calcolata"]])

    except Exception as e:
        st.error(f"⚠️ Errore di lettura: {e}")

else:
    st.info("👆 Carica il tuo Excel per iniziare.")
