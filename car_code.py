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
        # Leggiamo i due fogli che ci interessano
        df_modelli = pd.read_excel(uploaded_file, sheet_name="Dati Targa Modelli")
        df_dati = pd.read_excel(uploaded_file, sheet_name="Dati")
        
        # --- TRUCCO DA SVILUPPATORE: Mostriamo le colonne disponibili ---
        with st.expander("🛠️ Strumenti per lo Sviluppatore (Espandi per vedere i nomi esatti delle colonne)"):
            st.write("**Colonne nel foglio 'Dati Targa Modelli':**")
            st.write(df_modelli.columns.tolist())
            st.write("**Colonne nel foglio 'Dati':**")
            st.write(df_dati.columns.tolist())

        # --- 2. MAPPATURA DELLE COLONNE (MODIFICA QUI!) ---
        # Sostituisci i testi tra virgolette con i nomi esatti che hai letto nell'expander qui sopra
        COL_TECNOLOGIA = "Tecnologia"            # Es: "Tipo Veicolo", "Motorizzazione"
        COL_COSTO_ACQUISTO = "Costo_Acquisto"    # Es: "Prezzo [€]"
        COL_CONSUMO = "Consumo_per_100km"        # Es: "Consumo Specifico"
        COL_EMISSIONI_CO2 = "Emissioni_CO2"      # Es: "CO2 [g/km]"
        COL_MANUTENZIONE = "Manutenzione_Annua"  # Es: "OPEX Manutenzione [€]"

        # Filtriamo il dataframe per tenere solo le colonne che ci servono e rinominiamole 
        # per standardizzarle nel resto del codice
        df_auto = df_modelli[[COL_TECNOLOGIA, COL_COSTO_ACQUISTO, COL_CONSUMO, COL_EMISSIONI_CO2, COL_MANUTENZIONE]].copy()
        df_auto.columns = ["Tecnologia", "Costo_Acquisto", "Consumo", "CO2", "Manutenzione"]

        # --- 3. SIDEBAR: INPUT UTENTE (BARRE DI MODIFICA) ---
        st.sidebar.divider()
        st.sidebar.header("⚙️ Parametri di Simulazione")
        
        # Parametri di Utilizzo
        st.sidebar.subheader("Utilizzo e Vita Utile")
        km_annui = st.sidebar.slider("Percorrenza Annua (km/anno)", min_value=5000, max_value=50000, value=15000, step=1000)
        lifetime = st.sidebar.slider("Anni di utilizzo (Ammortamento)", min_value=1, max_value=20, value=10, step=1)

        # Costi Carburante
        st.sidebar.subheader("Costi Energia/Carburante")
        costo_ff = st.sidebar.number_input("Costo Fossile (€/litro)", value=1.80, step=0.05)
        costo_elc = st.sidebar.number_input("Costo Elettricità (€/kWh)", value=0.25, step=0.05)
        costo_h2 = st.sidebar.number_input("Costo Idrogeno (€/kg)", value=12.00, step=0.50)

        # --- 4. MOTORE DI CALCOLO DINAMICO ---
        # Creiamo una funzione per assegnare il costo dell'energia in base alla tecnologia
        def assegna_costo_energia(tecnologia):
            tecnologia = str(tecnologia).lower()
            if "elettric" in tecnologia or "bev" in tecnologia:
                return costo_elc
            elif "idrogeno" in tecnologia or "fcev" in tecnologia or "h2" in tecnologia:
                return costo_h2
            else:
                return costo_ff # Default per Diesel/Benzina/Fossile

        df_auto["Costo_Energia_Unitario"] = df_auto["Tecnologia"].apply(assegna_costo_energia)

        # Calcoli Finanziari e Ambientali
        df_auto["Costo_Carburante_Annuo"] = (df_auto["Consumo"] / 100) * km_annui * df_auto["Costo_Energia_Unitario"]
        df_auto["OPEX_Annuo"] = df_auto["Costo_Carburante_Annuo"] + df_auto["Manutenzione"]
        df_auto["CAPEX_Annuo"] = df_auto["Costo_Acquisto"] / lifetime
        df_auto["TCO_Annuo"] = df_auto["CAPEX_Annuo"] + df_auto["OPEX_Annuo"]
        df_auto["CO2_Annua_kg"] = (df_auto["CO2"] * km_annui) / 1000

        # --- 5. VISUALIZZAZIONE RISULTATI ---
        st.subheader("📊 Confronto TCO Annuo: Composizione dei Costi")
        
        # Prepariamo i dati per il grafico Stacked Bar (il migliore per i TCO)
        df_melted = pd.melt(df_auto, id_vars=['Tecnologia'], 
                            value_vars=['CAPEX_Annuo', 'Costo_Carburante_Annuo', 'Manutenzione'],
                            var_name='Voce di Costo', value_name='Euro')
        
        # Rinominiamo le voci per una legenda pulita
        df_melted['Voce di Costo'] = df_melted['Voce di Costo'].replace({
            'CAPEX_Annuo': 'Quota Veicolo (CAPEX)',
            'Costo_Carburante_Annuo': 'Costo Energia/Carburante',
            'Manutenzione': 'Manutenzione Annua'
        })

        # Grafico 1: TCO
        col1, col2 = st.columns(2)
        with col1:
            fig_tco = px.bar(df_melted, x="Tecnologia", y="Euro", color="Voce di Costo",
                             title="TCO: Acquisto vs Operatività",
                             color_discrete_sequence=px.colors.qualitative.Set2)
            fig_tco.update_layout(barmode='stack', yaxis_title="Costo Annuo (€)")
            st.plotly_chart(fig_tco, use_container_width=True)

        # Grafico 2: Emissioni
        with col2:
            fig_co2 = px.bar(df_auto, x="Tecnologia", y="CO2_Annua_kg", 
                             title="Impatto Ambientale: CO2 allo scarico",
                             text="CO2_Annua_kg",
                             color="Tecnologia",
                             color_discrete_sequence=px.colors.qualitative.Safe)
            fig_co2.update_traces(texttemplate='%{text:,.0f} kg', textposition='outside')
            fig_co2.update_layout(yaxis_title="kg di CO2 / anno", showlegend=False)
            st.plotly_chart(fig_co2, use_container_width=True)

        # Tabella di riepilogo dati finale
        st.subheader("📑 Tabella Dati di Sintesi")
        st.dataframe(df_auto[["Tecnologia", "TCO_Annuo", "CO2_Annua_kg"]].style.format({
            "TCO_Annuo": "€ {:,.2f}",
            "CO2_Annua_kg": "{:,.0f} kg"
        }), use_container_width=True)

    except Exception as e:
        st.error(f"⚠️ Si è verificato un errore durante la lettura del file. Verifica i nomi delle colonne. Dettaglio: {e}")

else:
    st.info("👆 Carica il tuo file Excel dalla barra laterale per avviare il DSS.")
