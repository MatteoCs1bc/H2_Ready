import streamlit as st
import pandas as pd
import plotly.express as px
import os

# --- CONFIGURAZIONE PAGINA ---
st.set_page_config(page_title="DSS Mobilità Comuni", page_icon="🚗", layout="wide")
st.title("🚗 DSS Comuni: Analisi Completa Flotta")

NOME_FILE_EXCEL = "Comparison H2 elc FF.xlsx" 

if not os.path.exists(NOME_FILE_EXCEL):
    st.error(f"❌ File '{NOME_FILE_EXCEL}' non trovato.")
    st.stop()

try:
    xl = pd.ExcelFile(NOME_FILE_EXCEL, engine='openpyxl')
    categoria_utente = st.sidebar.selectbox("🚌 Seleziona Flotta", ["AUTO", "CAMION", "AUTOBUS URBANO", "AUTOBUS EXTRAURBANO"])
    nome_foglio = next((f for f in xl.sheet_names if f.upper() == categoria_utente), xl.sheet_names[0])
    
    df_raw = pd.read_excel(xl, sheet_name=nome_foglio, header=None, engine='openpyxl')

    def clean_val(x):
        if pd.isna(x) or str(x).strip() == "": return 0.0
        s = str(x).replace('€', '').replace('%', '').replace(' ', '').replace(',', '.')
        try: return float(s)
        except: return 0.0

    # --- 1. ESTRAZIONE DATI BASE (Le tue 7 Tecnologie!) ---
    dati_finali = []
    tecnologie_cercate = ["Benzina", "Diesel", "Elettrico rete", "Elettrico autoprodotto", 
                          "Idrogeno Grigio", "Idrogeno rete", "Idrogeno autoprodotto"]

    for i in range(min(25, len(df_raw))):
        nome_tec = str(df_raw.iloc[i, 1]).strip() # Colonna B
        # Risolve eventuali problemi di maiuscole/minuscole
        match_tec = next((t for t in tecnologie_cercate if t.lower() == nome_tec.lower()), None)
        
        if match_tec:
            try:
                dati_finali.append({
                    "Tecnologia": match_tec,
                    "Autonomia": clean_val(df_raw.iloc[i, 3]),        # D
                    "Consumo": clean_val(df_raw.iloc[i, 4]),          # E
                    "Eta_WtW": clean_val(df_raw.iloc[i, 9]),          # J (Rendimento)
                    "En_Primaria_Base": clean_val(df_raw.iloc[i, 13]),# N (Calcolata base Excel)
                    "Emiss_Annue_Q": clean_val(df_raw.iloc[i, 16]),   # Q (P+O) base Excel
                    "Emiss_Costruz": clean_val(df_raw.iloc[i, 17]),   # R (M59) Costruzione fissa
                    "Maint_km": clean_val(df_raw.iloc[i, 22]),        # W (Costo Maint €/km)
                    "CAPEX_Totale": clean_val(df_raw.iloc[i, 25])     # Z (Costo acquisto €)
                })
            except Exception:
                continue

    if not dati_finali:
        st.error("Nessun dato trovato.")
        st.stop()

    df_clean = pd.DataFrame(dati_finali)

    # Assicuriamoci che l'ordine delle righe rispetti il tuo (Benzina -> Idrogeno)
    df_clean['Tecnologia'] = pd.Categorical(df_clean['Tecnologia'], categories=tecnologie_cercate, ordered=True)
    df_clean = df_clean.sort_values('Tecnologia')

    # --- 2. LETTURA COSTI FUEL (B20:C26) ---
    st.sidebar.divider()
    st.sidebar.header("⚡ Costi Carburante [€/kWh]")
    costi_input = {}
    
    riga_prezzi = 19
    for r in range(12, len(df_raw)):
        if str(df_raw.iloc[r, 1]).strip() == "Benzina":
            riga_prezzi = r
            break
            
    for r in range(riga_prezzi, riga_prezzi + 7):
        try:
            label = str(df_raw.iloc[r, 1]).strip()
            # Mappa per ignorare piccole differenze di testo
            match_label = next((t for t in tecnologie_cercate if t.lower() in label.lower() or label.lower() in t.lower()), label)
            val_def = clean_val(df_raw.iloc[r, 2])
            costi_input[match_label] = st.sidebar.number_input(match_label, value=val_def, format="%.3f")
        except:
            pass

    # --- 3. PARAMETRI UTENTE ---
    st.sidebar.divider()
    st.sidebar.header("⚙️ Parametri Flotta (C16, C17)")
    
    km_annui = st.sidebar.slider("Percorrenza Annua (km/y)", 5000, 100000, 15000, step=1000)
    lifetime = st.sidebar.slider("Anni di Utilizzo (y)", 1, 20, 10, step=1)
    km_totali = km_annui * lifetime
    
    # Mostriamo la percorrenza totale in modo chiaro
    st.sidebar.metric(label="Percorrenza Totale [km]", value=f"{km_totali:,}".replace(',', '.'))
    
    KM_BASE_EXCEL = 15000 # Costante usata nel tuo Excel per calcoli annui

    # --- 4. IL MOTORE MATEMATICO (Le tue formule) ---
    def esegui_calcoli(row):
        t = row["Tecnologia"]
        p_fuel = next((v for k, v in costi_input.items() if k.lower() in t.lower()), 0.20)
        
        # COSTI
        fuel_annuo = row["Consumo"] * km_annui * p_fuel          # V5
        maint_annuo = row["Maint_km"] * km_annui                 # X5
        capex_annuo = row["CAPEX_Totale"] / lifetime             # Y5
        
        fuel_totale = fuel_annuo * lifetime
        maint_totale = maint_annuo * lifetime
        
        costo_annuo_tot = fuel_annuo + maint_annuo + capex_annuo
        costo_tot_life = fuel_totale + maint_totale + row["CAPEX_Totale"] # AB5
        
        # EMISSIONI ED ENERGIA
        # Riproporzioniamo dai 15.000km standard ai km reali scelti
        en_primaria = row["En_Primaria_Base"] * (km_annui / KM_BASE_EXCEL) # N5
        emiss_annue = row["Emiss_Annue_Q"] * (km_annui / KM_BASE_EXCEL)    # Q5
        
        # S5 = (Costruzione + Annue * Lifetime) / 1000
        emiss_totali_tons = (row["Emiss_Costruz"] + (emiss_annue * lifetime)) / 1000
        
        return pd.Series([
            fuel_annuo, maint_annuo, capex_annuo, costo_annuo_tot,
            fuel_totale, maint_totale, costo_tot_life,
            en_primaria, emiss_annue, emiss_totali_tons
        ])

    df_clean[['OPEx_Fuel_y', 'OPEx_Maint_y', 'CAPEx_y', 'Costo_Annuo_Tot',
              'OPEx_Fuel_Tot', 'OPEx_Maint_Tot', 'Costo_Totale',
              'En_Primaria_y', 'Emiss_Annue', 'Emiss_Tot_Tons']] = df_clean.apply(esegui_calcoli, axis=1)

    # --- 5. VISUALIZZAZIONE RISULTATI (8 Grafici in Griglia 2x4) ---
    st.divider()
    
    # RIGA 1: Autonomia e Consumo
    c1, c2 = st.columns(2)
    with c1:
        st.subheader("1. Autonomia [km]")
        fig1 = px.bar(df_clean, x="Tecnologia", y="Autonomia", color="Tecnologia")
        st.plotly_chart(fig1, use_container_width=True)
    with c2:
        st.subheader("2. Consumo [kWh/km]")
        fig2 = px.bar(df_clean, x="Tecnologia", y="Consumo", color="Tecnologia")
        st.plotly_chart(fig2, use_container_width=True)

    # RIGA 2: Efficienza e Energia Primaria
    c3, c4 = st.columns(2)
    with c3:
        st.subheader("3. Efficienza WtW (η) [-]")
        # Moltiplichiamo per 100 per avere la percentuale visibile nel grafico se il dato in Excel è es. 0.21
        df_clean["Eta_Percent"] = df_clean["Eta_WtW"] * 100 if df_clean["Eta_WtW"].mean() < 2 else df_clean["Eta_WtW"]
        fig3 = px.bar(df_clean, x="Tecnologia", y="Eta_Percent", color="Tecnologia", text_auto='.1f')
        fig3.update_layout(yaxis_title="Rendimento %")
        st.plotly_chart(fig3, use_container_width=True)
    with c4:
        st.subheader("4. Energia Primaria [kWh/anno]")
        fig4 = px.bar(df_clean, x="Tecnologia", y="En_Primaria_y", color="Tecnologia")
        st.plotly_chart(fig4, use_container_width=True)

    # RIGA 3: Emissioni
    c5, c6 = st.columns(2)
    with c5:
        st.subheader("5. Emissioni Annue [kgCO2/anno]")
        fig5 = px.bar(df_clean, x="Tecnologia", y="Emiss_Annue", color="Tecnologia")
        st.plotly_chart(fig5, use_container_width=True)
    with c6:
        st.subheader("6. Emissioni Totali Vita [tCO2]")
        fig6 = px.bar(df_clean, x="Tecnologia", y="Emiss_Tot_Tons", color="Tecnologia")
        st.plotly_chart(fig6, use_container_width=True)

    # RIGA 4: Costi (Stack CAPEx/OPEx)
    c7, c8 = st.columns(2)
    with c7:
        st.subheader("7. Costo Annuo [€/anno]")
        df_plot_y = df_clean.melt(id_vars="Tecnologia", value_vars=['CAPEx_y', 'OPEx_Maint_y', 'OPEx_Fuel_y'], 
                                  var_name="Voce", value_name="Euro")
        df_plot_y["Voce"] = df_plot_y["Voce"].replace({'CAPEx_y':'CAPEx (Quota Acq.)', 'OPEx_Maint_y':'OPEx (Manut)', 'OPEx_Fuel_y':'OPEx (Fuel)'})
        fig7 = px.bar(df_plot_y, x="Tecnologia", y="Euro", color="Voce", barmode='stack',
                      color_discrete_sequence=["#0068C9", "#FFA421", "#FF4B4B"])
        st.plotly_chart(fig7, use_container_width=True)
        
    with c8:
        st.subheader("8. Costo Totale (TCO) [€]")
        # Usa il CAPEX intero (Costo Acquisto), OPEX Maint Totale e OPEX Fuel Totale
        df_clean['CAPEx_Totale_Bar'] = df_clean['CAPEX_Totale']
        df_plot_tot = df_clean.melt(id_vars="Tecnologia", value_vars=['CAPEx_Totale_Bar', 'OPEx_Maint_Tot', 'OPEx_Fuel_Tot'], 
                                    var_name="Voce", value_name="Euro")
        df_plot_tot["Voce"] = df_plot_tot["Voce"].replace({'CAPEx_Totale_Bar':'CAPEx (Acquisto)', 'OPEx_Maint_Tot':'OPEx (Manut)', 'OPEx_Fuel_Tot':'OPEx (Fuel)'})
        fig8 = px.bar(df_plot_tot, x="Tecnologia", y="Euro", color="Voce", barmode='stack',
                      color_discrete_sequence=["#0068C9", "#FFA421", "#FF4B4B"])
        st.plotly_chart(fig8, use_container_width=True)

    # --- TABELLA RIASSUNTIVA ---
    st.subheader("📋 Data Table Completa")
    st.dataframe(df_clean[["Tecnologia", "Autonomia", "Consumo", "Eta_WtW", "Costo_Annuo_Tot", "Costo_Totale", "Emiss_Tot_Tons"]].style.format({
        "Autonomia": "{:,.0f} km",
        "Consumo": "{:.3f} kWh/km",
        "Eta_WtW": "{:.1%}",
        "Costo_Annuo_Tot": "€ {:,.0f}",
        "Costo_Totale": "€ {:,.0f}",
        "Emiss_Tot_Tons": "{:,.1f} t"
    }), use_container_width=True)

except Exception as e:
    st.error(f"Errore di Elaborazione: {e}")
