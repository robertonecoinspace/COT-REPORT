import streamlit as st
import pandas as pd
import requests
import zipfile
import io

st.set_page_config(page_title="COT Analytics Pro", layout="wide")

@st.cache_data(ttl=3600)
def get_cot_data():
    # Carichiamo gli ultimi 3 anni per garantire la presenza di dati storici
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
    
    # Filtro flessibile per trovare l'asset
    m = df[df['Market_and_Exchange_Names'].str.contains(search_term, case=False, na=False)].copy()
    if m.empty: return None, None
    
    # Pulizia Date
    date_col = [c for c in m.columns if 'Report_Date' in c][0]
    m[date_col] = pd.to_datetime(m[date_col])
    m = m.sort_values(date_col).drop_duplicates(subset=[date_col], keep='last')
    
    # Mapping Colonne
    if is_commodity:
        s_long, s_short = 'Managed_Money_Positions_Long_All', 'Managed_Money_Positions_Short_All'
        c_long, c_short = 'Prod_Merc_Positions_Long_All', 'Prod_Merc_Positions_Short_All'
    else:
        s_long, s_short = 'Leveraged_Money_Positions_Long_All', 'Leveraged_Money_Positions_Short_All'
        c_long, c_short = 'Dealer_Positions_Long_All', 'Dealer_Positions_Short_All'

    # Calcolo Posizioni Nette e Index
    m['S_Net'] = pd.to_numeric(m[s_long], errors='coerce') - pd.to_numeric(m[s_short], errors='coerce')
    m['C_Net'] = pd.to_numeric(m[c_long], errors='coerce') - pd.to_numeric(m[c_short], errors='coerce')
    
    # Calcolo dell'indice mobile (rolling) per il grafico
    def calculate_rolling_idx(series):
        return series.rolling(window=52).apply(lambda x: (x[-1] - x.min()) / (x.max() - x.min()) * 100 if x.max() != x.min() else 50)

    m['Spec_Index_Hist'] = calculate_rolling_idx(m['S_Net'])
    
    summary = {
        "Asset": search_term.upper(), 
        "Spec_Index": round(m['Spec_Index_Hist'].iloc[-1], 1),
        "Comm_Index": round(((m['C_Net'].iloc[-1] - m['C_Net'].tail(52).min()) / (m['C_Net'].tail(52).max() - m['C_Net'].tail(52).min()) * 100), 1),
        "Ultima Data": m[date_col].iloc[-1].strftime('%d/%m/%Y')
    }
    
    return summary, m[[date_col, 'Spec_Index_Hist']].set_index(date_col)

# --- APP ---
st.title("📊 COT Report Advanced Analytics")
df_v, df_c = get_cot_data()

v_list = ["EURO FX", "BRITISH POUND", "JAPANESE YEN", "CANADIAN DOLLAR", "SWISS FRANC"]
c_list = ["GOLD -", "CRUDE OIL", "COPPER -", "NATURAL GAS", "SILVER -"]

# Layout Tabelle
t1, t2 = st.columns(2)
with t1:
    st.subheader("💱 Forex Sentiment")
    v_summaries = []
    for v in v_list:
        s, _ = process_market_with_history(df_v, v)
        if s: v_summaries.append(s)
    if v_summaries: st.dataframe(pd.DataFrame(v_summaries), hide_index=True)
    else: st.warning("Dati valute in aggiornamento...")

with t2:
    st.subheader("📦 Commodities Sentiment")
    c_summaries = []
    for c in c_list:
        s, _ = process_market_with_history(df_c, c, is_commodity=True)
        if s: c_summaries.append(s)
    if c_summaries: st.dataframe(pd.DataFrame(c_summaries), hide_index=True)
    else: st.info("Dati commodities non trovati. Prova a ricaricare tra poco.")

# --- SEZIONE GRAFICI ---
st.divider()
st.header("📈 Analisi Storica Speculatori (Ultimi 2 anni)")
all_assets = v_list + c_list
selected_asset = st.selectbox("Seleziona Asset per il grafico", all_assets)

is_com = selected_asset in c_list
df_to_use = df_c if is_com else df_v
summary, history = process_market_with_history(df_to_use, selected_asset, is_commodity=is_com)

if history is not None:
    st.line_chart(history.tail(104)) # Mostra le ultime 104 settimane (2 anni)
    st.caption(f"Il grafico mostra l'andamento del COT Index per {selected_asset}. Valori estremi (0 o 100) indicano potenziali punti di inversione.")

# --- LEGENDA ---
st.divider()
st.subheader("📚 Legenda e Guida")
c_l, c_r = st.columns(2)
with c_l:
    st.info("**S_Idx (Speculatori):** 100=Massimi acquisti annui, 0=Massimi saldi. Se > 95 o < 5, segnale contrarian.")
with c_r:
    st.warning("**C_Idx (Commercial):** Hedgers/Produttori. Solitamente si muovono in opposizione agli speculatori.")

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






