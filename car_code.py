import streamlit as st
import pandas as pd
import plotly.express as px

# --- CONFIGURAZIONE PAGINA ---
st.set_page_config(page_title="DSS Mobilità Comuni", page_icon="🚗", layout="wide")

st.title("🚗 DSS Comuni: Confronto Tecnologie Flotta")
st.markdown("Strumento di supporto decisionale per valutare il TCO (Total Cost of Ownership) e le emissioni delle diverse flotte comunali.")

# --- 1. CARICAMENTO DEL FILE EXCEL ---
st.sidebar.header("📁 Caricamento Dati")
uploaded_file = st.sidebar.file_uploader("Carica il file Excel", type=["xlsx"])

if uploaded_file:
    try:
        # --- 2. SCELTA DELLA CATEGORIA ---
        st.sidebar.header("🚌 Seleziona Flotta")
        categoria_scelta = st.sidebar.selectbox(
            "Quale categoria vuoi analizzare?", 
            ["AUTO", "CAMION", "AUTOBUS URBANO", "AUTOBUS EXTRAURBANO"]
        )

        # Lettura del foglio in base alla scelta
        if categoria_scelta == "AUTO":
            df_modelli = pd.read_excel(uploaded_file, sheet_name="Dati Targa Modelli", usecols="B:F", skiprows=1)
        elif categoria_scelta == "CAMION":
            df_modelli = pd.read_excel(uploaded_file, sheet_name="Dati Targa Modelli", usecols="K:O", skiprows=1)
        elif categoria_scelta == "AUTOBUS URBANO":
            df_modelli = pd.read_excel(uploaded_file, sheet_name="Dati Targa Modelli", usecols="T:X", skiprows=1)
        elif categoria_scelta == "AUTOBUS EXTRAURBANO":
            df_modelli = pd.read_excel(uploaded_file, sheet_name="Dati Targa Modelli", usecols="T:X", skiprows=29)

        # Pulizia righe completamente vuote
        df_modelli = df_modelli.dropna(how='all')

        with st.expander("🛠️ DEBUG: Guarda come Python vede le tue colonne"):
            st.write(f"Intestazioni trovate per la categoria {categoria_scelta}:")
            st.write(df_modelli.columns.tolist())

        # --- 3. MAPPATURA E PULIZIA CORAZZATA ---
        COL_MODELLO = "Unnamed: 1"
        COL_CONSUMO = "Unnamed: 4"
        COL_COSTO_ACQUISTO = "Unnamed: 5"
        
        # Per ora usiamo "Benzina" di default, poi lo renderemo dinamico per le altre colonne
        COL_TECNOLOGIA = "Unnamed: 1" 

        # Ritagliamo solo le colonne che ci servono
        df_auto = df_modelli[[COL_MODELLO, COL_TECNOLOGIA, COL_COSTO_ACQUISTO, COL_CONSUMO]].copy()
        df_auto.columns = ["Modello", "Tecnologia", "Costo_Acquisto", "Consumo"]

        # ---------------------------------------------------------
        # IL FILTRO CORAZZATO: Elimina tutto ciò che non è un numero
        # ---------------------------------------------------------
        # 1. Togliamo eventuali righe senza modello
        df_auto = df_auto.dropna(subset=["Modello"])

        # 2. Sistemiamo i testi (virgole in punti, via il simbolo € e i punti delle migliaia)
        df_auto["Consumo"] = df_auto["Consumo"].astype(str).str.replace(',', '.')
        df_auto["Costo_Acquisto"] = df_auto["Costo_Acquisto"].astype(str).str.replace('€', '').str.replace('.', '', regex=False).str.replace(' ', '')

        # 3. Forziamo la conversione in numeri. Se c'è scritto "Consumo" o "[l/km]", diventerà "NaN" (Not a Number)
        df_auto["Consumo"] = pd.to_numeric(df_auto["Consumo"], errors='coerce')
        df_auto["Costo_Acquisto"] = pd.to_numeric(df_auto["Costo_Acquisto"], errors='coerce')

        # 4. Eliminiamo tutte le righe
