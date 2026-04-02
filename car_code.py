import streamlit as st
import pandas as pd
import plotly.express as px

# --- CONFIGURAZIONE PAGINA ---
st.set_page_config(page_title="DSS Mobilità Comuni", page_icon="🚗", layout="wide")

st.title("🚗 DSS Comuni: Confronto Tecnologie Flotta Auto")
st.markdown("Questo strumento permette ai Comuni di confrontare il TCO (Total Cost of Ownership) e le emissioni delle diverse tecnologie.")

# --- 1. CARICAMENTO DEL FILE EXCEL ---
st.sidebar.header("📁 Caricamento Dati")
uploaded_file = st.sidebar.file_uploader("Carica il file Excel (Comparison H2 elc FF.xlsx)", type=["xlsx"])

if uploaded_file:
    try:
        # --- SCELTA DELLA CATEGORIA ---
        st.sidebar.header("🚌 Seleziona Categoria")
        categoria_scelta = st.sidebar.selectbox(
            "Quale flotta vuoi analizzare?", 
            ["AUTO", "CAMION", "AUTOBUS URBANO", "AUTOBUS EXTRAURBANO"]
        )

        # --- LETTURA "CHIRURGICA" DELL'EXCEL ---
        # A seconda della scelta, diciamo a Python quali colonne esatte leggere
        # e di saltare la prima riga (dove c'è il titolo) per prendere le vere intestazioni
        
        if categoria_scelta == "AUTO":
            # Es: Legge le colonne dalla B alla F (Modifica le lettere se la tua tabella è più larga)
            df_modelli = pd.read_excel(uploaded_file, sheet_name="Dati Targa Modelli", usecols="B:F", skiprows=1)
        
        elif categoria_scelta == "CAMION":
            # Es: Legge le colonne dalla K alla O
            df_modelli = pd.read_excel(uploaded_file, sheet_name="Dati Targa Modelli", usecols="K:O", skiprows=1)
            
        elif categoria_scelta == "AUTOBUS URBANO":
            # Es: Legge le colonne dalla T alla X
            df_modelli = pd.read_excel(uploaded_file, sheet_name="Dati Targa Modelli", usecols="T:X", skiprows=1)
            
        elif categoria_scelta == "AUTOBUS EXTRAURBANO":
            # Essendo alla riga 29, dobbiamo dire a Pandas di saltare 29 righe!
            df_modelli = pd.read_excel(uploaded_file, sheet_name="Dati Targa Modelli", usecols="T:X", skiprows=29)

        # Rimuoviamo eventuali righe completamente vuote "pescate" per sbaglio dall'Excel
        df_modelli = df_modelli.dropna(how='all')

        # --- MAPPATURA DELLE COLONNE ---
        # ORA che abbiamo ritagliato la tabella perfetta, usiamo i nomi delle colonne di QUEL blocco.
        # Assicurati che questi nomi siano esattamente quelli della riga 2 (o riga 30 per l'extraurbano)
        COL_TECNOLOGIA = "Combustibile" 
        COL_COSTO_ACQUISTO = "Prezzo Acquisto Veicolo Base"
        COL_CONSUMO = "Consumo Specifico"
        COL_MANUTENZIONE_KM = "Costo Manutenzione per km" 

        # Visto che l'utente ha già scelto la categoria a monte, non ci serve più la colonna "Tipo Veicolo"!
        # Usiamo direttamente la tecnologia come etichetta
        df_modelli["Etichetta_Veicolo"] = df_modelli[COL_TECNOLOGIA].astype(str)

        # Filtriamo il dataframe
        df_auto = df_modelli[["Etichetta_Veicolo", COL_TECNOLOGIA, COL_COSTO_ACQUISTO, COL_CONSUMO, COL_MANUTENZIONE_KM]].copy()
        df_auto.columns = ["Modello", "Tecnologia", "Costo_Acquisto", "Consumo", "Manutenzione_km"]

        # ... IL RESTO DEL CODICE PER I CALCOLI E I GRAFICI RIMANE IDENTICO A PRIMA ...

        # --- 2. MAPPATURA DELLE COLONNE AGGIORNATA CON I TUOI NOMI ---
        COL_TECNOLOGIA = "Combustibile" 
        COL_COSTO_ACQUISTO = "Prezzo Acquisto Veicolo Base"
        COL_CONSUMO = "Consumo Specifico"
        COL_MANUTENZIONE_KM = "Costo Manutenzione per km" 
        # Nota: ho aggiunto anche Tipo Veicolo per avere un nome più chiaro nei grafici
        COL_TIPO = "Tipo Veicolo"

        # Creiamo un'etichetta che unisce il Tipo Veicolo e il Combustibile (es. "SUV - Elettrico")
        df_modelli["Etichetta_Veicolo"] = df_modelli[COL_TIPO].astype(str) + " (" + df_modelli[COL_TECNOLOGIA].astype(str) + ")"

        df_auto = df_modelli[["Etichetta_Veicolo", COL_TECNOLOGIA, COL_COSTO_ACQUISTO, COL_CONSUMO, COL_MANUTENZIONE_KM]].copy()
        df_auto.columns = ["Modello", "Tecnologia", "Costo_Acquisto", "Consumo", "Manutenzione_km"]

        # --- 3. SIDEBAR: INPUT UTENTE (BARRE DI MODIFICA) ---
        st.sidebar.divider()
        st.sidebar.header("⚙️ Parametri di Simulazione")
        
        st.sidebar.subheader("Utilizzo e Vita Utile")
        km_annui = st.sidebar.slider("Percorrenza Annua (km/anno)", min_value=5000, max_value=50000, value=15000, step=1000)
        lifetime = st.sidebar.slider("Anni di utilizzo (Ammortamento)", min_value=1, max_value=20, value=10, step=1)

        st.sidebar.subheader("Costi Energia/Carburante")
        costo_ff = st.sidebar.number_input("Costo Fossile (€/litro)", value=1.80, step=0.05)
        costo_elc = st.sidebar.number_input("Costo Elettricità (€/kWh)", value=0.25, step=0.05)
        costo_h2 = st.sidebar.number_input("Costo Idrogeno (€/kg)", value=12.00, step=0.50)

        # --- 4. MOTORE DI CALCOLO DINAMICO ---
        # Funzione per assegnare il costo energia base al combustibile
        def assegna_costo_energia(tecnologia):
            tec = str(tecnologia).lower()
            if "elettric" in tec or "bev" in tec:
                return costo_elc
            elif "idrogeno" in tec or "h2" in tec or "fcev" in tec:
                return costo_h2
            else:
                return costo_ff

        df_auto["Costo_Energia_Unitario"] = df_auto["Tecnologia"].apply(assegna_costo_energia)

        # Calcoli Finanziari
        df_auto["Costo_Carburante_Annuo"] = (df_auto["Consumo"] / 100) * km_annui * df_auto["Costo_Energia_Unitario"]
        
        # NUOVO CALCOLO: Manutenzione per km moltiplicata per i km annui
        df_auto["Manutenzione_Annua"] = df_auto["Manutenzione_km"] * km_annui
        
        df_auto["OPEX_Annuo"] = df_auto["Costo_Carburante_Annuo"] + df_auto["Manutenzione_Annua"]
        df_auto["CAPEX_Annuo"] = df_auto["Costo_Acquisto"] / lifetime
        df_auto["TCO_Annuo"] = df_auto["CAPEX_Annuo"] + df_auto["OPEX_Annuo"]

        # Funzione temporanea per la CO2 (visto che manca la colonna in Dati Targa Modelli)
        def calcola_co2(row):
            tec = str(row["Tecnologia"]).lower()
            if "elettric" in tec or "idrogeno" in tec or "h2" in tec or "bev" in tec:
                return 0
            else:
                # Stima media di 150 g/km per i fossili (da perfezionare poi col foglio 'Dati')
                return (150 * km_annui) / 1000 

        df_auto["CO2_Annua_kg"] = df_auto.apply(calcola_co2, axis=1)

        # --- 5. VISUALIZZAZIONE RISULTATI ---
        st.subheader("📊 Confronto TCO Annuo: Composizione dei Costi")
        
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

    except Exception as e:
        st.error(f"⚠️ Errore: {e}")

else:
    st.info("👆 Carica il tuo file Excel dalla barra laterale per avviare il DSS.")
