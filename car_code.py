import streamlit as st
import pandas as pd
import plotly.express as px
import os

# --- CONFIGURAZIONE PAGINA ---
st.set_page_config(page_title="DSS Mobilità Comuni", page_icon="🚗", layout="wide")
st.title("🚗 DSS Comuni: Analisi Automatica Flotta")

# --- 1. CARICAMENTO AUTOMATICO ---
# Il file deve essere nella stessa cartella di car_code.py su GitHub
NOME_FILE_EXCEL = "Comparison H2 elc FF.xlsx" 

if not os.path.exists(NOME_FILE_EXCEL):
    st.error(f"❌ File '{NOME_FILE_EXCEL}' non trovato nel repository.")
    st.stop()

try:
    # Carichiamo il file (senza @st.cache_data per evitare l'errore di serializzazione)
    xl = pd.ExcelFile(NOME_FILE_EXCEL, engine='openpyxl')
    fogli_disponibili = xl.sheet_names

    # --- 2. SELEZIONE CATEGORIA ---
    categoria_utente = st.sidebar.selectbox("Seleziona Flotta", ["AUTO", "CAMION", "AUTOBUS URBANO", "AUTOBUS EXTRAURBANO"])
    
    # Cerchiamo il foglio ignorando maiuscole/minuscole
    nome_foglio = next((f for f in fogli_disponibili if f.upper() == categoria_utente), fogli_disponibili[0])
    
    # Leggiamo il foglio "puro" per trovare l'ancora
    df_raw = pd.read_excel(xl, sheet_name=nome_foglio, header=None, engine='openpyxl')

    # --- 3. RICERCA ANCORA "BENZINA" (Colonna B = Indice 1) ---
    anchor_row = None
    # Cerchiamo nelle prime 15 righe per evitare la tabella costi fuel
    for i in range(min(15, len(df_raw))):
        val = str(df_raw.iloc[i, 1]).strip().lower()
        if val == "benzina":
            anchor_row = i
            break

    if anchor_row is None:
        st.warning(f"⚠️ Non trovo 'Benzina' nella colonna B (prime 15 righe) del foglio {nome_foglio}.")
        st.write("Verifica la struttura del foglio nell'anteprima qui sotto:")
        st.dataframe(df_raw.iloc[:15, :10]) 
        st.stop()

    # --- 4. ESTRAZIONE DATI CON OFFSET ---
    # Tecnologia(B=1), Consumo(E=4), WtT(N=13), TtW(O=14), CAPEX_A(X=23), Maint_A(Y=24)
    # Se i dati sono slittati, cambiamo questi numeri:
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
    # Leggiamo i nomi dalla colonna B (1) e i valori dalla C (2)
    df_fuel = pd.read_excel(xl, sheet_name=nome_foglio, usecols="B:C", skiprows=19, nrows=7, header=None, engine='openpyxl')
    
    st.sidebar.header("⚡ Costi Carburante [€/kWh]")
    costi_input = {}
    for _, row in df_fuel.iterrows():
        label = str(row[0])
        val_default = to_num(row[1])
        costi_input[label] = st.sidebar.number_input(label, value=val_default, format="%.3f")

    # --- 6. SIMULAZIONE ---
    st.sidebar.divider()
    km_annui = st.sidebar.slider("Percorrenza Annua (km)", 5000, 100000, 15000)
    KM_RIF = 15000 
    
    def simulate(row):
        t = str(row["Tecnologia"])
        p_fuel = next((v for k, v in costi_input.items() if k.lower() in t.lower()), 0.20)
        
        fuel = row["Consumo_kWh_km"] * km_annui * p_fuel
        maint = (row["Maint_Anno"] / KM_RIF) * km_annui
        capex = row["CAPEX_Anno"]
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
        df_p["Voce"] = df_p["Voce"].replace({'CAPEX_S': 'CAPEX', 'Manut_S': 'Manutenzione', 'Fuel_S': 'Fuel'})
        fig = px.bar(df_p, x="Tecnologia", y="Euro", color="Voce", barmode='stack',
                     color_discrete_map={'Fuel': '#EF553B', 'Manutenzione': '#FECB52', 'CAPEX': '#636EFA'})
        st.plotly_chart(fig, use_container_width=True)
    
    with c2:
        st.subheader("🌱 Emissioni CO2 (kg/anno)")
        st.plotly_chart(px.bar(df_clean, x="Tecnologia", y="CO2_S", color="Tecnologia"), use_container_width=True)

    st.subheader("📋 Tabella Riepilogativa")
    st.dataframe(df_clean[["Tecnologia", "TCO", "Fuel_S", "CO2_S"]].style.format(precision=2))

except Exception as e:
    st.error(f"Errore tecnico: {e}")
