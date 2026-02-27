import streamlit as st
import pandas as pd
import requests
import zipfile
import io

st.set_page_config(page_title="COT Analysis Tool 2026", layout="wide")

@st.cache_data(ttl=3600) # Aggiorna ogni ora per beccare l'uscita del venerdì
def get_cot_data(years=[2026, 2025]):
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
                        df_year = pd.read_csv(z.open(z.namelist()[0]), low_memory=False)
                        final_dfs[cat].append(df_year)
            except: continue
    
    combined_v = pd.concat(final_dfs["Valute"], ignore_index=True) if final_dfs["Valute"] else None
    combined_c = pd.concat(final_dfs["Commodities"], ignore_index=True) if final_dfs["Commodities"] else None
    return combined_v, combined_c

def process_market(df, search_term, is_commodity=False):
    if df is None: return None
    
    # Filtro più permissivo
    m = df[df['Market_and_Exchange_Names'].str.contains(search_term, case=False, na=False)].copy()
    if m.empty: return None
    
    # Pulizia date
    date_col = [c for c in m.columns if 'Report_Date' in c and 'YYYY_MM_DD' in c]
    if not date_col: date_col = [c for c in m.columns if 'Report_Date' in c]
    if not date_col: return None
    
    date_col = date_col[0]
    m[date_col] = pd.to_datetime(m[date_col])
    m = m.sort_values(date_col).drop_duplicates(subset=[date_col], keep='last')
    
    if is_commodity:
        s_long, s_short = 'Managed_Money_Positions_Long_All', 'Managed_Money_Positions_Short_All'
        c_long, c_short = 'Prod_Merc_Positions_Long_All', 'Prod_Merc_Positions_Short_All'
    else:
        s_long, s_short = 'Leveraged_Money_Positions_Long_All', 'Leveraged_Money_Positions_Short_All'
        c_long, c_short = 'Dealer_Positions_Long_All', 'Dealer_Positions_Short_All'

    if s_long not in m.columns: return None

    m['S_Net'] = pd.to_numeric(m[s_long], errors='coerce') - pd.to_numeric(m[s_short], errors='coerce')
    m['C_Net'] = pd.to_numeric(m[c_long], errors='coerce') - pd.to_numeric(m[c_short], errors='coerce')
    
    def get_idx(series):
        win = series.dropna().tail(52)
        if win.empty or win.max() == win.min(): return 50.0
        return round(((series.iloc[-1] - win.min()) / (win.max() - win.min())) * 100, 1)

    return {
        "Asset": search_term, 
        "Spec_Index": get_idx(m['S_Net']), 
        "Comm_Index": get_idx(m['C_Net']),
        "Ultima Data": m[date_col].iloc[-1].strftime('%Y-%m-%d')
    }

# --- APP ---
st.title("📊 COT Report Analytics Pro")
df_v, df_c = get_cot_data([2026, 2025])

# Liste semplificate per il filtro
v_list = ["EURO", "POUND", "YEN", "CANADIAN", "SWISS", "ZEALAND"]
c_list = ["GOLD", "CRUDE OIL", "COPPER", "NATURAL GAS"]

col1, col2 = st.columns(2)

with col1:
    st.header("💱 Valute (G10)")
    v_res_list = [process_market(df_v, v) for v in v_list if process_market(df_v, v)]
    if v_res_list:
        val_res = pd.DataFrame(v_res_list)
        st.table(val_res)
    else: st.warning("In attesa dei dati dalle 21:30...")

with col2:
    st.header("📦 Commodities")
    c_res_list = [process_market(df_c, c, True) for c in c_list if process_market(df_c, c, True)]
    if c_res_list:
        com_res = pd.DataFrame(c_res_list)
        st.table(com_res)
    else: st.warning("Dati Commodities non trovati.")

# Forza Relativa e Legende rimangono uguali...
if 'val_res' in locals() and not val_res.empty:
    st.divider()
    st.header("⚖️ Analisi Forza Relativa")
    v1 = st.selectbox("Seleziona Valuta 1", val_res['Asset'].unique(), key="v1")
    v2 = st.selectbox("Seleziona Valuta 2", val_res['Asset'].unique(), index=1, key="v2")
    idx1 = val_res[val_res['Asset'] == v1]['Spec_Index'].values[0]
    idx2 = val_res[val_res['Asset'] == v2]['Spec_Index'].values[0]
    st.metric(f"Diff. {v1}/{v2}", f"{round(idx1-idx2, 1)} pts")

st.divider()
st.info("**LEGGENDA:** S_Idx (Speculatori) > 95 o < 5 = Segnale Contrarian (Possibile Inversione).")

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



