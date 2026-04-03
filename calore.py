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

    # --- 2. ESTRAZIONE DATI BASE (Righe 4-15 -> Indici 3-14) ---
    dati_finali = []
    
    # Estraiamo tutte e 12 le tecnologie senza filtri
    for i in range(3, 15):
        nome_tec = safe_str(df_raw, i, 1) # Colonna B
        
        if nome_tec == "" or nome_tec.lower() == "nan": 
            continue
            
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
        st.error("Nessun dato trovato per il riscaldamento. Verifica le righe 4-15.")
        st.stop()

    df_clean = pd.DataFrame(dati_finali)

    # Parametri globali base (J18, J19)
    fabbisogno_base_excel = safe_num(df_raw, 17, 9) # J18
    lifetime_base_excel = safe_num(df_raw, 18, 9)   # J19
    if fabbisogno_base_excel == 0: fabbisogno_base_excel = 150000
    if lifetime_base_excel == 0: lifetime_base_excel = 15

    # --- 3. LETTURA COSTI COMBUSTIBILE E COP (SIDEBAR) ---
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

    # Prezzi (B18:B25 -> Indici 17:24)
    for r in range(17, 25):
        label = safe_str(df_raw, r, 1) # B
        if label == "" or label.lower() == "nan": continue
        
        try:
            val_natura = safe_num(df_raw, r, 2)     # C: Costo unità nativa
            val_kwh_excel = safe_num(df_raw, r, 5)  # F: Costo in €/kWh (da Excel)
            
            # Fattore di conversione implicito dall'Excel
            fattore = (val_kwh_excel / val_natura) if val_natura > 0 else 1.0
                
            etichetta_ui = f"{label} {get_unit_heat(label)}"
            
            # Cursore (+/-) per il costo nativo
            user_val = st.sidebar.number_input(etichetta_ui, value=float(val_natura), format="%.3f", step=0.05)
            
            costi_input_kwh[label] = user_val * fattore
            etichette_costi_letti[label.lower()] = label
        except:
            pass

    st.sidebar.divider()
    st.sidebar.header("🌡️ Rendimenti PdC (COP)")
    
    # COP (C28 e C29 -> Indici 27 e 28, Colonna 2)
    cop_aria_def = safe_num(df_raw, 27, 2)
    if cop_aria_def == 0: cop_aria_def = 3.2
    cop_geo_def = safe_num(df_raw, 28, 2)
    if cop_geo_def == 0: cop_geo_def = 4.5
    
    user_cop_aria = st.sidebar.number_input("COP PdC Aria-H2O", value=float(cop_aria_def), step=0.1)
    user_cop_geo = st.sidebar.number_input("COP PdC Geotermica", value=float(cop_geo_def), step=0.1)

    st.sidebar.divider()
    st.sidebar.header("⚙️ Parametri Edificio (J18, J19)")
    
    # Cursori a scorrimento estesi fino a 2000 kWh/y
    user_fabbisogno = st.sidebar.slider(
        "Fabbisogno Termico [kWh_th/y]", 
        min_value=2000, 
        max_value=500000, 
        value=int(max(2000, fabbisogno_base_excel)), 
        step=1000
    )
    user_lifetime = st.sidebar.slider(
        "Vita Utile Impianto (y)", 
        min_value=1, 
        max_value=30, 
        value=int(max(1, lifetime_base_excel)), 
        step=1
    )

    # --- 4. IL MOTORE MATEMATICO ---
    def calcola_riscaldamento(row):
        t = row["Tecnologia"]
        t_low = t.lower()
        
        # 1. Abbinamento Intelligente Combustibile -> Tecnologia (rete vs auto)
        p_fuel_kwh = 0.10
        if "gasolio" in t_low: 
            p_fuel_kwh = costi_input_kwh.get(etichette_costi_letti.get("diesel", ""), 0.18)
        elif "metano" in t_low: 
            p_fuel_kwh = costi_input_kwh.get(etichette_costi_letti.get("metano", ""), 0.10)
        elif "pellet" in t_low: 
            p_fuel_kwh = costi_input_kwh.get(etichette_costi_letti.get("pellet", ""), 0.06)
        elif "elettrico" in t_low or "joule" in t_low or "pdc" in t_low or "aria-h2o" in t_low or "geotermica" in t_low:
            if "auto" in t_low or "pv" in t_low:
                p_fuel_kwh = costi_input_kwh.get(etichette_costi_letti.get("elettrico autoprodotto (pv)", ""), 0.24)
            else:
                p_fuel_kwh = costi_input_kwh.get(etichette_costi_letti.get("elettrico da rete", ""), 0.31)
        elif "idrogeno" in t_low:
            if "grigio" in t_low: 
                p_fuel_kwh = costi_input_kwh.get(etichette_costi_letti.get("idrogeno grigio", ""), 0.06)
            elif "rete" in t_low: 
                p_fuel_kwh = costi_input_kwh.get(etichette_costi_letti.get("idrogeno da rete", ""), 0.60)
            elif "verde" in t_low or "auto" in t_low: 
                p_fuel_kwh = costi_input_kwh.get(etichette_costi_letti.get("idrogeno verde autoprodotto", ""), 0.45)
            else: 
                p_fuel_kwh = costi_input_kwh.get(etichette_costi_letti.get("idrogeno grigio", ""), 0.06)
        
        # 2. Definisci il rendimento/COP
        attivo_eta_cop = row["Eta_COP_Base"]
        if "aria-h2o" in t_low or ("pdc" in t_low and "geo" not in t_low):
            attivo_eta_cop = user_cop_aria
        elif "geotermica" in t_low or "geo" in t_low:
            attivo_eta_cop = user_cop_geo
        
        if attivo_eta_cop == 0: attivo_eta_cop = 1.0 
        
        # 3. Ricalcolo Fabbisogni
        consumo_vettore_kwh = user_fabbisogno / attivo_eta_cop
        fattore_scala = consumo_vettore_kwh / row["Consumo_Base"] if row["Consumo_Base"] > 0 else 1.0
        
        en_primaria = row["En_Prim_Base"] * fattore_scala
        wtw_annuo = row["WtW_Base"] * fattore_scala
        
        # 4. Calcoli Economici
        fuel_annuo = consumo_vettore_kwh * p_fuel_kwh
        maint_annuo = row["Maint_Anno"] 
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

    # --- 6. VISUALIZZAZIONE RISULTATI ---
    st.divider()
    
    # RIGA 1: Energia e Rendimento
    c1, c2 = st.columns(2)
    with c1:
        st.subheader("1. Energia Primaria Richiesta [kWh/y]")
        fig1 = px.bar(df_clean, x="Tecnologia", y="En_Primaria", color="Tecnologia")
        # Rotazione etichette per evitare sovrapposizioni con 12 tecnologie
        fig1.update_layout(xaxis_tickangle=-45)
        st.plotly_chart(fig1, use_container_width=True)
    with c2:
        st.subheader("2. Efficienza di Processo (η)")
        df_clean["Eta_Perc"] = df_clean["Eta_Proc"] * 100 if df_clean["Eta_Proc"].mean() < 6 else df_clean["Eta_Proc"]
        fig2 = px.bar(df_clean, x="Tecnologia", y="Eta_Perc", color="Tecnologia", text_auto='.1f')
        fig2.update_layout(yaxis_title="Rendimento %", xaxis_tickangle=-45)
        st.plotly_chart(fig2, use_container_width=True)

    # RIGA 2: Emissioni
    c3, c4 = st.columns(2)
    with c3:
        st.subheader("3. Emissioni WtW [kg CO2/anno]")
        fig3 = px.bar(df_clean, x="Tecnologia", y="WtW_Annuo", color="Tecnologia")
        fig3.update_layout(xaxis_tickangle=-45)
        st.plotly_chart(fig3, use_container_width=True)
    with c4:
        st.subheader("4. Emissioni Totali LCA [t CO2]")
        fig4 = px.bar(df_clean, x="Tecnologia", y="Emiss_Tot_LCA", color="Tecnologia")
        fig4.update_layout(xaxis_tickangle=-45)
        st.plotly_chart(fig4, use_container_width=True)

    # RIGA 3: Costi
    c5, c6 = st.columns(2)
    with c5:
        st.subheader("5. Costo Annuo (TCO/y) [€/anno]")
        df_plot_y = df_clean.melt(id_vars="Tecnologia", value_vars=['CAPEx_Annuo', 'Maint_Annuo', 'Fuel_Annuo'], 
                                  var_name="Voce", value_name="Euro")
        df_plot_y["Voce"] = df_plot_y["Voce"].replace({'CAPEx_Annuo':'CAPEx (Quota Acq.)', 'Maint_Annuo':'OPEx (Manut)', 'Fuel_Annuo':'OPEx (Vettore)'})
        fig5 = px.bar(df_plot_y, x="Tecnologia", y="Euro", color="Voce", barmode='stack',
                      color_discrete_sequence=["#0068C9", "#FFA421", "#FF4B4B"])
        fig5.update_layout(xaxis_tickangle=-45)
        st.plotly_chart(fig5, use_container_width=True)
        
    with c6:
        st.subheader("6. Costo Totale Vita (TCO) [€]")
        df_clean['CAPEx_Acquisto'] = df_clean['CAPEX_Totale']
        df_plot_tot = df_clean.melt(id_vars="Tecnologia", value_vars=['CAPEx_Acquisto', 'Maint_Tot', 'Fuel_Tot'], 
                                    var_name="Voce", value_name="Euro")
        df_plot_tot["Voce"] = df_plot_tot["Voce"].replace({'CAPEx_Acquisto':'CAPEx (Investimento)', 'Maint_Tot':'OPEx (Manut)', 'Fuel_Tot':'OPEx (Vettore)'})
        fig6 = px.bar(df_plot_tot, x="Tecnologia", y="Euro", color="Voce", barmode='stack',
                      color_discrete_sequence=["#0068C9", "#FFA421", "#FF4B4B"])
        fig6.update_layout(xaxis_tickangle=-45)
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
