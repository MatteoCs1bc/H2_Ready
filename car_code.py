import streamlit as st
import pandas as pd
import plotly.express as px
import os

# --- CONFIGURAZIONE PAGINA ---
st.set_page_config(page_title="DSS Mobilità Comuni", page_icon="🚗", layout="wide")
st.title("🚗 DSS Comuni: Analisi Flotta")

NOME_FILE_EXCEL = "Comparison H2 elc FF.xlsx" 

if not os.path.exists(NOME_FILE_EXCEL):
    st.error(f"❌ File '{NOME_FILE_EXCEL}' non trovato nella cartella GitHub.")
    st.stop()

try:
    # Caricamento con engine openpyxl per massima compatibilità
    xl = pd.ExcelFile(NOME_FILE_EXCEL, engine='openpyxl')
    
    categoria_utente = st.sidebar.selectbox("Seleziona Flotta", ["AUTO", "CAMION", "AUTOBUS URBANO", "AUTOBUS EXTRAURBANO"])
    nome_foglio = next((f for f in xl.sheet_names if f.upper() == categoria_utente), xl.sheet_names[0])
    
    # Leggiamo il foglio COMPLETO senza restrizioni di colonne
    df_raw = pd.read_excel(xl, sheet_name=nome_foglio, header=None, engine='openpyxl')

    # --- FUNZIONE PULIZIA DATI ---
    def clean_val(x):
        if pd.isna(x) or str(x).strip() == "": return 0.0
        s = str(x).replace('€', '').replace(' ', '').replace(',', '.')
        try: return float(s)
        except: return 0.0

    # --- 1. TROVA LE TECNOLOGIE (Benzina, Diesel, ecc.) ---
    # Cerchiamo i dati sapendo che "Benzina" è in B5 (riga 4, col 1) o B6 (riga 5, col 1)
    dati_finali = []
    tecnologie_cercate = ["Benzina", "Diesel", "Elettrico rete", "Elettrico autoprodotto", 
                          "Idrogeno Grigio", "Idrogeno rete", "Idrogeno autoprodotto"]

    # Scansioniamo le prime 15 righe per trovare le corrispondenze
    for i in range(min(15, len(df_raw))):
        nome_tec = str(df_raw.iloc[i, 1]).strip() # Colonna B
        if nome_tec in tecnologie_cercate:
            try:
                # Prendiamo i valori basandoci sulle tue colonne (B=1, E=4, N=13, O=14, X=23, Y=24)
                # NOTA: Se Diesel è in B6, gli indici rimangono questi perché sono relativi alla riga i
                dati_finali.append({
                    "Tecnologia": nome_tec,
                    "Consumo_kWh_km": clean_val(df_raw.iloc[i, 4]),
                    "WtT": clean_val(df_raw.iloc[i, 13]),
                    "TtW": clean_val(df_raw.iloc[i, 14]),
                    "Maint_Anno": clean_val(df_raw.iloc[i, 23]),
                    "CAPEX_Anno": clean_val(df_raw.iloc[i, 24])
                })
            except Exception:
                continue

    if not dati_finali:
        st.error("Nessun dato trovato. Verifica che i nomi (Benzina, Diesel...) siano nella colonna B.")
        st.stop()

    df_clean = pd.DataFrame(dati_finali)

    # --- 2. TROVA COSTI FUEL (B20:C26) ---
    st.sidebar.header("⚡ Costi Carburante [€/kWh]")
    costi_input = {}
    
    # Cerchiamo la riga "Benzina" nella parte bassa (dopo la riga 15)
    riga_prezzi_start = 19 # Default riga 20
    for r in range(15, len(df_raw)):
        if str(df_raw.iloc[r, 1]).strip() == "Benzina":
            riga_prezzi_start = r
            break
            
    for r in range(riga_prezzi_start, riga_prezzi_start + 7):
        try:
            label = str(df_raw.iloc[r, 1])
            val_def = clean_val(df_raw.iloc[r, 2])
            costi_input[label] = st.sidebar.number_input(label, value=val_def, format="%.3f")
        except:
            pass

    # --- 3. SIMULAZIONE ---
    km_annui = st.sidebar.slider("Percorrenza Annua (km)", 5000, 100000, 15000)
    KM_RIF = 15000 
    
    def run_sim(row):
        t = row["Tecnologia"]
        p_fuel = next((v for k, v in costi_input.items() if k.lower() in t.lower()), 0.20)
        fuel = row["Consumo_kWh_km"] * km_annui * p_fuel
        maint = (row["Maint_Anno"] / KM_RIF) * km_annui
        capex = row["CAPEX_Anno"]
        co2 = ((row["WtT"] + row["TtW"]) / KM_RIF) * km_annui
        return pd.Series([fuel, maint, capex, co2])

    df_clean[['Fuel_S', 'Manut_S', 'CAPEX_S', 'CO2_S']] = df_clean.apply(run_sim, axis=1)
    df_clean["TCO"] = df_clean['Fuel_S'] + df_clean['Manut_S'] + df_clean['CAPEX_S']

    # --- 4. GRAFICI ---
    c1, c2 = st.columns(2)
    with c1:
        st.subheader("💰 TCO Annuo Personalizzato")
        fig = px.bar(df_clean, x="Tecnologia", y=["CAPEX_S", "Manut_S", "Fuel_S"], 
                     barmode='stack', color_discrete_sequence=["#636EFA", "#FECB52", "#EF553B"])
        st.plotly_chart(fig, use_container_width=True)
    with c2:
        st.subheader("🌱 Emissioni CO2 (WtW)")
        st.plotly_chart(px.bar(df_clean, x="Tecnologia", y="CO2_S", color="Tecnologia"), use_container_width=True)

    st.subheader("📋 Riepilogo Risultati")
    st.dataframe(df_clean[["Tecnologia", "TCO", "Fuel_S", "CO2_S"]].style.format(precision=2))

except Exception as e:
    st.error(f"Errore Tecnico: {e}")
