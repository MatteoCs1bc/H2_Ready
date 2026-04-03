import streamlit as st
import pandas as pd
import plotly.express as px
import os

# --- CONFIGURAZIONE PAGINA ---
st.set_page_config(page_title="DSS Comuni: Riscaldamento", page_icon="🔥", layout="wide")
st.title("🔥 DSS Comuni: Analisi Sistemi di Riscaldamento")

NOME_FILE_EXCEL = "Comparison H2 elc FF.xlsx" 

if not os.path.exists(NOME_FILE_EXCEL):
    st.error(f"❌ File '{NOME_FILE_EXCEL}' non trovato nel repository GitHub.")
    st.stop()

try:
    xl = pd.ExcelFile(NOME_FILE_EXCEL, engine='openpyxl')
    
    # Cerchiamo automaticamente il foglio che parla di riscaldamento (o lo facciamo scegliere)
    fogli_disponibili = xl.sheet_names
    foglio_default = next((f for f in fogli_disponibili if "riscaldamento" in f.lower()), fogli_disponibili[0])
    nome_foglio = st.sidebar.selectbox("🏠 Seleziona Foglio Edifici", fogli_disponibili, index=fogli_disponibili.index(foglio_default))
    
    df_raw = pd.read_excel(xl, sheet_name=nome_foglio, header=None, engine='openpyxl')

    def clean_val(x):
        if pd.isna(x) or str(x).strip() == "": return 0.0
        s = str(x).replace('€', '').replace('%', '').replace(' ', '').replace(',', '.')
        try: return float(s)
        except: return 0.0

    # --- 1. ESTRAZIONE DATI BASE (Righe 4-15 -> Indici 3-14) ---
    dati_finali = []
    
    for i in range(3, 15):
        nome_tec = str(df_raw.iloc[i, 1]).strip() # Colonna B
        
        if nome_tec == "" or nome_tec == "nan": 
            continue
            
        # Semplificazione richiesta: Trasformiamo Aria-H2O in PdC generica e ignoriamo la geotermica
        if "Geotermica" in nome_tec:
            continue
        if "Aria-H2O" in nome_tec:
            nome_tec = nome_tec.replace("Aria-H2O", "").strip()
            if nome_tec == "PdC": nome_tec = "Pompa di Calore (PdC)" # Estetica
            
        try:
            dati_finali.append({
                "Tecnologia": nome_tec,
                "Eta_COP_Base": clean_val(df_raw.iloc[i, 3]),     # D: eta o COP
                "Consumo_Base": clean_val(df_raw.iloc[i, 5]),     # F: Consumo vettore
                "En_Prim_Base": clean_val(df_raw.iloc[i, 7]),     # H: Energia primaria
                "Eta_Processo": clean_val(df_raw.iloc[i, 8]),     # I: Eta processo
                "WtW_Base": clean_val(df_raw.iloc[i, 11]),        # L: Emissioni WtW
                "Emiss_Costruz": clean_val(df_raw.iloc[i, 12]),   # M: Emissioni costruzione
                "Maint_Anno": clean_val(df_raw.iloc[i, 17]),      # R: OPEx Maintenance
                "CAPEX_Totale": clean_val(df_raw.iloc[i, 19])     # T: CAPEx (Costo totale impianto)
            })
        except Exception:
            continue

    if not dati_finali:
        st.error("Nessun dato trovato per il riscaldamento. Verifica che le righe 4-15 siano popolate.")
        st.stop()

    df_clean = pd.DataFrame(dati_finali)

    # Parametri globali base letti da Excel
    fabbisogno_base_excel = clean_val(df_raw.iloc[17, 9]) # J18
    lifetime_base_excel = clean_val(df_raw.iloc[18, 9])   # J19
    if fabbisogno_base_excel == 0: fabbisogno_base_excel = 150000
    if lifetime_base_excel == 0: lifetime_base_excel = 15

    # --- 2. LETTURA COSTI COMBUSTIBILE (Righe 18-25 -> Indici 17-24) ---
    st.sidebar.divider()
    st.sidebar.header("⚡ Costi Vettore Energetico")
    
    costi_input_kwh = {} 
    
    # Assegnazione unità di misura per estetica UI
    def get_unit_heat(t):
        t_low = t.lower()
        if "diesel" in t_low or "gasolio" in t_low: return "[€/l]"
        if "pellet" in t_low: return "[€/sacco]"
        if "metano" in t_low: return "[€/Sm3]"
        if "idrogeno" in t_low: return "[€/kg]"
        return "[€/kWh]"

    for r in range(17, 25):
        label = str(df_raw.iloc[r, 1]).strip() # Colonna B
        if label == "" or label == "nan": continue
        
        try:
            val_natura = clean_val(df_raw.iloc[r, 2])     # C: Costo unità nativa
            val_kwh_excel = clean_val(df_raw.iloc[r, 5])  # F: Costo in €/kWh calcolato da Excel
            
            # Calcoliamo il fattore di conversione (PCI, densità, etc.) insito nell'Excel
            fattore = (val_kwh_excel / val_natura) if val_natura > 0 else 1.0
                
            etichetta_ui = f"{label} {get_unit_heat(label)}"
            
            # L'utente imposta il prezzo nell'unità che preferisce (es. a sacco o a litro)
            user_val = st.sidebar.number_input(etichetta_ui, value=float(val_natura), format="%.3f", step=0.05)
            
            # Il motore salva il costo tradotto in kWh per fare i conti esatti
            costi_input_kwh[label] = user_val * fattore
        except:
            pass

    # --- 3. PARAMETRI DI GESTIONE (COP, Fabbisogno, Anni) ---
    st.sidebar.divider()
    st.sidebar.header("⚙️ Parametri Edificio (J18, J19)")
    
    user_fabbisogno = st.sidebar.number_input("Fabbisogno Termico Annuo [kWh_th]", value=float(fabbisogno_base_excel), step=5000.0)
    user_lifetime = st.sidebar.slider("Vita Utile Impianto (y)", 1, 30, int(lifetime_base_excel), step=1)
    
    st.sidebar.divider()
    st.sidebar.header("🌡️ Rendimenti Macchine")
    user_cop_pdc = st.sidebar.number_input("COP Pompa di Calore (PdC)", value=3.2, step=0.1)

    # --- 4. IL MOTORE MATEMATICO (Simulazione su nuovo Fabbisogno) ---
    def calcola_riscaldamento(row):
        t = row["Tecnologia"]
        
        # 1. Trova il costo fuel corretto
        p_fuel_kwh = 0.10
        for k, v in costi_input_kwh.items():
            if k.lower() in t.lower() or (("gasolio" in t.lower()) and ("diesel" in k.lower())):
                p_fuel_kwh = v
                break
        
        # 2. Definisci il rendimento/COP
        attivo_eta_cop = user_cop_pdc if "PdC" in t else row["Eta_COP_Base"]
        if attivo_eta_cop == 0: attivo_eta_cop = 1.0 # Prevenzione div-by-zero
        
        # 3. Ricalcolo Fabbisogni
        consumo_vettore_kwh = user_fabbisogno / attivo_eta_cop
        
        # Fattore di scala rispetto alla base Excel per proiettare Emissioni ed En. Primaria
        fattore_scala = consumo_vettore_kwh / row["Consumo_Base"] if row["Consumo_Base"] > 0 else 1.0
        
        en_primaria = row["En_Prim_Base"] * fattore_scala
        wtw_annuo = row["WtW_Base"] * fattore_scala
        
        # 4. Calcoli Economici
        fuel_annuo = consumo_vettore_kwh * p_fuel_kwh
        maint_annuo = row["Maint_Anno"] # Assunto fisso annuo come da Excel
        capex_annuo = row["CAPEX_Totale"] / user_lifetime
        
        costo_annuo_tot = fuel_annuo + maint_annuo + capex_annuo
        costo_tot_life = (fuel_annuo + maint_annuo) * user_lifetime + row["CAPEX_Totale"]
        
        # 5. Calcoli Ambientali
        emiss_annue_tons = (wtw_annuo + (row["Emiss_Costruz"] / user_lifetime)) / 1000
        emiss_totali_lca = emiss_annue_tons * user_lifetime
        
        return pd.Series([
            en_primaria, row["Eta_Processo"], wtw_annuo, emiss_totali_lca,
            fuel_annuo, maint_annuo, capex_annuo, costo_annuo_tot,
            fuel_annuo * user_lifetime, maint_annuo * user_lifetime, costo_tot_life
        ])

    df_clean[['En_Primaria', 'Eta_Proc', 'WtW_Annuo', 'Emiss_Tot_LCA',
              'Fuel_Annuo', 'Maint_Annuo', 'CAPEx_Annuo', 'Costo_Annuo_Tot',
              'Fuel_Tot', 'Maint_Tot', 'Costo_Totale']] = df_clean.apply(calcola_riscaldamento, axis=1)

    # --- 5. VISUALIZZAZIONE RISULTATI (6 GRAFICI) ---
    st.divider()
    
    # RIGA 1
    c1, c2 = st.columns(2)
    with c1:
        st.subheader("1. Energia Primaria Richiesta [kWh]")
        fig1 = px.bar(df_clean, x="Tecnologia", y="En_Primaria", color="Tecnologia")
        st.plotly_chart(fig1, use_container_width=True)
    with c2:
        st.subheader("2. Efficienza di Processo (η)")
        df_clean["Eta_Perc"] = df_clean["Eta_Proc"] * 100 if df_clean["Eta_Proc"].mean() < 2 else df_clean["Eta_Proc"]
        fig2 = px.bar(df_clean, x="Tecnologia", y="Eta_Perc", color="Tecnologia", text_auto='.1f')
        fig2.update_layout(yaxis_title="Rendimento %")
        st.plotly_chart(fig2, use_container_width=True)

    # RIGA 2
    c3, c4 = st.columns(2)
    with c3:
        st.subheader("3. Emissioni WtW [kg CO2/anno]")
        fig3 = px.bar(df_clean, x="Tecnologia", y="WtW_Annuo", color="Tecnologia")
        st.plotly_chart(fig3, use_container_width=True)
    with c4:
        st.subheader("4. Emissioni Totali LCA [t CO2]")
        fig4 = px.bar(df_clean, x="Tecnologia", y="Emiss_Tot_LCA", color="Tecnologia")
        st.plotly_chart(fig4, use_container_width=True)

    # RIGA 3
    c5, c6 = st.columns(2)
    with c5:
        st.subheader("5. Costo Annuo (TCO/y) [€/anno]")
        df_plot_y = df_clean.melt(id_vars="Tecnologia", value_vars=['CAPEx_Annuo', 'Maint_Annuo', 'Fuel_Annuo'], 
                                  var_name="Voce", value_name="Euro")
        df_plot_y["Voce"] = df_plot_y["Voce"].replace({'CAPEx_Annuo':'CAPEx (Quota)', 'Maint_Annuo':'OPEx (Manut)', 'Fuel_Annuo':'OPEx (Fuel)'})
        fig5 = px.bar(df_plot_y, x="Tecnologia", y="Euro", color="Voce", barmode='stack',
                      color_discrete_sequence=["#0068C9", "#FFA421", "#FF4B4B"])
        st.plotly_chart(fig5, use_container_width=True)
        
    with c6:
        st.subheader("6. Costo Totale Vita (TCO) [€]")
        df_clean['CAPEx_Acquisto'] = df_clean['CAPEX_Totale']
        df_plot_tot = df_clean.melt(id_vars="Tecnologia", value_vars=['CAPEx_Acquisto', 'Maint_Tot', 'Fuel_Tot'], 
                                    var_name="Voce", value_name="Euro")
        df_plot_tot["Voce"] = df_plot_tot["Voce"].replace({'CAPEx_Acquisto':'CAPEx (Investimento)', 'Maint_Tot':'OPEx (Manut)', 'Fuel_Tot':'OPEx (Fuel)'})
        fig6 = px.bar(df_plot_tot, x="Tecnologia", y="Euro", color="Voce", barmode='stack',
                      color_discrete_sequence=["#0068C9", "#FFA421", "#FF4B4B"])
        st.plotly_chart(fig6, use_container_width=True)

    # --- TABELLA RIASSUNTIVA ---
    st.subheader("📋 Tabella Dati Analitici")
    st.dataframe(df_clean[["Tecnologia", "En_Primaria", "WtW_Annuo", "Costo_Annuo_Tot", "Costo_Totale", "Emiss_Tot_LCA"]].style.format({
        "En_Primaria": "{:,.0f} kWh",
        "WtW_Annuo": "{:,.0f} kg",
        "Costo_Annuo_Tot": "€ {:,.0f}",
        "Costo_Totale": "€ {:,.0f}",
        "Emiss_Tot_LCA": "{:,.1f} t"
    }), use_container_width=True)

except Exception as e:
    st.error(f"Errore di Elaborazione: {e}")
