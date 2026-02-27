import streamlit as st
import pandas as pd
import requests
import zipfile
import io

st.set_page_config(page_title="COT Analytics Pro 2026", layout="wide")

@st.cache_data(ttl=3600)
def get_cot_data():
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
                        df_year = pd.read_csv(z.open(z.namelist()[0]), low_memory=False)
                        if not df_year.empty:
                            final_dfs[cat].append(df_year)
            except: continue
    
    v_df = pd.concat(final_dfs["Valute"], ignore_index=True) if final_dfs["Valute"] else None
    c_df = pd.concat(final_dfs["Commodities"], ignore_index=True) if final_dfs["Commodities"] else None
    return v_df, c_df

def process_market_with_history(df, search_term, is_commodity=False):
    if df is None: return None, None
    
    # Filtro asset
    m = df[df['Market_and_Exchange_Names'].str.contains(search_term, case=False, na=False)].copy()
    if m.empty: return None, None
    
    # Identificazione colonna data
    date_cols = [c for c in m.columns if 'Report_Date' in c]
    if not date_cols: return None, None
    date_col = date_cols[0]
    m[date_col] = pd.to_datetime(m[date_col])
    m = m.sort_values(date_col).drop_duplicates(subset=[date_col], keep='last')
    
    # Selezione colonne in base al tipo di report (TFF per valute, Disaggregated per comm)
    if is_commodity:
        cols = ['Managed_Money_Positions_Long_All', 'Managed_Money_Positions_Short_All', 
                'Prod_Merc_Positions_Long_All', 'Prod_Merc_Positions_Short_All']
    else:
        cols = ['Leveraged_Money_Positions_Long_All', 'Leveraged_Money_Positions_Short_All', 
                'Dealer_Positions_Long_All', 'Dealer_Positions_Short_All']

    # Controllo di sicurezza: se mancano le colonne, scarta l'asset
    if not all(c in m.columns for c in cols[:2]):
        return None, None

    # Calcolo Posizioni Nette
    m['S_Net'] = pd.to_numeric(m[cols[0]], errors='coerce').fillna(0) - pd.to_numeric(m[cols[1]], errors='coerce').fillna(0)
    
    # Calcolo Index Mobile
    def calc_idx(series):
        win = series.tail(52)
        if win.max() == win.min(): return 50.0
        return ((series.iloc[-1] - win.min()) / (win.max() - win.min())) * 100

    # Generazione storica per grafico
    m['Spec_Index_Hist'] = m['S_Net'].rolling(window=52).apply(
        lambda x: (x[-1] - x.min()) / (x.max() - x.min()) * 100 if x.max() != x.min() else 50
    )
    
    summary = {
        "Asset": search_term.replace(" -", ""), 
        "Spec_Index": round(m['Spec_Index_Hist'].iloc[-1], 1) if not pd.isna(m['Spec_Index_Hist'].iloc[-1]) else 50.0,
        "Ultima Data": m[date_col].iloc[-1].strftime('%d/%m/%Y')
    }
    
    return summary, m[[date_col, 'Spec_Index_Hist']].set_index(date_col)

# --- UI ---
st.title("📊 COT Report Analytics 2026")
df_v, df_c = get_cot_data()

v_list = ["EURO FX", "BRITISH POUND", "JAPANESE YEN", "CANADIAN DOLLAR", "SWISS FRANC"]
c_list = ["GOLD -", "CRUDE OIL", "COPPER -", "NATURAL GAS", "SILVER -"]

t1, t2 = st.columns(2)
with t1:
    st.subheader("💱 Valute")
    v_summs = []
    for v in v_list:
        s, _ = process_market_with_history(df_v, v)
        if s: v_summs.append(s)
    if v_summs: st.table(pd.DataFrame(v_summs))
    else: st.warning("Dati valute non disponibili (Verifica report TFF)")

with t2:
    st.subheader("📦 Commodities")
    c_summs = []
    for c in c_list:
        s, _ = process_market_with_history(df_c, c, is_commodity=True)
        if s: c_summs.append(s)
    if c_summs: st.table(pd.DataFrame(c_summs))
    else: st.warning("Dati commodities non disponibili (Verifica report Disaggregated)")

st.divider()

# --- GRAFICI ---
st.header("📈 Grafico Storico Speculatori")
all_assets = v_list + c_list
choice = st.selectbox("Seleziona asset:", all_assets)

target_df = df_c if choice in c_list else df_v
is_c = choice in c_list
s, hist = process_market_with_history(target_df, choice, is_commodity=is_c)

if hist is not None:
    st.line_chart(hist.tail(104))
    
else:
    st.error("Impossibile generare il grafico per questo asset.")

st.divider()
st.info("**Legenda:** Spec_Index > 90 (Iper-comprato), < 10 (Iper-venduto). Analisi basata su 52 settimane.")






