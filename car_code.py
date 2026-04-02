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

        # Lettura "chirurgica" del foglio in base alla scelta
        # NOTA: Aggiorna le lettere di 'usecols' in base a quanto è larga la tua tabella in Excel
        if categoria_scelta == "AUTO":
            df_modelli = pd.read_excel(uploaded_file, sheet_name="Dati Targa Modelli", usecols="B:F", skiprows=1)
        elif categoria_scelta == "CAMION":
            df_modelli = pd.read_excel(uploaded_file, sheet_name="Dati Targa Modelli", usecols="K:O", skiprows=1)
        elif categoria_scelta == "AUTOBUS URBANO":
            df_modelli = pd.read_excel(uploaded_file, sheet_name="Dati Targa Modelli", usecols="T:X", skiprows=1)
        elif categoria_scelta == "AUTOBUS EXTRAURBANO":
            df_modelli = pd.read_excel(uploaded_file, sheet_name="Dati Targa Modelli", usecols="T:X", skiprows=29)

        # Pulizia righe vuote
        df_modelli = df_modelli.dropna(how='all')

        # --- TRUCCO DI DEBUG (Lascialo qui nel caso serva in futuro) ---
        with st.expander("🛠️ DEBUG: Guarda come Python vede le tue colonne"):
            st.write(f"Intestazioni trovate per la categoria {categoria_scelta}:")
            st.write(df_modelli.columns.tolist())

        # --- 3. MAPPATURA DELLE COLONNE ---
        # ORA USIAMO SOLO I NOMI "UNNAMED" TROVATI DAL DEBUGGER!
        
        # In base al tuo esempio, assegniamo gli Unnamed corretti:
        # Unnamed: 1 = Modello
        # Unnamed: 2 = Serbatoio (non ci serve per i calcoli)
        # Unnamed: 3 = Autonomia (non ci serve)
        # Unnamed: 4 = Consumo
        # Unnamed: 5 = Costo
        
        COL_MODELLO = "Unnamed: 1"
        COL_CONSUMO = "Unnamed: 4"
        COL_COSTO_ACQUISTO = "Unnamed: 5"
        
        # Visto che la "Tecnologia" (Benzina, Elettrico) nel tuo Excel è un titolo
        # sopra la tabella e NON una colonna, per ora "freghiamo" il sistema 
        # duplicando la colonna del modello, poi lo aggiusteremo!
        COL_TECNOLOGIA = "Unnamed: 1" 

        # Ritagliamo solo le colonne che ci servono
        df_auto = df_modelli[[COL_MODELLO, COL_TECNOLOGIA, COL_COSTO_ACQUISTO, COL_CONSUMO]].copy()
        
        # Rinominiamo le colonne in modo pulito per far funzionare i grafici
        df_auto.columns = ["Modello", "Tecnologia", "Costo_Acquisto", "Consumo"]

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
        
        # A. Assegnazione Costo Energia
        def assegna_costo_energia(tecnologia):
            tec = str(tecnologia).lower()
            if "elettric" in tec or "bev" in tec:
                return costo_elc
            elif "idrogeno" in tec or "h2" in tec or "fcev" in tec:
                return costo_h2
            else:
                return costo_ff

        df_auto["Costo_Energia_Unitario"] = df_auto["Tecnologia"].apply(assegna_costo_energia)

        # B. Assegnazione Costi Manutenzione Base (Dal foglio 'Dati')
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

        # C. Calcoli Finanziari (TCO)
        # Manutenzione Annua = Tariffa al km * km percorsi
        df_auto["Manutenzione_Annua"] = df_auto["Tariffa_Manutenzione_km"] * km_annui
        
        # Costo Carburante = Consumo (al km) * km percorsi * costo unitario
        df_auto["Costo_Carburante_Annuo"] = df_auto["Consumo"] * km_annui * df_auto["Costo_Energia_Unitario"]
        
        df_auto["OPEX_Annuo"] = df_auto["Costo_Carburante_Annuo"] + df_auto["Manutenzione_Annua"]
        df_auto["CAPEX_Annuo"] = df_auto["Costo_Acquisto"] / lifetime
        df_auto["TCO_Annuo"] = df_auto["CAPEX_Annuo"] + df_auto["OPEX_Annuo"]

        # D. Calcolo CO2 (Semplificato)
        def calcola_co2(row):
            tec = str(row["Tecnologia"]).lower()
            if "elettric" in tec or "idrogeno" in tec or "bev" in tec:
                return 0
            else:
                return (150 * km_annui) / 1000 # Stima base 150 g/km per i fossili

        df_auto["CO2_Annua_kg"] = df_auto.apply(calcola_co2, axis=1)

        # --- 6. VISUALIZZAZIONE RISULTATI ---
        st.subheader(f"📊 Confronto TCO Annuo: {categoria_scelta}")
        
        # Prepariamo i dati per il grafico Stacked Bar
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
        st.info("💡 Suggerimento: Controlla la sezione 'Mappatura delle Colonne' (riga 40 del codice) per assicurarti che i nomi corrispondano esattamente a quelli del tuo Excel.")

else:
    st.info("👆 Carica il tuo file Excel dalla barra laterale per avviare il DSS.")
