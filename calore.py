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
                "Emiss_Costruz_Tot": safe_num(df_raw, i + 42, 2), # C46 trascinata
                "Maint_Anno": safe_num(df_raw, i, 17),      
                "CAPEX_Raw": safe_num(df_raw, i, 19)     
            })
        except Exception:
            continue

    if not dati_finali:
        st.error("Nessun dato trovato.")
        st.stop()

    df_clean = pd.DataFrame(dati_finali)
    
    # ORDINE INVERSO: Gasolio prima, Idrogeno alla fine
    ordine_tecnologie = df_clean["Tecnologia"].tolist()[::-1]

    fabbisogno_base_excel = safe_num(df_raw, 17, 9) 
    lifetime_base_excel = safe_num(df_raw, 18, 9)   
    if fabbisogno_base_excel == 0: fabbisogno_base_excel = 150000
    if lifetime_base_excel == 0: lifetime_base_excel = 15

    # --- 3. SIDEBAR PARAMETRI ---
    st.sidebar.header("⚡ Costi e Parametri")
    costi_input_kwh = {} 
    
    for r in range(17, 25):
        label = safe_str(df_raw, r, 1)
        if label == "" or label.lower() == "nan": continue
        val_natura = safe_num(df_raw, r, 2)     
        val_kwh_excel = safe_num(df_raw, r, 5)  
        fattore = (val_kwh_excel / val_natura) if val_natura > 0 else 1.0
        user_val = st.sidebar.number_input(f"{label}", value=float(val_natura), format="%.3f")
        costi_input_kwh[label.lower()] = user_val * fattore

    user_cop_aria = st.sidebar.number_input("COP Pompa di Calore", value=float(safe_num(df_raw, 27, 2) or 3.2), step=0.1)
    user_fabbisogno = st.sidebar.slider("Fabbisogno Termico [kWh/y]", 2000, 500000, int(fabbisogno_base_excel), 1000)
    user_lifetime = st.sidebar.slider("Vita Utile (y)", 1, 30, int(lifetime_base_excel), 1)

    # --- 4. MOTORE MATEMATICO ---
    def calcola_riscaldamento(row):
        t_full = row["Tecnologia"].lower()
        
        # Selezione costo fuel
        p_fuel_kwh = 0.10
        if "gasolio" in t_full: p_fuel_kwh = costi_input_kwh.get("diesel", 0.18)
        elif "metano" in t_full: p_fuel_kwh = costi_input_kwh.get("metano", 0.10)
        elif "pellet" in t_full: p_fuel_kwh = costi_input_kwh.get("pellet", 0.06)
        elif "pdc" in t_full:
            p_fuel_kwh = costi_input_kwh.get("elettrico autoprodotto (pv)", 0.24) if ("auto" in t_full or "pv" in t_full) else costi_input_kwh.get("elettrico da rete", 0.31)
        elif "idrogeno" in t_full:
            if "verde" in t_full: p_fuel_kwh = costi_input_kwh.get("idrogeno verde autoprodotto", 0.45)
            elif "rete" in t_full: p_fuel_kwh = costi_input_kwh.get("idrogeno da rete", 0.60)
            else: p_fuel_kwh = costi_input_kwh.get("idrogeno grigio", 0.06)
        
        attivo_eta_cop = user_cop_aria if "pdc" in t_full else row["Eta_COP_Base"]
        if attivo_eta_cop == 0: attivo_eta_cop = 1.0 
        
        consumo_vettore_kwh = user_fabbisogno / attivo_eta_cop
        fattore_scala = consumo_vettore_kwh / row["Consumo_Base"] if row["Consumo_Base"] > 0 else 1.0
        
        # Emissioni (Logica Excel: F4 * G35 / H35 e C46 trascinato)
        wtt_annuo = consumo_vettore_kwh * (row["WtT_Base"] / row["Consumo_Base"] if row["Consumo_Base"] > 0 else 0)
        ttw_annuo = consumo_vettore_kwh * (row["TtW_Base"] / row["Consumo_Base"] if row["Consumo_Base"] > 0 else 0)
        costruz_annuo = row["Emiss_Costruz_Tot"] / user_lifetime   
        
        # Costi
        fuel_annuo = consumo_vettore_kwh * p_fuel_kwh
        maint_annuo = row["Maint_Anno"] 
        capex_annuo = row["CAPEX_Raw"] / user_lifetime
        
        return pd.Series([
            row["En_Prim_Base"] * fattore_scala, attivo_eta_cop, 
            wtt_annuo, ttw_annuo, costruz_annuo, wtt_annuo + ttw_annuo + costruz_annuo,
            fuel_annuo, maint_annuo, capex_annuo, fuel_annuo + maint_annuo + capex_annuo
        ])

    df_clean[['En_Primaria', 'Eta_Attiva', 'WtT_Annuo', 'TtW_Annuo', 'Costruz_Annuo', 'Emiss_Tot_Annue',
              'Fuel_Annuo', 'Maint_Annuo', 'CAPEx_Annuo', 'Costo_Annuo_Tot']] = df_clean.apply(calcola_riscaldamento, axis=1)

    # --- 5. GRAFICI ---
    st.divider()
    
    # 1. Energia Primaria
    st.subheader("1. Energia Primaria Richiesta [kWh/y]")
    fig1 = px.bar(df_clean, y="Tecnologia", x="En_Primaria", color="Tecnologia", orientation='h', category_orders={"Tecnologia": ordine_tecnologie})
    fig1.update_yaxes(autorange="reversed", title_text=""); fig1.update_layout(showlegend=False, height=400)
    st.plotly_chart(fig1, use_container_width=True)
    
    # 2. Efficienza
    st.subheader("2. Efficienza della Macchina (η / COP)")
    fig2 = px.bar(df_clean, y="Tecnologia", x="Eta_Attiva", color="Tecnologia", orientation='h', text_auto='.2f', category_orders={"Tecnologia": ordine_tecnologie})
    fig2.update_yaxes(autorange="reversed", title_text=""); fig2.update_layout(showlegend=False, height=400)
    st.plotly_chart(fig2, use_container_width=True)

    # 3. Emissioni
    st.subheader(f"3. Impronta Carbonica ANNUA [kg CO2/y] (costruzione spalmata in {user_lifetime} anni)")
    df_em = df_clean.melt(id_vars="Tecnologia", value_vars=['WtT_Annuo', 'TtW_Annuo', 'Costruz_Annuo'], var_name="Fase", value_name="E")
    df_em["Fase"] = df_em["Fase"].replace({'WtT_Annuo': 'WtT (Filiera)', 'TtW_Annuo': 'TtW (Camino)', 'Costruz_Annuo': f'Costruzione (spalmata in {user_lifetime} y)'})
    fig3 = px.bar(df_em, y="Tecnologia", x="E", color="Fase", orientation='h', barmode='stack', category_orders={"Tecnologia": ordine_tecnologie}, color_discrete_sequence=["#8B4513", "#CD5C5C", "#A9A9A9"])
    fig3.update_yaxes(autorange="reversed", title_text=""); fig3.update_layout(height=450, legend=dict(orientation="h", y=1.05))
    st.plotly_chart(fig3, use_container_width=True)
    
    # 4. Costo
    st.subheader(f"4. Costo ANNUO (TCO/y) [€/y] (acquisto spalmato in {user_lifetime} anni)")
    df_c = df_clean.melt(id_vars="Tecnologia", value_vars=['CAPEx_Annuo', 'Maint_Annuo', 'Fuel_Annuo'], var_name="V", value_name="Eur")
    df_c["V"] = df_c["V"].replace({'CAPEx_Annuo': f'CAPEx (spalmato in {user_lifetime} y)', 'Maint_Annuo': 'Manutenzione', 'Fuel_Annuo': 'Vettore Energetico'})
    fig4 = px.bar(df_c, y="Tecnologia", x="Eur", color="V", orientation='h', barmode='stack', category_orders={"Tecnologia": ordine_tecnologie}, color_discrete_sequence=["#0068C9", "#FFA421", "#FF4B4B"])
    fig4.update_yaxes(autorange="reversed", title_text=""); fig4.update_layout(height=450, legend=dict(orientation="h", y=1.05))
    st.plotly_chart(fig4, use_container_width=True)

    # Tabella
    st.subheader("📋 Riepilogo Dati")
    st.dataframe(df_clean[["Tecnologia", "En_Primaria", "Eta_Attiva", "Emiss_Tot_Annue", "Costo_Annuo_Tot"]].style.format({"En_Primaria": "{:,.0f}", "Eta_Attiva": "{:.2f}", "Emiss_Tot_Annue": "{:,.0f}", "Costo_Annuo_Tot": "€ {:,.0f}"}), use_container_width=True)

except Exception as e:
    st.error(f"Errore: {e}")
