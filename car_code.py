import streamlit as st
import pandas as pd
import plotly.express as px
import os

# --- CONFIGURAZIONE PAGINA ---
st.set_page_config(page_title="DSS Mobilità Comuni", page_icon="🚗", layout="wide")
st.title("🚗 DSS Comuni: Analisi Flotta (Multi-Alimentazione)")

# --- 1. CARICAMENTO AUTOMATICO DA GITHUB ---
NOME_FILE_EXCEL = "Comparison H2 elc FF.xlsx" 

if not os.path.exists(NOME_FILE_EXCEL):
    st.error(f"❌ File '{NOME_FILE_EXCEL}' non trovato nel repository GitHub.")
    st.stop()

try:
    xl = pd.ExcelFile(NOME_FILE_EXCEL, engine='openpyxl')
    categoria_utente = st.sidebar.selectbox("Seleziona Flotta", ["AUTO", "CAMION", "AUTOBUS URBANO", "AUTOBUS EXTRAURBANO"])
    nome_foglio = next((f for f in xl.sheet_names if f.upper() == categoria_utente), xl.sheet_names[0])
    
    # Leggiamo il foglio integrale
    df_raw = pd.read_excel(xl, sheet_name=nome_foglio, header=None, engine='openpyxl')

    # --- 2. TROVA LA TABELLA DATI (ANCORE) ---
    # Cerchiamo la prima occorrenza di "Benzina" nelle prime 15 righe
    riga_inizio_dati = None
    col_inizio_dati = None
    for r in range(min(15, len(df_raw))):
        for c in range(len(df_raw.columns)):
            if str(df_raw.iloc[r, c]).strip().lower() == "benzina":
                riga_inizio_dati = r
                col_inizio_dati = c
                break
        if riga_inizio_dati is not None: break

    if riga_inizio_dati is None:
        st.error("Impossibile trovare la tabella dati (parola chiave 'Benzina' non trovata in alto).")
        st.stop()

    # --- 3. ESTRAZIONE DATI (7 RIGHE DA BENZINA IN GIÙ) ---
    # Basato sulle tue indicazioni: 
    # Tecnologia (Col B/Index 1), Consumo (Col E/Index 4), WtT (N/13), TtW (O/14), Maint (X/23), CAPEX (Y/24)
    # Calcoliamo gli offset rispetto alla colonna dove abbiamo trovato "Benzina"
    off = col_inizio_dati 
    df_clean = df_raw.iloc[riga_inizio_dati:riga_inizio_dati+10, [off, off+3, off+12, off+13, off+22, off+23]].copy()
    df_clean.columns = ["Tecnologia", "Consumo_kWh_km", "WtT", "TtW", "CAPEX_Anno", "Maint_Anno"]
    
    # Pulizia: rimuoviamo righe che non sono tecnologie (come le righe vuote 12 e 13)
    tecnologie_valide = ["benzina", "diesel", "elettrico", "idrogeno"]
    df_clean = df_clean[df_clean["Tecnologia"].astype(str).str.lower().str.contains('|'.join(tecnologie_valide), na=False)]

    def clean_val(x):
        if pd.isna(x): return 0.0
        s = str(x).replace('€', '').replace(' ', '').replace(',', '.')
        try: return float(s)
        except: return 0.0

    for col in df_clean.columns[1:]:
        df_clean[col] = df_clean[col].apply(clean_val)

    # --- 4. TROVA LA TABELLA COSTI FUEL (PARTE BASSA) ---
    # Cerchiamo la riga dove ricomincia "Benzina" o "Costi Fuel" dopo la riga 15
    riga_prezzi = None
    for r in range(15, len(df_raw)):
        if str(df_raw.iloc[r, col_inizio_dati]).strip().lower() in ["benzina", "costi fuel"]:
            riga_prezzi = r
            break
    
    st.sidebar.header("⚡ Costi Carburante [€/kWh]")
    costi_input = {}
    if riga_prezzi is not None:
        # Leggiamo i 7 prezzi
        df_prezzi = df_raw.iloc[riga_prezzi:riga_prezzi+7, [col_inizio_dati, col_inizio_dati+1]]
        for _, row in df_prezzi.iterrows():
            label = str(row[0])
            val_def = clean_val(row[1])
            costi_input[label] = st.sidebar.number_input(label, value=val_def, format="%.3f")
    else:
        st.sidebar.warning("Tabella prezzi non trovata automaticamente. Uso valori standard.")
        costi_input = {"Benzina": 0.22, "Diesel": 0.18, "Elettrico": 0.30, "Idrogeno": 0.50}

    # --- 5. SIMULAZIONE ---
    km_annui = st.sidebar.slider("Percorrenza Annua (km)", 5000, 100000, 15000)
    
    def run_sim(row):
        t = str(row["Tecnologia"])
        p_fuel = next((v for k, v in costi_input.items() if k.lower() in t.lower()), 0.20)
        fuel = row["Consumo_kWh_km"] * km_annui * p_fuel
        maint = (row["Maint_Anno"] / 15000) * km_annui
        capex = row["CAPEX_Anno"]
        co2 = ((row["WtT"] + row["TtW"]) / 15000) * km_annui
        return pd.Series([fuel, maint, capex, co2])

    df_clean[['Fuel_S', 'Manut_S', 'CAPEX_S', 'CO2_S']] = df_clean.apply(run_sim, axis=1)
    df_clean["TCO"] = df_clean[['Fuel_S', 'Manut_S', 'CAPEX_S']].sum(axis=1)

    # --- 6. GRAFICI ---
    c1, c2 = st.columns(2)
    with c1:
        st.subheader("💰 TCO Annuo")
        fig = px.bar(df_clean, x="Tecnologia", y=["CAPEX_S", "Manut_S", "Fuel_S"], 
                     labels={"value": "Euro", "variable": "Voce"}, barmode='stack',
                     color_discrete_map={"CAPEX_S": "#0068C9", "Manut_S": "#FFA421", "Fuel_S": "#FF4B4B"})
        st.plotly_chart(fig, use_container_width=True)
    with c2:
        st.subheader("🌱 CO2 Well-to-Wheel")
        st.plotly_chart(px.bar(df_clean, x="Tecnologia", y="CO2_S", color="Tecnologia"), use_container_width=True)

    st.table(df_clean[["Tecnologia", "TCO", "CO2_S"]].style.format(precision=2))

except Exception as e:
    st.error(f"Errore tecnico: {e}")
