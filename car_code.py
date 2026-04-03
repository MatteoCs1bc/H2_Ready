import streamlit as st
import pandas as pd
import plotly.express as px
import os

# --- CONFIGURAZIONE PAGINA ---
st.set_page_config(page_title="DSS Mobilità Comuni", page_icon="🚗", layout="wide")
st.title("🚗 DSS Comuni: Analisi TCO e Ambientale")

NOME_FILE_EXCEL = "Comparison H2 elc FF.xlsx" 

if not os.path.exists(NOME_FILE_EXCEL):
    st.error(f"❌ File '{NOME_FILE_EXCEL}' non trovato su GitHub.")
    st.stop()

try:
    xl = pd.ExcelFile(NOME_FILE_EXCEL, engine='openpyxl')
    
    categoria_utente = st.sidebar.selectbox("🚌 Seleziona Flotta", ["AUTO", "CAMION", "AUTOBUS URBANO", "AUTOBUS EXTRAURBANO"])
    nome_foglio = next((f for f in xl.sheet_names if f.upper() == categoria_utente), xl.sheet_names[0])
    
    # Leggiamo tutto il foglio
    df_raw = pd.read_excel(xl, sheet_name=nome_foglio, header=None, engine='openpyxl')

    def clean_val(x):
        if pd.isna(x) or str(x).strip() == "": return 0.0
        s = str(x).replace('€', '').replace(' ', '').replace(',', '.')
        try: return float(s)
        except: return 0.0

    # --- 1. ESTRAZIONE DATI BASE (Coordinate Esatte) ---
    dati_finali = []
    tecnologie_cercate = ["Benzina", "Diesel", "Elettrico rete", "Elettrico autoprodotto", 
                          "Idrogeno Grigio", "Idrogeno rete", "Idrogeno autoprodotto"]

    for i in range(min(20, len(df_raw))):
        nome_tec = str(df_raw.iloc[i, 1]).strip() # Colonna B
        if nome_tec in tecnologie_cercate:
            try:
                dati_finali.append({
                    "Tecnologia": nome_tec,
                    # Seguendo ESATTAMENTE le tue formule:
                    "Consumo_kWh_km": clean_val(df_raw.iloc[i, 4]),   # E5
                    "WtT_Excel": clean_val(df_raw.iloc[i, 14]),       # O5
                    "TtW_Excel": clean_val(df_raw.iloc[i, 15]),       # P5
                    "Maint_km": clean_val(df_raw.iloc[i, 22]),        # W5 (Euro/km puro)
                    "CAPEX_Totale": clean_val(df_raw.iloc[i, 25])     # Z5 (Euro totale)
                })
            except Exception:
                continue

    if not dati_finali:
        st.error("Nessun dato trovato. Assicurati che il foglio contenga le tecnologie nella colonna B.")
        st.stop()

    df_clean = pd.DataFrame(dati_finali)

    # --- 2. LETTURA COSTI FUEL (B20:C26) ---
    st.sidebar.divider()
    st.sidebar.header("⚡ Costi Carburante [€/kWh]")
    costi_input = {}
    
    riga_prezzi = 19
    for r in range(15, len(df_raw)):
        if str(df_raw.iloc[r, 1]).strip() == "Benzina":
            riga_prezzi = r
            break
            
    for r in range(riga_prezzi, riga_prezzi + 7):
        try:
            label = str(df_raw.iloc[r, 1])
            if label in tecnologie_cercate:
                val_def = clean_val(df_raw.iloc[r, 2])
                costi_input[label] = st.sidebar.number_input(label, value=val_def, format="%.3f")
        except:
            pass

    # --- 3. PARAMETRI UTENTE (Le tue C16 e C17) ---
    st.sidebar.divider()
    st.sidebar.header("⚙️ Parametri Flotta")
    
    # Riproduciamo le variabili dell'Excel
    km_annui = st.sidebar.slider("Percorrenza Annua (km)", 5000, 100000, 15000, step=1000) # Equivalente a C17
    lifetime = st.sidebar.slider("Anni di Utilizzo (Ammortamento)", 1, 20, 10, step=1)      # Equivalente a C16
    
    # Server per riproporzionare la CO2 calcolata in Excel (che immagino sia su base 15.000)
    km_base_excel = 15000 

    # --- 4. IL MOTORE MATEMATICO ---
    def calcola_indicatori(row):
        t = row["Tecnologia"]
        p_fuel = next((v for k, v in costi_input.items() if k.lower() in t.lower()), 0.20)
        
        # 1. Carburante (Formula = E5 * km_annui * p_fuel)
        fuel = row["Consumo_kWh_km"] * km_annui * p_fuel
        
        # 2. OPEx Maintenance (Formula: X5 = W5 * km_annui)
        maint = row["Maint_km"] * km_annui
        
        # 3. CAPEx Annuo (Formula: Y5 = Z5 / lifetime)
        capex = row["CAPEX_Totale"] / lifetime
        
        # 4. Emissioni Scalate
        wtt_scalato = (row["WtT_Excel"] / km_base_excel) * km_annui
        ttw_scalato = (row["TtW_Excel"] / km_base_excel) * km_annui
        co2 = wtt_scalato + ttw_scalato
        
        return pd.Series([fuel, maint, capex, co2])

    df_clean[['Fuel_S', 'Manut_S', 'CAPEX_S', 'CO2_S']] = df_clean.apply(calcola_indicatori, axis=1)
    df_clean["TCO_Annuo"] = df_clean['Fuel_S'] + df_clean['Manut_S'] + df_clean['CAPEX_S']

    # --- 5. VISUALIZZAZIONE RISULTATI ---
    c1, c2 = st.columns(2)
    with c1:
        st.subheader("💰 Composizione Costo Annuo (TCO)")
        df_plot = df_clean.melt(id_vars="Tecnologia", value_vars=['CAPEX_S', 'Manut_S', 'Fuel_S'], 
                                var_name="Voce di Costo", value_name="Euro")
        
        df_plot["Voce di Costo"] = df_plot["Voce di Costo"].replace({
            'CAPEX_S': 'Quota Veicolo (CAPEX)',
            'Manut_S': 'Manutenzione',
            'Fuel_S': 'Energia/Carburante'
        })
        
        fig = px.bar(df_plot, x="Tecnologia", y="Euro", color="Voce di Costo", 
                     barmode='stack', color_discrete_sequence=["#0068C9", "#FFA421", "#FF4B4B"])
        fig.update_layout(yaxis_title="€ / Anno")
        st.plotly_chart(fig, use_container_width=True)
        
    with c2:
        st.subheader("🌱 Emissioni Annuali Well-to-Wheel")
        fig_co2 = px.bar(df_clean, x="Tecnologia", y="CO2_S", color="Tecnologia")
        fig_co2.update_layout(yaxis_title="kg di CO2 / Anno", showlegend=False)
        st.plotly_chart(fig_co2, use_container_width=True)

    st.subheader("📋 Tabella Riepilogativa")
    st.dataframe(df_clean[["Tecnologia", "TCO_Annuo", "CAPEX_S", "Manut_S", "Fuel_S", "CO2_S"]].style.format({
        "TCO_Annuo": "€ {:,.2f}",
        "CAPEX_S": "€ {:,.2f}",
        "Manut_S": "€ {:,.2f}",
        "Fuel_S": "€ {:,.2f}",
        "CO2_S": "{:,.0f} kg"
    }), use_container_width=True)

except Exception as e:
    st.error(f"Errore di Elaborazione: {e}")
