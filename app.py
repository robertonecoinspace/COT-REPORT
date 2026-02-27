import streamlit as st
import pandas as pd
import requests
import zipfile
import io

# Configurazione Pagina Streamlit
st.set_page_config(page_title="COT Analysis Tool 2026", layout="wide")

@st.cache_data(ttl=86400) # Salva i dati per 24 ore per velocizzare l'app
def get_cot_data(year=2026):
    urls = {
        "Valute": f"https://www.cftc.gov/files/dea/history/fut_fin_txt_{year}.zip",
        "Commodities": f"https://www.cftc.gov/files/dea/history/fut_disagg_txt_{year}.zip"
    }
    dataframes = {}
    for cat, url in urls.items():
        try:
            r = requests.get(url)
            with zipfile.ZipFile(io.BytesIO(r.content)) as z:
                dataframes[cat] = pd.read_csv(z.open(z.namelist()[0]), low_memory=False)
        except:
            st.error(f"Errore nel download dei dati {cat}")
    return dataframes.get("Valute"), dataframes.get("Commodities")

def process_market(df, name, is_commodity=False):
    if df is None: return None
    m = df[df['Market_and_Exchange_Names'].str.contains(name, case=False, na=False)].copy()
    if m.empty: return None
    m = m.sort_values('Report_Date_as_YYYY_MM_DD')
    
    if is_commodity:
        s_long, s_short = 'Managed_Money_Positions_Long_All', 'Managed_Money_Positions_Short_All'
        c_long, c_short = 'Prod_Merc_Positions_Long_All', 'Prod_Merc_Positions_Short_All'
    else:
        s_long, s_short = 'Leveraged_Money_Positions_Long_All', 'Leveraged_Money_Positions_Short_All'
        c_long, c_short = 'Dealer_Positions_Long_All', 'Dealer_Positions_Short_All'

    m['S_Net'] = m[s_long] - m[s_short]
    m['C_Net'] = m[c_long] - m[c_short]
    
    def get_idx(series):
        win = series.tail(52)
        if win.max() == win.min(): return 50.0
        return round(((series.iloc[-1] - win.min()) / (win.max() - win.min())) * 100, 1)

    return {"Asset": name.split(' -')[0], "Spec_Index": get_idx(m['S_Net']), "Comm_Index": get_idx(m['C_Net'])}

# --- LOGICA APP ---
st.title("📊 COT Report Analytics Pro")
st.markdown(f"**Data Analisi:** 20/08/2026")

df_v, df_c = get_cot_data()

col1, col2 = st.columns(2)

with col1:
    st.header("💱 Valute (G10)")
    v_list = ["EURO FX", "CANADIAN DOLLAR", "BRITISH POUND", "JAPANESE YEN", "SWISS FRANC", "NEW ZEALAND DOLLAR"]
    val_res = pd.DataFrame([process_market(df_v, v) for v in v_list if process_market(df_v, v)])
    st.table(val_res)

with col2:
    st.header("📦 Commodities")
    c_list = ["GOLD", "CRUDE OIL", "COPPER", "NATURAL GAS"]
    com_res = pd.DataFrame([process_market(df_c, c, True) for c in c_list if process_market(df_c, c, True)])
    st.table(com_res)

st.divider()

# --- FORZA RELATIVA ---
st.header("⚖️ Analisi Forza Relativa")
v1 = st.selectbox("Seleziona Valuta 1", val_res['Asset'].unique())
v2 = st.selectbox("Seleziona Valuta 2", val_res['Asset'].unique(), index=1)

idx1 = val_res[val_res['Asset'] == v1]['Spec_Index'].values[0]
idx2 = val_res[val_res['Asset'] == v2]['Spec_Index'].values[0]
diff = round(idx1 - idx2, 1)

st.metric(label=f"Differenziale {v1} / {v2}", value=f"{diff} pts", delta=diff)

# --- LEGENDE UNITE ---
st.divider()
st.subheader("📚 Legenda e Guida all'Analisi")

c_leg1, c_leg2 = st.columns(2)

with c_leg1:
    st.info("""
    **Legenda Tecnica:**
    - **S_Idx (Spec_Index):** Speculatori. 100=Massimi acquisti annui, 0=Massimi saldi.
    - **C_Idx (Comm_Index):** Commercial. Solitamente opposto agli speculatori.
    - **Contrarian:** Se S_Idx > 95 o < 5, possibile inversione di trend.
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
