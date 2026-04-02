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

        # 4. Eliminiamo tutte le righe che sono diventate "NaN" (cioè le intestazioni e le unità di misura!)
        df_auto = df_auto.dropna(subset=["Consumo", "Costo_Acquisto"])
        
        # Ri-assegniamo forzatamente l'etichetta Tecnologia a tutti i veicoli estratti da questa prima tabella
        df_auto["Tecnologia"] = "Benzina"
        # ---------------------------------------------------------

        # --- 4. SIDEBAR: INPUT UTENTE (PARAMETRI ECONOMICI) ---
        st.sidebar.divider()
        st.sidebar.header("⚙️ Parametri di Simulazione")
        
        st.sidebar.subheader("Utilizzo e Vita Utile")
        km_annui = st.sidebar.slider("Percorrenza Annua (km/anno)", min_value=5000, max_value=80000, value=15000, step=1000)
        lifetime = st.sidebar.slider("Anni di utilizzo (Ammortamento)", min_value=1, max_value=20, value=10, step=1)

        st.sidebar.subheader("Costi Energia/Carburante")
        costo_ff = st.sidebar.number_input("Costo Fossile (€/litro)", value=1.80, step=0.05)
        costo_elc = st.sidebar.number_input("Costo Elettricità (€/kWh)", value=0.25, step=0.05)
        costo_h2 = st.sidebar.number_input("Costo Idrogeno (€/kg)", value=12.00, step=0.50)

        # --- 5. MOTORE DI CALCOLO DINAMICO ---
        # A. Costo Energia
        def assegna_costo_energia(tecnologia):
            tec = str(tecnologia).lower()
            if "elettric" in tec or "bev" in tec: return costo_elc
            elif "idrogeno" in tec or "h2" in tec or "fcev" in tec: return costo_h2
            else: return costo_ff

        df_auto["Costo_Energia_Unitario"] = df_auto["Tecnologia"].apply(assegna_costo_energia)

        # B. Manutenzione
        costi_manutenzione_km = {
            "Benzina": 0.08,
            "Diesel": 0.065,
            "Elettrica (BEV)": 0.03,
            "Idrogeno (FCEV)": 0.055
        }

        def assegna_manutenzione_km(tecnologia):
            tec = str(tecnologia).lower()
            if "benzina" in tec: return costi_manutenzione_km["Benzina"]
            elif "diesel" in tec: return costi_manutenzione_km["Diesel"]
            elif "elettric" in tec or "bev" in tec: return costi_manutenzione_km["Elettrica (BEV)"]
            elif "idrogeno" in tec or "fcev" in tec: return costi_manutenzione_km["Idrogeno (FCEV)"]
            else: return 0.08 # Default

        df_auto["Tariffa_Manutenzione_km"] = df_auto["Tecnologia"].apply(assegna_manutenzione_km)

        # C. Calcoli TCO
        df_auto["Manutenzione_Annua"] = df_auto["Tariffa_Manutenzione_km"] * km_annui
        df_auto["Costo_Carburante_Annuo"] = df_auto["Consumo"] * km_annui * df_auto["Costo_Energia_Unitario"]
        df_auto["OPEX_Annuo"] = df_auto["Costo_Carburante_Annuo"] + df_auto["Manutenzione_Annua"]
        df_auto["CAPEX_Annuo"] = df_auto["Costo_Acquisto"] / lifetime
        df_auto["TCO_Annuo"] = df_auto["CAPEX_Annuo"] + df_auto["OPEX_Annuo"]

        # D. Calcolo CO2
        def calcola_co2(row):
            tec = str(row["Tecnologia"]).lower()
            if "elettric" in tec or "idrogeno" in tec or "bev" in tec: return 0
            else: return (150 * km_annui) / 1000 

        df_auto["CO2_Annua_kg"] = df_auto.apply(calcola_co2, axis=1)

        # --- 6. VISUALIZZAZIONE RISULTATI ---
        st.subheader(f"📊 Confronto TCO Annuo: {categoria_scelta}")
        
        df_melted = pd.melt(df_auto, id_vars=['Modello'], 
                            value_vars=['CAPEX_Annuo', 'Costo_Carburante_Annuo', 'Manutenzione_Annua'],
                            var_name='Voce di Costo', value_name='Euro')
        
        df_melted['Voce di Costo'] = df_melted['Voce di Costo'].replace({
            'CAPEX_Annuo': 'Quota Veicolo (CAPEX)',
            'Costo_Carburante_Annuo': 'Costo Energia/Carburante',
            'Manutenzione_Annua': 'Manutenzione Annua'
        })

        col1, col2 = st.columns(2)
        with col1:
            fig_tco = px.bar(df_melted, x="Modello", y="Euro", color="Voce di Costo",
                             title="TCO: Acquisto vs Operatività",
                             color_discrete_sequence=px.colors.qualitative.Set2)
            fig_tco.update_layout(barmode='stack', yaxis_title="Costo Annuo (€)")
            st.plotly_chart(fig_tco, use_container_width=True)

        with col2:
            fig_co2 = px.bar(df_auto, x="Modello", y="CO2_Annua_kg", 
                             title="Impatto Ambientale: CO2 allo scarico",
                             text="CO2_Annua_kg",
                             color="Modello",
                             color_discrete_sequence=px.colors.qualitative.Safe)
            fig_co2.update_traces(texttemplate='%{text:,.0f} kg', textposition='outside')
            fig_co2.update_layout(yaxis_title="kg di CO2 / anno", showlegend=False)
            st.plotly_chart(fig_co2, use_container_width=True)

        # Tabella di riepilogo
        st.subheader("📑 Dati di Sintesi")
        st.dataframe(df_auto[["Modello", "Tecnologia", "TCO_Annuo", "CO2_Annua_kg"]].style.format({
            "TCO_Annuo": "€ {:,.2f}",
            "CO2_Annua_kg": "{:,.0f} kg"
        }), use_container_width=True)

    except Exception as e:
        st.error(f"⚠️ Errore durante l'elaborazione: {e}")
        import traceback
        st.code(traceback.format_exc())

else:
    st.info("👆 Carica il tuo file Excel dalla barra laterale per avviare il DSS.")
