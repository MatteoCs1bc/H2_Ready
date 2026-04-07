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
    
    fogli_disponibili = xl.sheet_names
    nome_foglio = next((f for f in fogli_disponibili if "riscaldam" in f.lower() or "edifici" in f.lower() or "calore" in f.lower()), fogli_disponibili[0])
    
    df_raw = pd.read_excel(xl, sheet_name=nome_foglio, header=None, engine='openpyxl')

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

    # --- MAPPATURA DINAMICA EMISSIONI COSTRUZIONE ---
    emiss_costruz_excel = {}
    for r in range(30, 100):
        nome_riga = safe_str(df_raw, r, 0).lower()
        if not nome_riga: nome_riga = safe_str(df_raw, r, 1).lower()
        if nome_riga and ("caldaia" in nome_riga or "stufa" in nome_riga or "pompa" in nome_riga or "riscaldamento" in nome_riga):
            val = safe_num(df_raw, r, 1)
            if val == 0: val = safe_num(df_raw, r, 2)
            if val > 0: emiss_costruz_excel[nome_riga] = val

    def trova_emissioni_costruzione(nome_tecnologia, indice_riga):
        t_low = nome_tecnologia.lower().strip()
        t_low_alt = t_low.replace("aria-h2o", "aria-acqua").replace("pdc", "pompa di calore")
        for chiave_excel, valore in emiss_costruz_excel.items():
            if t_low_alt in chiave_excel or chiave_excel in t_low_alt: return valore
        return safe_num(df_raw, indice_riga + 42, 2)

    # --- ESTRAZIONE DATI BASE ---
    dati_finali = []
    
    for i in range(3, 15):
        nome_tec = safe_str(df_raw, i, 1) 
        vettore = safe_str(df_raw, i, 4)  
        
        if nome_tec == "" or nome_tec.lower() == "nan": continue
        if "geotermica" in nome_tec.lower() or "joule" in nome_tec.lower() or "riscaldamento elettrico" in nome_tec.lower(): continue
        
        tec_base = nome_tec
        if "Aria-H2O" in tec_base:
            tec_base = tec_base.replace("Aria-H2O", "").strip()
            if tec_base == "PdC": tec_base = "Pompa di Calore (PdC)"
            
        nome_display = f"{tec_base} [{vettore}]" if vettore and vettore.lower() != "nan" else tec_base
            
        try:
            dati_finali.append({
                "Tecnologia": nome_display,                 
                "Eta_COP_Base": safe_num(df_raw, i, 3),     
                "Consumo_Base": safe_num(df_raw, i, 5),     
                "En_Prim_Base": safe_num(df_raw, i, 7),
                "WtT_Base": safe_num(df_raw, i, 9),         
                "TtW_Base": safe_num(df_raw, i, 10),        
                "Emiss_Costruz_Tot": trova_emissioni_costruzione(nome_tec, i), 
                "Maint_Anno": safe_num(df_raw, i, 17),      
                "CAPEX_Raw": safe_num(df_raw, i, 19)     
            })
        except Exception:
            continue

    if not dati_finali:
        st.error("Nessun dato trovato.")
        st.stop()

    df_clean = pd.DataFrame(dati_finali)
    ordine_tecnologie = df_clean["Tecnologia"].tolist()[::-1]

    # --- LETTURA DEFAULT E PARAMETRI ---
    # Corretti i Default per farli corrispondere al tuo foglio Excel!
    fabbisogno_base_excel = safe_num(df_raw, 17, 9) 
    if fabbisogno_base_excel == 0: fabbisogno_base_excel = 10000 # Era 150000!
    
    lifetime_base_excel = safe_num(df_raw, 18, 9)   
    if lifetime_base_excel == 0: lifetime_base_excel = 20 # Era 15!

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
    user_fabbisogno = st.sidebar.slider("Fabbisogno Termico [kWh/y]", 2000, 50000, int(fabbisogno_base_excel), 1000)
    user_lifetime = st.sidebar.slider("Vita Utile (y)", 1, 30, int(lifetime_base_excel), 1)

    # --- MOTORE MATEMATICO ---
    def calcola_riscaldamento(row):
        t_full = row["Tecnologia"].lower()
        
        # Ricerca robusta dei prezzi carburante
        p_fuel_kwh = 0.10
        if "gasolio" in t_full: 
            p_fuel_kwh = next((v for k, v in costi_input_kwh.items() if "gasolio" in k or "diesel" in k), 0.18)
        elif "metano" in t_full: 
            p_fuel_kwh = next((v for k, v in costi_input_kwh.items() if "metano" in k or "naturale" in k), 0.10)
        elif "pellet" in t_full: 
            p_fuel_kwh = next((v for k, v in costi_input_kwh.items() if "pellet" in k or "biomassa" in k), 0.06)
        elif "pdc" in t_full or "elettrico" in t_full:
            if "auto" in t_full or "pv" in t_full: 
                p_fuel_kwh = next((v for k, v in costi_input_kwh.items() if "auto" in k or "pv" in k), 0.24)
            else: 
                p_fuel_kwh = next((v for k, v in costi_input_kwh.items() if "rete" in k), 0.31)
        elif "idrogeno" in t_full:
            if "verde" in t_full and "auto" in t_full: 
                p_fuel_kwh = next((v for k, v in costi_input_kwh.items() if "idrogeno" in k and "auto" in k), 0.45)
            elif "rete" in t_full or "verde" in t_full: 
                p_fuel_kwh = next((v for k, v in costi_input_kwh.items() if "idrogeno" in k and "rete" in k), 0.60)
            else: 
                p_fuel_kwh = next((v for k, v in costi_input_kwh.items() if "idrogeno" in k and "grigio" in k), 0.06)
        
        attivo_eta_cop = user_cop_aria if "pdc" in t_full else row["Eta_COP_Base"]
        if attivo_eta_cop == 0: attivo_eta_cop = 1.0 
        
        consumo_vettore_kwh = user_fabbisogno / attivo_eta_cop
        fattore_scala = consumo_vettore_kwh / row["Consumo_Base"] if row["Consumo_Base"] > 0 else 1.0
        
        wtt_annuo = consumo_vettore_kwh * (row["WtT_Base"] / row["Consumo_Base"] if row["Consumo_Base"] > 0 else 0)
        ttw_annuo = consumo_vettore_kwh * (row["TtW_Base"] / row["Consumo_Base"] if row["Consumo_Base"] > 0 else 0)
        costruz_annuo = row["Emiss_Costruz_Tot"] / user_lifetime   
        
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

    # --- GRAFICI ---
    st.divider()
    
    st.subheader(f"1. Energia Primaria Richiesta per soddisfare il fabbisogno pari a {user_fabbisogno} [kWh/y]")
    fig1 = px.bar(df_clean, y="Tecnologia", x="En_Primaria", color="Tecnologia", orientation='h', category_orders={"Tecnologia": ordine_tecnologie})
    fig1.update_yaxes(autorange="reversed", title_text=""); fig1.update_xaxes(title_text="")
    fig1.update_layout(showlegend=False, height=400)
    st.plotly_chart(fig1, use_container_width=True)
    
    st.subheader("2. Efficienza della Macchina (η / COP)")
    fig2 = px.bar(df_clean, y="Tecnologia", x="Eta_Attiva", color="Tecnologia", orientation='h', text_auto='.2f', category_orders={"Tecnologia": ordine_tecnologie})
    fig2.update_yaxes(autorange="reversed", title_text=""); fig2.update_xaxes(title_text="")
    fig2.update_layout(showlegend=False, height=400)
    st.plotly_chart(fig2, use_container_width=True)

    st.subheader(f"3. Impronta Carbonica ANNUA [kg CO2/y] (costruzione spalmata in {user_lifetime} anni)")
    df_em = df_clean.melt(id_vars="Tecnologia", value_vars=['WtT_Annuo', 'TtW_Annuo', 'Costruz_Annuo'], var_name="Fase", value_name="E")
    df_em["Fase"] = df_em["Fase"].replace({'WtT_Annuo': 'WtT (Filiera)', 'TtW_Annuo': 'TtW (Camino)', 'Costruz_Annuo': f'Costruzione (spalmata in {user_lifetime} y)'})
    fig3 = px.bar(df_em, y="Tecnologia", x="E", color="Fase", orientation='h', barmode='stack', category_orders={"Tecnologia": ordine_tecnologie}, color_discrete_sequence=["#8B4513", "#CD5C5C", "#A9A9A9"])
    fig3.update_yaxes(autorange="reversed", title_text=""); fig3.update_xaxes(title_text="")
    fig3.update_layout(height=450, legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="center", x=0.5, title_text=""))
    st.plotly_chart(fig3, use_container_width=True)
    
    st.subheader(f"4. Costo ANNUO (TCO/y) [€/y] (acquisto spalmato in {user_lifetime} anni)")
    df_c = df_clean.melt(id_vars="Tecnologia", value_vars=['CAPEx_Annuo', 'Maint_Annuo', 'Fuel_Annuo'], var_name="V", value_name="Eur")
    df_c["V"] = df_c["V"].replace({'CAPEx_Annuo': f'CAPEx (spalmato in {user_lifetime} y)', 'Maint_Annuo': 'Manutenzione', 'Fuel_Annuo': 'Vettore Energetico'})
    fig4 = px.bar(df_c, y="Tecnologia", x="Eur", color="V", orientation='h', barmode='stack', category_orders={"Tecnologia": ordine_tecnologie}, color_discrete_sequence=["#0068C9", "#FFA421", "#FF4B4B"])
    fig4.update_yaxes(autorange="reversed", title_text=""); fig4.update_xaxes(title_text="")
    fig4.update_layout(height=450, legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="center", x=0.5, title_text=""))
    st.plotly_chart(fig4, use_container_width=True)

    st.subheader("📋 Riepilogo Dati")
    st.dataframe(df_clean[["Tecnologia", "En_Primaria", "Eta_Attiva", "Emiss_Tot_Annue", "Costo_Annuo_Tot"]].style.format({"En_Primaria": "{:,.0f}", "Eta_Attiva": "{:.2f}", "Emiss_Tot_Annue": "{:,.0f}", "Costo_Annuo_Tot": "€ {:,.0f}"}), use_container_width=True)

except Exception as e:
    st.error(f"Errore: {e}")
