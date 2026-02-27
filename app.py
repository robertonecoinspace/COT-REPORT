import streamlit as st
import pandas as pd
import requests
import zipfile
import io

st.set_page_config(page_title="COT Analytics Pro", layout="wide")

@st.cache_data(ttl=3600)
def get_cot_data():
    # Analizziamo gli ultimi 3 anni per avere uno storico di 52 settimane solido
    years = [2026, 2025, 2024]
    categories = {
        "Valute": "https://www.cftc.gov/files/dea/history/fut_fin_txt_{}.zip",
        "Commodities": "https://www.cftc.gov/files/dea/history/fut_disagg_txt_{}.zip"
    }
    final_dfs = {"Valute": [], "Commodities": []}
    
    for cat, url_template in categories.items():
        for year in years:
            try:
                r = requests.get(url_template.format(year), timeout=15)
                if r.status_code == 200:
                    with zipfile.ZipFile(io.BytesIO(r.content)) as z:
                        # Leggiamo il file txt all'interno dello zip
                        df_year = pd.read_csv(z.open(z.namelist()[0]), low_memory=False)
                        if not df_year.empty:
                            final_dfs[cat].append(df_year)
            except: continue
    
    v_df = pd.concat(final_dfs["Valute"], ignore_index=True) if final_dfs["Valute"] else None
    c_df = pd.concat(final_dfs["Commodities"], ignore_index=True) if final_dfs["Commodities"] else None
    return v_df, c_df

def process_market(df, search_term, is_commodity=False):
    if df is None: return None
    
    # Filtro flessibile: cerchiamo la parola chiave nel nome del mercato
    m = df[df['Market_and_Exchange_Names'].str.contains(search_term, case=False, na=False)].copy()
    if m.empty: return None
    
    # Pulizia e ordinamento per data
    date_cols = [c for c in m.columns if 'Report_Date' in c]
    if not date_cols: return None
    date_col = date_cols[0]
    
    m[date_col] = pd.to_datetime(m[date_col])
    m = m.sort_values(date_col).drop_duplicates(subset=[date_col], keep='last')
    
    # Mapping colonne Speculatori (Smart Money) e Commercial (Hedgers)
    if is_commodity:
        # Report Disaggregated: Managed Money vs Producer/Merchant
        s_long, s_short = 'Managed_Money_Positions_Long_All', 'Managed_Money_Positions_Short_All'
        c_long, c_short = 'Prod_Merc_Positions_Long_All', 'Prod_Merc_Positions_Short_All'
    else:
        # Report TFF: Leveraged Money vs Dealer/Intermediary
        s_long, s_short = 'Leveraged_Money_Positions_Long_All', 'Leveraged_Money_Positions_Short_All'
        c_long, c_short = 'Dealer_Positions_Long_All', 'Dealer_Positions_Short_All'

    try:
        # Calcolo Posizioni Nette
        m['S_Net'] = pd.to_numeric(m[s_long], errors='coerce') - pd.to_numeric(m[s_short], errors='coerce')
        m['C_Net'] = pd.to_numeric(m[c_long], errors='coerce') - pd.to_numeric(m[c_short], errors='coerce')
        
        # Calcolo COT Index (Percentile ultimi 12 mesi)
        def get_idx(series):
            win = series.dropna().tail(52)
            if win.empty or win.max() == win.min(): return 50.0
            return round(((series.iloc[-1] - win.min()) / (win.max() - win.min())) * 100, 1)

        return {
            "Asset": search_term.upper(), 
            "Spec_Index": get_idx(m['S_Net']), 
            "Comm_Index": get_idx(m['C_Net']),
            "Ultima Data": m[date_col].iloc[-1].strftime('%d/%m/%Y')
        }
    except: return None

# --- UI STREAMLIT ---
st.title("📊 COT Report Analytics Pro")
st.caption("Aggiornamento automatico dai server CFTC.gov")

df_v, df_c = get_cot_data()

# Liste di ricerca ottimizzate per i database CFTC
v_list = ["EURO", "POUND", "YEN", "CANADIAN", "SWISS", "ZEALAND"]
# Per le commodities usiamo nomi più generici per aumentare le probabilità di match
c_list = ["GOLD", "CRUDE OIL", "COPPER", "NATURAL GAS", "SILVER"]

c1, c2 = st.columns(2)

with c1:
    st.subheader("💱 Valute (FX)")
    v_data = [process_market(df_v, v) for v in v_list if process_market(df_v, v)]
    if v_data:
        st.dataframe(pd.DataFrame(v_data), use_container_width=True, hide_index=True)
    else: st.warning("Dati valute non disponibili al momento.")

with c2:
    st.subheader("📦 Commodities")
    # Qui è dove il filtro potrebbe fallire se non è accurato
    c_data = []
    if df_c is not None:
        for c in c_list:
            res = process_market(df_c, c, is_commodity=True)
            if res: c_data.append(res)
    
    if c_data:
        st.dataframe(pd.DataFrame(c_data), use_container_width=True, hide_index=True)
    else: 
        st.error("Dati Commodities non trovati nel database scaricato.")
        if df_c is not None:
            st.info(f"Il database Commodities è stato scaricato ({len(df_c)} righe), ma i filtri {c_list} non hanno prodotto risultati.")

# Forza Relativa
if v_data:
    val_res = pd.DataFrame(v_data)
    st.divider()
    st.header("⚖️ Analisi Forza Relativa")
    v_options = val_res['Asset'].unique()
    col_a, col_b = st.columns(2)
    with col_a: v1 = st.selectbox("Valuta 1", v_options, key="v1")
    with col_b: v2 = st.selectbox("Valuta 2", v_options, index=1, key="v2")
    
    idx1 = val_res[val_res['Asset'] == v1]['Spec_Index'].values[0]
    idx2 = val_res[val_res['Asset'] == v2]['Spec_Index'].values[0]
    
    st.metric(f"Spread {v1}/{v2}", f"{round(idx1 - idx2, 1)} pts", help="Un valore positivo indica che la Valuta 1 è più forte della Valuta 2 secondo gli speculatori.")

# Legende
st.divider()
with st.expander("📚 GUIDA E LEGENDA"):
    st.write("""
    - **Spec_Index:** Posizionamento dei grandi fondi (Smart Money). >90 Iper-comprato, <10 Iper-venduto.
    - **Comm_Index:** Posizionamento dei produttori/utilizzatori reali. Spesso agisce da contrappeso agli speculatori.
    - **Nota:** Il COT Report viene rilasciato il venerdì sera (USA) con i dati del martedì precedente.
    """)

# --- LEGENDE UNITE ---
st.divider()
st.subheader("📚 Legenda e Guida all'Analisi")

c_leg1, c_leg2 = st.columns(2)

with c_leg1:
    st.info("""
    **Legenda Tecnica:**
    - **Spec_Index (S_Idx):** Speculatori. 100=Massimi acquisti annui, 0=Massimi saldi.
    - **Comm_Index (C_Idx):** Commercial. Solitamente opposto agli speculatori.
    - **Contrarian:** Se Spec_Index > 95 o < 5, possibile inversione di trend.
    """)

with c_leg2:
    st.warning("""
    **Guida all'Interpretazione:**
    1. **Spec_COT_Index (0-100%):** Rappresenta il posizionamento degli Hedge Funds. 
       - Vicino a 100: Iper-comprato. 
       - Vicino a 0: Iper-venduto.
    2. **Comm_COT_Index:** Se Spec=90 e Comm=10, il trend è confermato da entrambi i lati.
    3. **Crowded Trades:** Un valore di 95% suggerisce che la forza del trend potrebbe essere esaurita.
    """)

st.divider()
st.caption("Nota: I dati vengono aggiornati ogni venerdì sera dal server ufficiale CFTC.gov.")





