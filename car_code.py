import streamlit as st
import pandas as pd
import plotly.express as px

# --- CONFIGURAZIONE PAGINA ---
st.set_page_config(page_title="DSS Mobilità Comuni", page_icon="🚗", layout="wide")
st.title("🚗 DSS Comuni: Supporto Decisionale Tecnologie H2/EV")

# --- 1. CARICAMENTO DEL FILE EXCEL ---
st.sidebar.header("📁 Caricamento Database")
uploaded_file = st.sidebar.file_uploader("Carica il file 'Comparison H2 elc FF.xlsx'", type=["xlsx"])

if uploaded_file:
    try:
        # Carichiamo l'elenco dei fogli per evitare errori di nome
        xl = pd.ExcelFile(uploaded_file)
        fogli_disponibili = xl.sheet_names

        # --- 2. SCELTA DELLA CATEGORIA ---
        st.sidebar.header("🚌 Selezione Flotta")
        categoria_utente = st.sidebar.selectbox(
            "Quale categoria vuoi analizzare?", 
            ["AUTO", "CAMION", "AUTOBUS URBANO", "AUTOBUS EXTRAURBANO"]
        )

        # Cerchiamo il foglio corrispondente (es. se l'utente sceglie AUTO, cerchiamo "AUTO" o "Auto")
        nome_foglio = next((f for f in fogli_disponibili if f.upper() == categoria_utente), None)

        if not nome_foglio:
            st.error(f"Foglio '{categoria_utente}' non trovato nell'Excel. Fogli presenti: {fogli_disponibili}")
            st.stop()

        # --- 3. LETTURA COSTI FUEL (C20:C26) ---
        # Leggiamo i costi carburante dal foglio scelto (o dal foglio 'Dati' se preferisci)
        # Qui ipotizziamo siano nel foglio della categoria stessa come da tua indicazione
        df_fuel = pd.read_excel(uploaded_file, sheet_name=nome_foglio, usecols="B:C", skiprows=19, nrows=7, header=None)
        df_fuel.columns = ["Tipo", "Valore"]
        
        st.sidebar.divider()
        st.sidebar.header("⚡ Costi Carburante [€/kWh]")
        
        # Creiamo gli input dinamici usando i valori letti dall'Excel come default
        costi_input = {}
        for i, row in df_fuel.iterrows():
            nome_label = str(row["Tipo"])
            valore_def = float(row["Valore"]) if pd.notnull(row["Valore"]) else 0.0
            costi_input[nome_label] = st.sidebar.number_input(nome_label, value=valore_def, format="%.3f")

        # --- 4. LETTURA TABELLA OUTPUT (Benzina in B5) ---
        # Saltiamo 3 righe per arrivare alla testata della tabella (riga 4)
        df_output = pd.read_excel(uploaded_file, sheet_name=nome_foglio, skiprows=3)
        
        # Pulizia: teniamo solo le righe delle tecnologie principali
        tecnologie_target = ["Benzina", "Diesel", "Elettrico rete", "Elettrico autoprodotto", 
                             "Idrogeno Grigio", "Idrogeno rete", "Idrogeno autoprodotto"]
        
        # Filtriamo la colonna B (che Pandas chiamerà probabilmente 'Unnamed: 1' se la cella B4 è vuota)
        # Cerchiamo la colonna che contiene "Benzina"
        col_tec_name = df_output.columns[1] 
        df_final = df_output[df_output[col_tec_name].isin(tecnologie_target)].copy()

        # Mappatura colonne basata sulla tua descrizione dell'output
        # Nota: i nomi devono corrispondere a quelli della riga 4 del tuo Excel
        mappa_colonne = {
            col_tec_name: "Tecnologia",
            "Consumo": "Consumo_kWh_km",
            "WtW - [kgCO2/anno]": "CO2_Annua",
            "CAPEx": "Costo_Veicolo",
            "OPEx Maintenance": "Manutenzione_km"
        }
        
        # Rinominiamo solo le colonne che troviamo
        df_display = df_final.rename(columns=mappa_colonne)

        # --- 5. PARAMETRI DI SIMULAZIONE ---
        st.sidebar.divider()
        km_annui = st.sidebar.slider("Percorrenza Annua (km/anno)", 5000, 100000, 15000)
        lifetime = st.sidebar.slider("Anni Ammortamento", 1, 20, 10)

        # --- 6. CALCOLO DINAMICO TCO ---
        def calcola_tco(row):
            tec = row["Tecnologia"]
            prezzo_energia = costi_input.get(tec, 0.20) # Se non trova il nome, usa 0.20
            
            fuel_annuo = row["Consumo_kWh_km"] * km_annui * prezzo_energia
            manut_annua = row["Manutenzione_km"] * km_annui
            capex_annuo = row["Costo_Veicolo"] / lifetime
            return fuel_annuo + manut_annua + capex_annuo

        df_display["TCO_Annuo_Simulato"] = df_display.apply(calcola_tco, axis=1)

        # --- 7. GRAFICI ---
        col_sx, col_dx = st.columns(2)
        
        with col_sx:
            st.subheader("💰 Costo Totale Annuo (TCO)")
            fig_tco = px.bar(df_display, x="Tecnologia", y="TCO_Annuo_Simulato", 
                             color="Tecnologia", title="Confronto Costi (€/anno)")
            st.plotly_chart(fig_tco, use_container_width=True)

        with col_dx:
            st.subheader("🌱 Emissioni CO2 (WtW)")
            # Proporzioniamo la CO2 ai nuovi km (assumendo che il dato Excel sia su 15.000km)
            df_display["CO2_Scalata"] = (df_display["CO2_Annua"] / 15000) * km_annui
            fig_co2 = px.bar(df_display, x="Tecnologia", y="CO2_Scalata", 
                             title="Emissioni Annuali (kg CO2/anno)")
            st.plotly_chart(fig_co2, use_container_width=True)

        st.subheader("📋 Tabella Dati Analitici")
        st.write(df_display[["Tecnologia", "TCO_Annuo_Simulato", "CO2_Scalata"]])

    except Exception as e:
        st.error(f"Errore tecnico: {e}")
        st.info("Assicurati che i nomi delle colonne nell'Excel (riga 4) corrispondano a: 'Consumo', 'WtW - [kgCO2/anno]', 'CAPEx', 'OPEx Maintenance'")

else:
    st.info("👋 Benvenuto! Carica il file Excel per visualizzare il Decision Support System.")
