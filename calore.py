import streamlit as st
import pandas as pd
import plotly.express as px
import os

# --- CONFIGURAZIONE PAGINA ---
st.set_page_config(page_title="DSS Comuni: Riscaldamento", page_icon="🔥", layout="wide")
st.title("🔥 DSS Comuni: Analisi Sistemi di Riscaldamento")

if os.path.exists("ReadMe_calore.md"):
    with st.expander("ℹ️ Leggi Istruzioni, Limiti e Assunzioni"):
        with open("ReadMe_calore.md", "r", encoding="utf-8") as f:
            st.markdown(f.read())

NOME_FILE_EXCEL = "Comparison H2 elc FF.xlsx" 

if not os.path.exists(NOME_FILE_EXCEL):
    st.error(f"❌ File '{NOME_FILE_EXCEL}' non trovato nel repository GitHub.")
    st.stop()

try:
    xl = pd.ExcelFile(NOME_FILE_EXCEL, engine='openpyxl')
    
    # 1. SELEZIONE AUTOMATICA DEL FOGLIO
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
            
        if "geotermica" in nome_tec.lower() or "joule" in nome_tec.lower() or "riscaldamento elettrico" in nome_tec.lower():
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
                "WtT_Base": safe_num(df_raw, i, 9),         
                "TtW_Base": safe_num(df_raw, i, 10),        
                "WtW_Base": safe_num(df_raw, i, 11),        
                "Emiss_Costruz": safe_num(df_raw, i + 42, 2), 
                "Maint_Anno": safe_num(df_raw, i, 17),      
                "CAPEX_Raw": safe_num(df_raw, i, 19)     
            })
        except Exception:
            continue

    if not dati_finali:
        st.error("Nessun dato trovato per il riscaldamento.")
        st.stop()

    df_clean = pd.DataFrame(dati_finali)
    ordine_tecnologie = df_clean["Tecnologia"].tolist()

    fabbisogno_base_excel = safe_num(df_raw, 17, 9) 
    lifetime_base_excel = safe_num(df_raw, 18, 9)   
    if fabbisogno_base_excel == 0: fabbisogno_base_excel = 150000
    if lifetime_base_excel == 0: lifetime_base_excel = 15

    # --- 3. LETTURA COSTI E PARAMETRI ---
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
        label = safe_str(df_raw, r, 1)
        if label == "" or label.lower() == "nan": continue
        try:
            val_natura = safe_num(df_raw, r, 2)     
            val_kwh_excel = safe_num(df_raw, r, 5)  
            fattore = (val_kwh_excel / val_natura) if val_natura > 0 else 1.0
            etichetta_ui = f"{label} {get_unit_heat(label)}"
            user_val = st.sidebar.number_input(etichetta_ui, value=float(val_natura), format="%.3f", step=0.05)
            costi_input_kwh[label.lower()] = user_val * fattore
        except:
            pass

    st.sidebar.divider()
    st.sidebar.header("🌡️ Rendimento Macchina")
    
    cop_aria_def = safe_num(df_raw, 27, 2)
    if cop_aria_def == 0: cop_aria_def = 3.2
    user_cop_aria = st.sidebar.number_input("COP Pompa di Calore", value=float(cop_aria_def), step=0.1)

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

    # --- 4. MOTORE MATEMATICO ---
    def calcola_riscaldamento(row):
        t_full = row["Tecnologia"].lower()
        
        p_fuel_kwh = 0.10
        if "gasolio" in t_full: p_fuel_kwh = costi_input_kwh.get("diesel", 0.18)
        elif "metano" in t_full: p_fuel_kwh = costi_input_kwh.get("metano", 0.10)
        elif "pellet" in t_full: p_fuel_kwh = costi_input_kwh.get("pellet", 0.06)
        elif "pdc" in t_full:
            if "auto" in t_full or "pv" in t_full: p_fuel_kwh = costi_input_kwh.get("elettrico autoprodotto (pv)", 0.24)
            else: p_fuel_kwh = costi_input_kwh.get("elettrico da rete", 0.31)
        elif "idrogeno" in t_full:
            if "grigio" in t_full: p_fuel_kwh = costi_input_kwh.get("idrogeno grigio", 0.06)
            elif "rete" in t_full: p_fuel_kwh = costi_input_kwh.get("idrogeno da rete", 0.60)
            elif "verde" in t_full or "auto" in t_full: p_fuel_kwh = costi_input_kwh.get("idrogeno verde autoprodotto", 0.45)
            else: p_fuel_kwh = costi_input_kwh.get("idrogeno grigio", 0.06)
        
        attivo_eta_cop = row["Eta_COP_Base"]
        if "pdc" in t_full: attivo_eta_cop = user_cop_aria
        if attivo_eta_cop == 0: attivo_eta_cop = 1.0 
        
        consumo_vettore_kwh = user_fabbisogno / attivo_eta_cop
        fattore_scala = consumo_vettore_kwh / row["Consumo_Base"] if row["Consumo_Base"] > 0 else 1.0
        
        en_primaria = row["En_Prim_Base"] * fattore_scala
        
        # Fattori di emissione
        fattore_wtt = row["WtT_Base"] / row["Consumo_Base"] if row["Consumo_Base"] > 0 else 0.0
        fattore_ttw = row["TtW_Base"] / row["Consumo_Base"] if row["Consumo_Base"] > 0 else 0.0
        
        # Dati ANNUALI
        wtt_annuo = consumo_vettore_kwh * fattore_wtt          
        ttw_annuo = consumo_vettore_kwh * fattore_ttw          
        wtw_annuo = wtt_annuo + ttw_annuo                      
        costruz_annuo = row["Emiss_Costruz"] / user_lifetime   
        emiss_totali_annue = wtw_annuo + costruz_annuo
        
        fuel_annuo = consumo_vettore_kwh * p_fuel_kwh
        maint_annuo = row["Maint_Anno"] 
        capex_annuo = row["CAPEX_Raw"] / user_lifetime
        costo_annuo_tot = fuel_annuo + maint_annuo + capex_annuo

        # Dati SULLA VITA UTILE (TOTALI)
        costruz_totale = row["Emiss_Costruz"]
        wtt_totale = wtt_annuo * user_lifetime
        ttw_totale = ttw_annuo * user_lifetime
        emiss_vita_intera = wtt_totale + ttw_totale + costruz_totale

        capex_totale_assoluto = row["CAPEX_Raw"]
        fuel_totale = fuel_annuo * user_lifetime
        maint_totale = maint_annuo * user_lifetime
        costo_vita_intera = fuel_totale + maint_totale + capex_totale_assoluto
        
        return pd.Series([
            en_primaria, attivo_eta_cop, 
            wtt_annuo, ttw_annuo, wtw_annuo, costruz_annuo, emiss_totali_annue,
            fuel_annuo, maint_annuo, capex_annuo, costo_annuo_tot,
            wtt_totale, ttw_totale, costruz_totale, emiss_vita_intera,
            fuel_totale, maint_totale, capex_totale_assoluto, costo_vita_intera
        ])

    df_clean[['En_Primaria', 'Eta_Attiva', 
              'WtT_Annuo', 'TtW_Annuo', 'WtW_Annuo', 'Costruz_Annuo', 'Emiss_Totali_Annue',
              'Fuel_Annuo', 'Maint_Annuo', 'CAPEx_Annuo', 'Costo_Annuo_Tot',
              'WtT_Totale', 'TtW_Totale', 'Costruz_Totale', 'Emiss_Vita_Intera',
              'Fuel_Totale', 'Maint_Totale', 'CAPEx_Tot_Assoluto', 'Costo_Vita_Intera']] = df_clean.apply(calcola_riscaldamento, axis=1)

    # --- 5. VISUALIZZAZIONE RISULTATI ---
    st.divider()
    
    # 1. Energia Primaria
    st.subheader("1. Energia Primaria Richiesta [kWh/y]")
    fig1 = px.bar(df_clean, y="Tecnologia", x="En_Primaria", color="Tecnologia", orientation='h', 
                  category_orders={"Tecnologia": ordine_tecnologie})
    fig1.update_yaxes(autorange="reversed", title_text="")
    fig1.update_layout(showlegend=False, height=400)
    st.plotly_chart(fig1, use_container_width=True)
    
    # 2. Efficienza
    st.subheader("2. Efficienza della Macchina (η / COP)")
    fig2 = px.bar(df_clean, y="Tecnologia", x="Eta_Attiva", color="Tecnologia", orientation='h', text_auto='.2f',
                  category_orders={"Tecnologia": ordine_tecnologie})
    fig2.update_yaxes(autorange="reversed", title_text="")
    fig2.update_layout(xaxis_title="Valore Assoluto (η o COP)", showlegend=False, height=400)
    st.plotly_chart(fig2, use_container_width=True)

    # 3. Emissioni ANNUE
    st.subheader("3. Impronta Carbonica ANNUA [kg CO2/y]")
    df_plot_emiss_annue = df_clean.melt(id_vars="Tecnologia", value_vars=['WtT_Annuo', 'TtW_Annuo', 'Costruz_Annuo'], 
                                  var_name="Fase", value_name="Emissioni")
    df_plot_emiss_annue["Fase"] = df_plot_emiss_annue["Fase"].replace({
        'WtT_Annuo': 'WtT (Estrazione e Trasporto)', 
        'TtW_Annuo': 'TtW (Combustione Locale)',
        'Costruz_Annuo': 'Costruzione Impianto (Quota Annua)'
    })
    fig3 = px.bar(df_plot_emiss_annue, y="Tecnologia", x="Emissioni", color="Fase", orientation='h', barmode='stack',
                  color_discrete_sequence=["#8B4513", "#CD5C5C", "#A9A9A9"],
                  category_orders={"Tecnologia": ordine_tecnologie})
    fig3.update_yaxes(autorange="reversed", title_text="")
    fig3.update_layout(height=450, legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1))
    st.plotly_chart(fig3, use_container_width=True)
    
    # 4. Costo ANNUO
    st.subheader("4. Costo ANNUO (TCO/y) [€/y]")
    df_plot_y_annuo = df_clean.melt(id_vars="Tecnologia", value_vars=['CAPEx_Annuo', 'Maint_Annuo', 'Fuel_Annuo'], 
                                  var_name="Voce", value_name="Euro")
    df_plot_y_annuo["Voce"] = df_plot_y_annuo["Voce"].replace({'CAPEx_Annuo':'CAPEx (Quota Acq.)', 'Maint_Annuo':'OPEx (Manut)', 'Fuel_Annuo':'OPEx (Vettore)'})
    fig4 = px.bar(df_plot_y_annuo, y="Tecnologia", x="Euro", color="Voce", orientation='h', barmode='stack',
                  color_discrete_sequence=["#0068C9", "#FFA421", "#FF4B4B"],
                  category_orders={"Tecnologia": ordine_tecnologie})
    fig4.update_yaxes(autorange="reversed", title_text="")
    fig4.update_layout(height=450, legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1))
    st.plotly_chart(fig4, use_container_width=True)

    # 5. Emissioni TOTALI
    st.subheader(f"5. Impronta Carbonica TOTALE (su {user_lifetime} anni) [kg CO2]")
    df_plot_emiss_tot = df_clean.melt(id_vars="Tecnologia", value_vars=['WtT_Totale', 'TtW_Totale', 'Costruz_Totale'], 
                                  var_name="Fase", value_name="Emissioni")
    df_plot_emiss_tot["Fase"] = df_plot_emiss_tot["Fase"].replace({
        'WtT_Totale': 'WtT (Estrazione e Trasporto Tot)', 
        'TtW_Totale': 'TtW (Combustione Locale Tot)',
        'Costruz_Totale': 'Costruzione Impianto (Assoluta)'
    })
    fig5 = px.bar(df_plot_emiss_tot, y="Tecnologia", x="Emissioni", color="Fase", orientation='h', barmode='stack',
                  color_discrete_sequence=["#5C3317", "#8B0000", "#696969"], # Colori leggermente più scuri per distinguere dai totali annui
                  category_orders={"Tecnologia": ordine_tecnologie})
    fig5.update_yaxes(autorange="reversed", title_text="")
    fig5.update_layout(height=450, legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1))
    st.plotly_chart(fig5, use_container_width=True)

    # 6. Costo TOTALE
    st.subheader(f"6. Costo TOTALE (TCO su {user_lifetime} anni) [€]")
    df_plot_y_tot = df_clean.melt(id_vars="Tecnologia", value_vars=['CAPEx_Tot_Assoluto', 'Maint_Totale', 'Fuel_Totale'], 
                                  var_name="Voce", value_name="Euro")
    df_plot_y_tot["Voce"] = df_plot_y_tot["Voce"].replace({'CAPEx_Tot_Assoluto':'CAPEx (Acquisto Impianto)', 'Maint_Totale':'OPEx (Manutenzione Tot)', 'Fuel_Totale':'OPEx (Vettore Tot)'})
    fig6 = px.bar(df_plot_y_tot, y="Tecnologia", x="Euro", color="Voce", orientation='h', barmode='stack',
                  color_discrete_sequence=["#004B8D", "#CC7A00", "#B22222"], # Colori leggermente più scuri
                  category_orders={"Tecnologia": ordine_tecnologie})
    fig6.update_yaxes(autorange="reversed", title_text="")
    fig6.update_layout(height=450, legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1))
    st.plotly_chart(fig6, use_container_width=True)

    # --- TABELLA RIASSUNTIVA PULITA ---
    st.subheader("📋 Tabella Dati Analitici")
    st.dataframe(df_clean[["Tecnologia", "En_Primaria", "Eta_Attiva", "Emiss_Totali_Annue", "Costo_Annuo_Tot", "Emiss_Vita_Intera", "Costo_Vita_Intera"]].style.format({
        "En_Primaria": "{:,.0f} kWh/y",
        "Eta_Attiva": "{:.2f}",
        "Emiss_Totali_Annue": "{:,.0f} kg/y",
        "Costo_Annuo_Tot": "€ {:,.0f}/y",
        "Emiss_Vita_Intera": "{:,.0f} kg",
        "Costo_Vita_Intera": "€ {:,.0f}"
    }), use_container_width=True)

except Exception as e:
    st.error(f"Errore tecnico: {e}")
