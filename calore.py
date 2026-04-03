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
    
    # 1. SELEZIONE AUTOMATICA DEL FOGLIO (Niente più menu a tendina)
    fogli_disponibili = xl.sheet_names
    # Cerca un foglio che si chiami "riscaldamento", altrimenti prende il primo
    nome_foglio = next((f for f in fogli_disponibili if "riscaldam" in f.lower()), fogli_disponibili[0])
    
    # Leggiamo il foglio
    df_raw = pd.read_excel(xl, sheet_name=nome_foglio, header=None, engine='openpyxl')

    # --- FUNZIONI SCUDO ANTI-CRASH (Evitano l'errore "Out of bounds") ---
    def safe_str(df, r, c):
        if r < len(df) and c < len(df.columns):
            val = df.iloc[r, c]
            if pd.isna(val): return ""
            return str(val).strip()
        return ""

    def safe_num(df, r, c):
        if r < len(df) and c < len(df.columns):
            val = df.iloc[r, c]
            if pd.isna(val) or str(val).strip() == "": return 0.0
            s = str(val).replace('€', '').replace('%', '').replace(' ', '').replace(',', '.')
            try: return float(s)
            except: return 0.0
        return 0.0

    # --- 2. ESTRAZIONE DATI BASE (Righe 4-15 -> Indici 3-14) ---
    dati_finali = []
    
    for i in range(3, 15):
        nome_tec = safe_str(df_raw, i, 1) # Colonna B
        
        if nome_tec == "" or nome_tec.lower() == "nan": 
            continue
            
        # Semplificazione: Trasformiamo Aria-H2O in PdC generica e ignoriamo la geotermica
        if "Geotermica" in nome_tec: continue
        if "Aria-H2O" in nome_tec:
            nome_tec = nome_tec.replace("Aria-H2O", "").strip()
            if nome_tec == "PdC": nome_tec = "Pompa di Calore (PdC)"
            
        try:
            dati_finali.append({
                "Tecnologia": nome_tec,
                "Eta_COP_Base": safe_num(df_raw, i, 3),     # D: eta o COP
                "Consumo_Base": safe_num(df_raw, i, 5),     # F: Consumo vettore
                "En_Prim_Base": safe_num(df_raw, i, 7),     # H: Energia primaria
                "Eta_Processo": safe_num(df_raw, i, 8),     # I: Eta processo
                "WtW_Base": safe_num(df_raw, i, 11),        # L: Emissioni WtW
                "Emiss_Costruz": safe_num(df_raw, i, 12),   # M: Emissioni costruzione
                "Maint_Anno": safe_num(df_raw, i, 17),      # R: OPEx Maintenance
                "CAPEX_Totale": safe_num(df_raw, i, 19)     # T: CAPEx (Costo totale)
            })
        except Exception:
            continue

    if not dati_finali:
        st.error(f"Nessun dato valido trovato nel foglio '{nome_foglio}'.")
        st.stop()

    df_clean = pd.DataFrame(dati_finali)

    # Parametri globali (J18, J19) estratti con lo scudo
    fabbisogno_base_excel = safe_num(df_raw, 17, 9) # J18
    lifetime_base_excel = safe_num(df_raw, 18, 9)   # J19
    if fabbisogno_base_excel == 0: fabbisogno_base_excel = 150000
    if lifetime_base_excel == 0: lifetime_base_excel = 15

    # --- 3. LETTURA COSTI COMBUSTIBILE (Righe 18-25 -> Indici 17-24) ---
    st.sidebar.divider()
    st.sidebar.header("⚡ Costi Vettore Energetico")
    
    costi_input_kwh = {} 
    
    def get_unit_heat(t):
        t_low = t.lower()
        if "diesel" in t_low or "gasolio" in t_low: return "[€/l]"
        if "pellet" in t_low: return "[€/sacco]"
        if "metano" in t_low: return "[€/Sm3]"
        if "idrogeno" in t_low: return "[€/kg]"
        return "[€/kWh]"

    for r in range(17, 25):
        label = safe_str(df_raw, r, 1) # Colonna B
        if label == "" or label.lower() == "nan": continue
        
        try:
            val_natura = safe_num(df_raw, r, 2)     # C: Costo unità nativa
            val_kwh_excel = safe_num(df_raw, r, 5)  # F: Costo in €/kWh (da Excel)
            
            # Fattore di conversione implicito
            fattore = (val_kwh_excel / val_natura) if val_natura > 0 else 1.0
                
            etichetta_ui = f"{label} {get_unit_heat(label)}"
            
            user_val = st.sidebar.number_input(etichetta_ui, value=float(val_natura), format="%.3f", step=0.05)
            costi_input_kwh[label] = user_val * fattore
        except:
            pass

    # --- 4. PARAMETRI DI GESTIONE (COP, Fabbisogno, Anni) ---
    st.sidebar.divider()
    st.sidebar.header("⚙️ Parametri Edificio")
    
    user_fabbisogno = st.sidebar.number_input("Fabbisogno Termico [kWh_th/y]", value=float(fabbisogno_base_excel), step=5000.0)
    user_lifetime = st.sidebar.slider("Vita Utile Impianto (y)", 1, 30, int(lifetime_base_excel), step=1)
    
    st.sidebar.divider()
    st.sidebar.header("🌡️ Rendimento PdC")
    user_cop_pdc = st.sidebar.number_input("COP Pompa di Calore", value=3.2, step=0.1)

    # --- 5. IL MOTORE MATEMATICO ---
    def calcola_riscaldamento(row):
        t = row["Tecnologia"]
        
        # Abbinamento flessibile del costo combustibile
        p_fuel_kwh = 0.10
        for k, v in costi_input_kwh.items():
            if k.lower() in t.lower() or (("gasolio" in t.lower()) and ("diesel" in k.lower())):
                p_fuel_kwh = v
                break
        
        attivo_eta_cop = user_cop_pdc if "PdC" in t else row["Eta_COP_Base"]
        if attivo_eta_cop == 0: attivo_eta_cop = 1.0 
        
        # Proiezione sui nuovi fabbisogni
        consumo_vettore_kwh = user_fabbisogno / attivo_eta_cop
        fattore_scala = consumo_vettore_kwh / row["Consumo_Base"] if row["Consumo_Base"] > 0 else 1.0
        
        en_primaria = row["En_Prim_Base"] * fattore_scala
        wtw_annuo = row["WtW_Base"] * fattore_scala
        
        # Economia
        fuel_annuo = consumo_vettore_kwh * p_fuel_kwh
        maint_annuo = row["Maint_Anno"] 
        capex_annuo = row["CAPEX_Totale"] / user_lifetime
        
        costo_annuo_tot = fuel_annuo + maint_annuo + capex_annuo
        costo_tot_life = (fuel_annuo + maint_annuo) * user_lifetime + row["CAPEX_Totale"]
        
        # Ambiente
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

    # --- 6. VISUALIZZAZIONE RISULTATI ---
    st.divider()
    
    c1, c2 = st.columns(2)
    with c1:
        st.subheader("1. Energia Primaria Richiesta [kWh/y]")
        fig1 = px.bar(df_clean, x="Tecnologia", y="En_Primaria", color="Tecnologia")
        st.plotly_chart(fig1, use_container_width=True)
    with c2:
        st.subheader("2. Efficienza di Processo (η)")
        df_clean["Eta_Perc"] = df_clean["Eta_Proc"] * 100 if df_clean["Eta_Proc"].mean() < 2 else df_clean["Eta_Proc"]
        fig2 = px.bar(df_clean, x="Tecnologia", y="Eta_Perc", color="Tecnologia", text_auto='.1f')
        fig2.update_layout(yaxis_title="Rendimento %")
        st.plotly_chart(fig2, use_container_width=True)

    c3, c4 = st.columns(2)
    with c3:
        st.subheader("3. Emissioni WtW [kg CO2/anno]")
        fig3 = px.bar(df_clean, x="Tecnologia", y="WtW_Annuo", color="Tecnologia")
        st.plotly_chart(fig3, use_container_width=True)
    with c4:
        st.subheader("4. Emissioni Totali LCA [t CO2]")
        fig4 = px.bar(df_clean, x="Tecnologia", y="Emiss_Tot_LCA", color="Tecnologia")
        st.plotly_chart(fig4, use_container_width=True)

    c5, c6 = st.columns(2)
    with c5:
        st.subheader("5. Costo Annuo (TCO/y) [€/anno]")
        df_plot_y = df_clean.melt(id_vars="Tecnologia", value_vars=['CAPEx_Annuo', 'Maint_Annuo', 'Fuel_Annuo'], 
                                  var_name="Voce", value_name="Euro")
        df_plot_y["Voce"] = df_plot_y["Voce"].replace({'CAPEx_Annuo':'CAPEx (Quota Acq.)', 'Maint_Annuo':'OPEx (Manut)', 'Fuel_Annuo':'OPEx (Vettore)'})
        fig5 = px.bar(df_plot_y, x="Tecnologia", y="Euro", color="Voce", barmode='stack',
                      color_discrete_sequence=["#0068C9", "#FFA421", "#FF4B4B"])
        st.plotly_chart(fig5, use_container_width=True)
        
    with c6:
        st.subheader("6. Costo Totale Vita (TCO) [€]")
        df_clean['CAPEx_Acquisto'] = df_clean['CAPEX_Totale']
        df_plot_tot = df_clean.melt(id_vars="Tecnologia", value_vars=['CAPEx_Acquisto', 'Maint_Tot', 'Fuel_Tot'], 
                                    var_name="Voce", value_name="Euro")
        df_plot_tot["Voce"] = df_plot_tot["Voce"].replace({'CAPEx_Acquisto':'CAPEx (Investimento)', 'Maint_Tot':'OPEx (Manut)', 'Fuel_Tot':'OPEx (Vettore)'})
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
    st.error(f"Errore tecnico: {e}")
