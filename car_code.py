import streamlit as st
import pandas as pd
import plotly.express as px
import os

# --- CONFIGURAZIONE PAGINA ---
st.set_page_config(page_title="DSS Mobilità Comuni", page_icon="🚗", layout="wide")
st.title("🚗 DSS Comuni: Analisi Automatica Flotta")

# --- 1. CARICAMENTO AUTOMATICO DA REPOSITORY ---
# Inserisci qui il nome esatto del tuo file su GitHub
NOME_FILE_EXCEL = "Comparison H2 elc FF.xlsx" 

@st.cache_data
def load_data_from_git(filename):
    if os.path.exists(filename):
        return pd.ExcelFile(filename)
    return None

xl = load_data_from_git(NOME_FILE_EXCEL)

if xl is None:
    st.error(f"❌ Non ho trovato il file '{NOME_FILE_EXCEL}' nel repository.")
    st.info("Assicurati di aver caricato il file su GitHub nella stessa cartella di questo script Python.")
    st.stop()

try:
    # --- 2. SELEZIONE CATEGORIA ---
    fogli_disponibili = xl.sheet_names
    categoria_utente = st.sidebar.selectbox("Seleziona Flotta", ["AUTO", "CAMION", "AUTOBUS URBANO", "AUTOBUS EXTRAURBANO"])
    
    # Cerchiamo il foglio ignorando maiuscole/minuscole
    nome_foglio = next((f for f in fogli_disponibili if f.upper() == categoria_utente), fogli_disponibili[0])
    
    # Leggiamo tutto il foglio senza header per mappare le celle
    df_raw = pd.read_excel(xl, sheet_name=nome_foglio, header=None)

    # --- 3. RICERCA ANCORA "BENZINA" (Tra riga 1 e 15) ---
    anchor_row = None
    for i in range(min(15, len(df_raw))):
        # Cerchiamo nella colonna B (indice 1)
        val = str(df_raw.iloc[i, 1]).strip()
        if val.lower() == "benzina":
            anchor_row = i
            break

    if anchor_row is None:
        st.warning(f"⚠️ Non trovo 'Benzina' nella colonna B del foglio {nome_foglio}.")
        st.write("Ecco cosa vedo nelle prime righe:")
        st.dataframe(df_raw.iloc[:10, :5]) # Mostra anteprima per debug
        st.stop()

    # --- 4. ESTRAZIONE DATI ---
    # Tecnologia (B=1), Consumo (E=4), WtT (N=13), TtW (O=14), CAPEX_A (X=23), Maint_A (Y=24)
    # Regola questi indici se la tabella slitta!
    df_clean = df_raw.iloc[anchor_row:anchor_row+7, [1, 4, 13, 14, 23, 24]].copy()
    df_clean.columns = ["Tecnologia", "Consumo_kWh_km", "WtT", "TtW", "CAPEX_Anno", "Maint_Anno"]

    def to_num(x):
        if pd.isna(x): return 0.0
        s = str(x).replace('€', '').replace(' ', '').replace(',', '.')
        try: return float(s)
        except: return 0.0

    for c in df_clean.columns[1:]:
        df_clean[c] = df_clean[c].apply(to_num)

    # --- 5. COSTI FUEL (C20:C26) ---
    df_fuel = pd.read_excel(xl, sheet_name=nome_foglio, usecols="B:C", skiprows=19, nrows=7, header=None)
    
    st.sidebar.header("⚡ Costi Carburante [€/kWh]")
    costi_input = {}
    for _, row in df_fuel.iterrows():
        label = str(row[0])
        costi_input[label] = st.sidebar.number_input(label, value=to_num(row[1]), format="%.3f")

    # --- 6. SIMULAZIONE ---
    km_annui = st.sidebar.slider("Percorrenza Annua (km)", 5000, 100000, 15000)
    
    def simulate(row):
        t = str(row["Tecnologia"])
        p_fuel = next((v for k, v in costi_input.items() if k.lower() in t.lower()), 0.20)
        
        fuel = row["Consumo_kWh_km"] * km_annui * p_fuel
        maint = (row["Maint_Anno"] / 15000) * km_annui
        capex = row["CAPEX_Anno"]
        co2 = ((row["WtT"] + row["TtW"]) / 15000) * km_annui
        return pd.Series([fuel, maint, capex, co2])

    df_clean[['Fuel_S', 'Manut_S', 'CAPEX_S', 'CO2_S']] = df_clean.apply(simulate, axis=1)
    df_clean["TCO"] = df_clean[['Fuel_S', 'Manut_S', 'CAPEX_S']].sum(axis=1)

    # --- 7. GRAFICI ---
    c1, c2 = st.columns(2)
    with c1:
        st.subheader("💰 TCO Annuo")
        fig = px.bar(df_clean, x="Tecnologia", y=["CAPEX_S", "Manut_S", "Fuel_S"], 
                     labels={"value": "€/anno", "variable": "Costo"}, barmode='stack',
                     color_discrete_map={"CAPEX_S": "#0068C9", "Manut_S": "#FFA421", "Fuel_S": "#FF4B4B"})
        st.plotly_chart(fig, use_container_width=True)
    with c2:
        st.subheader("🌱 Emissioni CO2")
        st.plotly_chart(px.bar(df_clean, x="Tecnologia", y="CO2_S", color="Tecnologia"), use_container_width=True)

    st.table(df_clean[["Tecnologia", "TCO", "CO2_S"]].style.format(precision=2))

except Exception as e:
    st.error(f"Errore tecnico: {e}")
