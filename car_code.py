import streamlit as st
import pandas as pd

st.set_page_config(page_title="Debug Excel", layout="wide")

st.title("🔍 Analizzatore Struttura Excel")

uploaded_file = st.sidebar.file_uploader("Carica il file Excel", type=["xlsx"])

if uploaded_file:
    try:
        # 1. Vediamo i nomi dei fogli
        xl = pd.ExcelFile(uploaded_file)
        fogli = xl.sheet_names
        st.write(f"### Fogli trovati: {fogli}")
        
        selected_sheet = st.selectbox("Seleziona il foglio da analizzare", fogli)
        
        # 2. Leggiamo il foglio in modo "puro" (senza saltare righe, senza filtri)
        # Usiamo engine='openpyxl' che è il più stabile per file complessi
        df = pd.read_excel(uploaded_file, sheet_name=selected_sheet, header=None)
        
        st.write("### Anteprima del foglio (Coordinate Reali)")
        st.write("Usa questa tabella per contare le colonne (A=0, B=1, C=2, D=3, E=4...)")
        
        # Mostriamo la tabella con gli indici di riga e colonna visibili
        st.dataframe(df)
        
        # 3. Test di cattura dati (Righe 5-11, Colonne B, E, N, O, X, Y)
        # Tradotto in indici (partendo da 0): Righe 4-10, Colonne 1, 4, 13, 14, 23, 24
        st.divider()
        st.write("### Test estrazione dati (secondo le tue coordinate)")
        try:
            test_data = df.iloc[4:11, [1, 4, 13, 14, 23, 24]]
            test_data.columns = ["Tecnologia (B)", "Consumo (E)", "WtT (N)", "TtW (O)", "Maint (X)", "CAPEX (Y)"]
            st.table(test_data)
        except Exception as e_inner:
            st.error(f"Errore nell'estrazione mirata: {e_inner}")
            st.info("Se vedi questo errore, guarda la tabella sopra: la colonna più a destra che numero ha?")

    except Exception as e:
        st.error(f"Errore critico di lettura: {e}")
else:
    st.info("Carica il file Excel per vedere come viene letto da Python.")
