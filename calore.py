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
    
    # 1. SELEZIONE AUTOMATICA DEL FOGLIO (INVISIBILE)
    fogli_disponibili = xl.sheet_names
    nome_foglio = next((f for f in fogli_disponibili if "riscaldam" in f.lower() or "edifici" in f.lower() or "calore" in f.lower()), fogli_disponibili[0])
    
    df_raw = pd.read_excel(xl, sheet_name=nome_foglio, header=None, engine='openpyxl')

    # --- FUNZIONI SCUDO ---
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

    # --- 2. ESTRAZIONE DATI BASE ---
    dati_finali = []
    
    for i in range(3, 15):
        nome_tec = safe_str(df_raw, i, 1) 
        vettore = safe_str(df_raw, i, 4)  
        
        if nome_tec == "" or nome_tec.lower() == "nan": 
            continue
        
        tec_base = nome_tec
        if "Aria-H2O" in tec_base:
            tec_base = tec_base.replace("Aria-H2O", "").strip()
            if tec_base == "PdC": tec_base = "Pompa di Calore (PdC)"
            
        if vettore and vettore.lower() != "nan":
            nome_display = f"{tec_base} [{vettore}]"
        else:
            nome_display = tec_base
            
        try:
            dati_finali.append({
                "Tecnologia": nome_display,                 
                "Tec_Originale": nome_tec,                  
                "Eta_COP_Base": safe_num(df_raw, i, 3),     
                "Consumo_Base": safe_num(df_raw, i, 5),     
                "En_Prim_Base": safe_num(df_raw, i, 7),     
                "Eta_Processo": safe_num(df_raw, i, 8),     
                "WtW_Base": safe_num(df_raw, i, 11),        
                "Emiss_Costruz": safe_num(df_raw, i, 12),   
                "Maint_Anno": safe_num(df_raw, i, 17),      
                "CAPEX_Totale": safe_num(df_raw, i, 19)     
            })
        except Exception:
            continue

    if not dati_finali:
        st.error("Nessun dato trovato per il riscaldamento. Verifica le righe 4-15.")
        st.stop()

    df_clean = pd.DataFrame(dati_finali)

    fabbisogno_base_excel = safe_num(df_raw, 17, 9) 
    lifetime_base_excel = safe_num(df_raw, 18, 9)   
    if fabbisogno_base_excel == 0: fabbisogno_base_excel = 150000
    if lifetime_base_excel == 0: lifetime_base_excel = 15

    # --- 3. LETTURA COSTI COMBUSTIBILE E COP ---
    st.sidebar.header("⚡ Costi Vettore Energetico")
    
    costi_input_kwh = {} 
    etichette_costi_letti = {} 
    
    def get_unit_heat(t):
        t_low = t.lower()
        if "diesel" in t_low or "gasolio" in t_low: return "[€/l]"
        if "pellet" in t_low: return "[€/sacco]"
        if "metano" in t_low: return "[€/Sm3]"
        if "idrogeno" in t_low: return "[€/kg]"
        return "[€/kWh]"

    for r in range(17, 25):
        label = safe_str(df_raw, r, 1)
        if label == "" or label.lower() == "nan": continue
        try:
            val_natura = safe_num(df_raw, r, 2)     
            val_kwh_excel = safe_num(df_raw, r, 5)  
            fattore = (val_kwh_excel / val_natura) if val_natura > 0 else 1.0
            etichetta_ui = f"{label} {get_unit_heat(label)}"
            user_val = st.sidebar.number_input(etichetta_ui, value=float(val_natura), format="%.3f", step=0.05)
            
            costi_input_kwh[label.lower()] = user_val * fattore
            etichette_costi_letti[label.lower()] = label
        except:
            pass

    st.sidebar.divider()
    st.sidebar.header("🌡️ Rendimenti PdC (COP)")
    
    cop_aria_def = safe_num(df_raw, 27, 2)
    if cop_aria_def == 0: cop_aria_def = 3.2
    cop_geo_def = safe_num(df_raw, 28, 2)
    if cop_geo_def == 0: cop_geo_def = 4.5
    
    user_cop_aria = st.sidebar.number_input("COP PdC Aria-H2O", value=float(cop_aria_def), step=0.1)
    user_cop_geo = st.sidebar.number_input("COP PdC Geotermica", value=float(cop_geo_def), step=0.1)

    st.sidebar.divider()
    st.sidebar.header("⚙️ Parametri Edificio")
    
    user_fabbisogno = st.sidebar.slider(
        "Fabbisogno Termico [kWh_th/y]", 
        min_value=2000, max_value=500000, value=int(max(2000, fabbisogno_base_excel)), step=1000
    )
    user_lifetime = st.sidebar.slider(
        "Vita Utile Impianto (y)", 
        min_value=1, max_value=30, value=int(max(1, lifetime_base_excel)), step=1
    )

    # --- 4. MOTORE MATEMATICO (Alleggerito dai totali LCA/Lifetime) ---
    def calcola_riscaldamento(row):
        t_full = row["Tecnologia"].lower()
        
        p_fuel_kwh = 0.10
        if "gasolio" in t_full: p_fuel_kwh = costi_input_kwh.get("diesel", 0.18)
        elif "metano" in t_full: p_fuel_kwh = costi_input_kwh.get("metano", 0.10)
        elif "pellet" in t_full: p_fuel_kwh = costi_input_kwh.get("pellet", 0.06)
        elif "elettrico" in t_full or "joule" in t_full or "pdc" in t_full or "geotermica" in t_full:
            if "auto" in t_full or "pv" in t_full: p_fuel_kwh = costi_input_kwh.get("elettrico autoprodotto (pv)", 0.24)
            else: p_fuel_kwh = costi_input_kwh.get("elettrico da rete", 0.31)
        elif "idrogeno" in t_full:
            if "grigio" in t_full: p_fuel_kwh = costi_input_kwh.get("idrogeno grigio", 0.06)
            elif "rete" in t_full: p_fuel_kwh = costi_input_kwh.get("idrogeno da rete", 0.60)
            elif "verde" in t_full or "auto" in t_full: p_fuel_kwh = costi_input_kwh.get("idrogeno verde autoprodotto", 0.45)
            else: p_fuel_kwh = costi_input_kwh.get("idrogeno grigio", 0.06)
        
        attivo_eta_cop = row["Eta_COP_Base"]
        if "aria-h2o" in row["Tec_Originale"].lower() or ("pdc" in t_full and "geo" not in t_full): attivo_eta_cop = user_cop_aria
        elif "geotermica" in t_full or "geo" in t_full: attivo_eta_cop = user_cop_geo
        if attivo_eta_cop == 0: attivo_eta_cop = 1.0 
        
        consumo_vettore_kwh = user_fabbisogno / attivo_eta_cop
        fattore_scala = consumo_vettore_kwh / row["Consumo_Base"] if row["Consumo_Base"] > 0 else 1.0
        
        en_primaria = row["En_Prim_Base"] * fattore_scala
        wtw_annuo = row["WtW_Base"] * fattore_scala
        
        fuel_annuo = consumo_vettore_kwh * p_fuel_kwh
        maint_annuo = row["Maint_Anno"] 
        capex_annuo = row["CAPEX_Totale"] / user_lifetime
        costo_annuo_tot = fuel_annuo + maint_annuo + capex_annuo
        
        return pd.Series([
            en_primaria, row["Eta_Processo"], wtw_annuo,
            fuel_annuo, maint_annuo, capex_annuo, costo_annuo_tot
        ])

    df_clean[['En_Primaria', 'Eta_Proc', 'WtW_Annuo',
              'Fuel_Annuo', 'Maint_Annuo', 'CAPEx_Annuo', 'Costo_Annuo_Tot']] = df_clean.apply(calcola_riscaldamento, axis=1)

    # --- 5. VISUALIZZAZIONE RISULTATI (4 GRAFICI ORIZZONTALI) ---
    st.divider()
    
    # RIGA 1: Energia e Rendimento
    c1, c2 = st.columns(2)
    with c1:
        st.subheader("1. Energia Primaria Richiesta [kWh/y]")
        # GRAFICO ORIZZONTALE (orientation='h')
        fig1 = px.bar(df_clean, y="Tecnologia", x="En_Primaria", color="Tecnologia", orientation='h')
        # Invertiamo l'asse Y per leggere dall'alto verso il basso e nascondiamo i titoli superflui
        fig1.update_yaxes(autorange="reversed", title_text="")
        fig1.update_layout(showlegend=False, height=500)
        st.plotly_chart(fig1, use_container_width=True)
        
    with c2:
        st.subheader("2. Efficienza di Processo (η)")
        df_clean["Eta_Perc"] = df_clean["Eta_Proc"] * 100 if df_clean["Eta_Proc"].mean() < 6 else df_clean["Eta_Proc"]
        fig2 = px.bar(df_clean, y="Tecnologia", x="Eta_Perc", color="Tecnologia", orientation='h', text_auto='.1f')
        fig2.update_yaxes(autorange="reversed", title_text="")
        fig2.update_layout(xaxis_title="Rendimento %", showlegend=False, height=500)
        st.plotly_chart(fig2, use_container_width=True)

    # RIGA 2: Emissioni e Costi
    c3, c4 = st.columns(2)
    with c3:
        st.subheader("3. Emissioni WtW [kg CO2/anno]")
        fig3 = px.bar(df_clean, y="Tecnologia", x="WtW_Annuo", color="Tecnologia", orientation='h')
        fig3.update_yaxes(autorange="reversed", title_text="")
        fig3.update_layout(showlegend=False, height=500)
        st.plotly_chart(fig3, use_container_width=True)
        
    with c4:
        st.subheader("4. Costo Annuo (TCO/y) [€/anno]")
        df_plot_y = df_clean.melt(id_vars="Tecnologia", value_vars=['CAPEx_Annuo', 'Maint_Annuo', 'Fuel_Annuo'], 
                                  var_name="Voce", value_name="Euro")
        df_plot_y["Voce"] = df_plot_y["Voce"].replace({'CAPEx_Annuo':'CAPEx (Quota Acq.)', 'Maint_Annuo':'OPEx (Manut)', 'Fuel_Annuo':'OPEx (Vettore)'})
        
        # Stacked bar orizzontale
        fig4 = px.bar(df_plot_y, y="Tecnologia", x="Euro", color="Voce", orientation='h', barmode='stack',
                      color_discrete_sequence=["#0068C9", "#FFA421", "#FF4B4B"])
        fig4.update_yaxes(autorange="reversed", title_text="")
        fig4.update_layout(height=500, legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1))
        st.plotly_chart(fig4, use_container_width=True)

    # --- TABELLA RIASSUNTIVA PULITA ---
    st.subheader("📋 Tabella Dati Analitici")
    st.dataframe(df_clean[["Tecnologia", "En_Primaria", "Eta_Perc", "WtW_Annuo", "Costo_Annuo_Tot"]].style.format({
        "En_Primaria": "{:,.0f} kWh",
        "Eta_Perc": "{:.1f} %",
        "WtW_Annuo": "{:,.0f} kg",
        "Costo_Annuo_Tot": "€ {:,.0f}"
    }), use_container_width=True)

except Exception as e:
    st.error(f"Errore tecnico: {e}")
