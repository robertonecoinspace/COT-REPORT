import streamlit as st
import pandas as pd
import requests
import zipfile
import io

st.set_page_config(page_title="COT Analytics 2026 Pro", layout="wide")

@st.cache_data(ttl=3600)
def get_cot_data():
    # Proviamo a scaricare i file consolidati (storici + correnti)
    years = [2026, 2025]
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
                        for filename in z.namelist():
                            if filename.endswith('.txt') or filename.endswith('.csv'):
                                with z.open(filename) as f:
                                    df_temp = pd.read_csv(f, low_memory=False)
                                    final_dfs[cat].append(df_temp)
            except: continue
    
    v_df = pd.concat(final_dfs["Valute"], ignore_index=True) if final_dfs["Valute"] else None
    c_df = pd.concat(final_dfs["Commodities"], ignore_index=True) if final_dfs["Commodities"] else None
    return v_df, c_df

def process_market(df, search_term, is_commodity=False):
    if df is None: return None, None
    
    # Filtro flessibile: cerchiamo la parola chiave
    m = df[df['Market_and_Exchange_Names'].str.contains(search_term, case=False, na=False)].copy()
    if m.empty: return None, None
    
    # Identificazione colonna data
    date_cols = [c for c in m.columns if 'Report_Date' in c]
    if not date_cols: return None, None
    date_col = date_cols[0]
    m[date_col] = pd.to_datetime(m[date_col])
    m = m.sort_values(date_col).drop_duplicates(subset=[date_col], keep='last')
    
    # Mapping Colonne
    if is_commodity:
        cols = ['Managed_Money_Positions_Long_All', 'Managed_Money_Positions_Short_All', 'Prod_Merc_Positions_Long_All', 'Prod_Merc_Positions_Short_All']
    else:
        cols = ['Leveraged_Money_Positions_Long_All', 'Leveraged_Money_Positions_Short_All', 'Dealer_Positions_Long_All', 'Dealer_Positions_Short_All']

    if not all(c in m.columns for c in cols[:2]): return None, None

    # Calcolo Net e Index
    m['S_Net'] = pd.to_numeric(m[cols[0]], errors='coerce').fillna(0) - pd.to_numeric(m[cols[1]], errors='coerce').fillna(0)
    
    def get_idx(series):
        win = series.tail(52)
        if win.max() == win.min(): return 50.0
        return round(((series.iloc[-1] - win.min()) / (win.max() - win.min())) * 100, 1)

    m['Spec_Index_Hist'] = m['S_Net'].rolling(window=52).apply(lambda x: (x[-1] - x.min()) / (x.max() - x.min()) * 100 if x.max() != x.min() else 50)
    
    summary = {
        "Asset": search_term.upper(), 
        "S_Idx": get_idx(m['S_Net']),
        "Data": m[date_col].iloc[-1].strftime('%d/%m/%Y')
    }
    return summary, m[[date_col, 'Spec_Index_Hist']].set_index(date_col)

# --- UI ---
st.title("📊 COT Analytics - Dashboard Strategica")
df_v, df_c = get_cot_data()

# Liste di ricerca ottimizzate
v_list = ["EURO FX", "BRITISH POUND", "JAPANESE YEN", "CANADIAN DOLLAR", "SWISS FRANC"]
c_list = ["GOLD", "CRUDE OIL", "COPPER", "NATURAL GAS"]

c1, c2 = st.columns(2)

with c1:
    st.subheader("💱 Valute")
    v_data = [process_market(df_v, v)[0] for v in v_list if process_market(df_v, v)[0]]
    if v_data: st.table(pd.DataFrame(v_data))
    else: st.error("Database Valute non filtrabile. Riprova più tardi.")

with c2:
    st.subheader("📦 Commodities")
    c_data = [process_market(df_c, c, True)[0] for c in c_list if process_market(df_c, c, True)[0]]
    if c_data: st.table(pd.DataFrame(c_data))
    else: st.error("Database Commodities non filtrabile.")

st.divider()

# --- GRAFICO ---
st.header("📈 Analisi Trend Speculatori")
all_assets = v_list + c_list
choice = st.selectbox("Scegli asset:", all_assets)
is_c = choice in c_list
target_df = df_c if is_c else df_v
summ, hist = process_market(target_df, choice, is_commodity=is_c)

if hist is not None:
    st.line_chart(hist.tail(104))
    
else:
    st.info("Seleziona un asset per visualizzare lo storico.")

st.sidebar.markdown("""
### 💡 Guida Rapida
1. **S_Idx > 90**: Sentiment estremo rialzista. Spesso precede un'inversione (Analisi Contrarian).
2. **S_Idx < 10**: Sentiment estremo ribassista. Possibile rimbalzo.
3. **Data**: Verifica sempre che la data sia l'ultima disponibile (venerdì sera esce il nuovo report).
""")








