import streamlit as st
import pandas as pd
import requests
import zipfile
import io

# Configurazione Pagina Streamlit
st.set_page_config(page_title="COT Analysis Tool 2026", layout="wide")

@st.cache_data(ttl=86400)
def get_cot_data(years=[2026, 2025]):
    """Scarica e unisce i dati di più anni per garantire uno storico di 52 settimane."""
    categories = {
        "Valute": "https://www.cftc.gov/files/dea/history/fut_fin_txt_{}.zip",
        "Commodities": "https://www.cftc.gov/files/dea/history/fut_disagg_txt_{}.zip"
    }
    
    final_dfs = {"Valute": [], "Commodities": []}
    
    for cat, url_template in categories.items():
        for year in years:
            try:
                r = requests.get(url_template.format(year), timeout=10)
                if r.status_code == 200:
                    with zipfile.ZipFile(io.BytesIO(r.content)) as z:
                        df_year = pd.read_csv(z.open(z.namelist()[0]), low_memory=False)
                        final_dfs[cat].append(df_year)
            except:
                continue
    
    # Unione dei dati (concatena i dataframe degli anni scelti)
    combined_v = pd.concat(final_dfs["Valute"], ignore_index=True) if final_dfs["Valute"] else None
    combined_c = pd.concat(final_dfs["Commodities"], ignore_index=True) if final_dfs["Commodities"] else None
    
    return combined_v, combined_c

def process_market(df, name, is_commodity=False):
    if df is None: return None
    
    # Filtro mercato
    m = df[df['Market_and_Exchange_Names'].str.contains(name, case=False, na=False)].copy()
    if m.empty: return None
    
    # Gestione dinamica colonna data (cerca il formato più comune)
    date_col = [c for c in m.columns if 'Report_Date' in c and 'YYYY_MM_DD' in c]
    if not date_col:
        date_col = [c for c in m.columns if 'Report_Date' in c]
    
    if not date_col: return None
    date_col = date_col[0]
    
    # Conversione data e ordinamento
    m[date_col] = pd.to_datetime(m[date_col])
    m = m.sort_values(date_col)
    
    # Identificazione Colonne in base al report
    if is_commodity:
        s_long, s_short = 'Managed_Money_Positions_Long_All', 'Managed_Money_Positions_Short_All'
        c_long, c_short = 'Prod_Merc_Positions_Long_All', 'Prod_Merc_Positions_Short_All'
    else:
        s_long, s_short = 'Leveraged_Money_Positions_Long_All', 'Leveraged_Money_Positions_Short_All'
        c_long, c_short = 'Dealer_Positions_Long_All', 'Dealer_Positions_Short_All'

    if s_long not in m.columns or s_short not in m.columns:
        return None

    # Calcolo Posizioni Nette
    m['S_Net'] = pd.to_numeric(m[s_long], errors='coerce') - pd.to_numeric(m[s_short], errors='coerce')
    m['C_Net'] = pd.to_numeric(m[c_long], errors='coerce') - pd.to_numeric(m[c_short], errors='coerce')
    
    def get_idx(series):
        win = series.dropna().tail(52) # Prende le ultime 52 settimane disponibili
        if win.empty or win.max() == win.min(): return 50.0
        return round(((series.iloc[-1] - win.min()) / (win.max() - win.min())) * 100, 1)

    return {
        "Asset": name.split(' -')[0], 
        "Spec_Index": get_idx(m['S_Net']), 
        "Comm_Index": get_idx(m['C_Net'])
    }

# --- INTERFACCIA STREAMLIT ---
st.title("📊 COT Report Analytics Pro")
st.markdown("**Stato Connessione CFTC:** Dati 2025-2026 integrati")

# Caricamento dati (2026 e 2025 combinati)
df_v, df_c = get_cot_data([2026, 2025])

v_list = ["EURO FX", "CANADIAN DOLLAR", "BRITISH POUND", "JAPANESE YEN", "SWISS FRANC", "NEW ZEALAND DOLLAR"]
c_list = ["GOLD", "CRUDE OIL", "COPPER", "NATURAL GAS"]

col1, col2 = st.columns(2)

with col1:
    st.header("💱 Valute (G10)")
    v_results_list = []
    if df_v is not None:
        for v in v_list:
            res = process_market(df_v, v, is_commodity=False)
            if res: v_results_list.append(res)
        
        if v_results_list:
            val_res = pd.DataFrame(v_results_list)
            st.table(val_res)
        else:
            st.warning("Nessun dato trovato per le valute. Verifica la connessione al server CFTC.")
    else:
        st.error("Dati Valute non disponibili.")

with col2:
    st.header("📦 Commodities")
    c_results_list = []
    if df_c is not None:
        for c in c_list:
            res = process_market(df_c, c, is_commodity=True)
            if res: c_results_list.append(res)
            
        if c_results_list:
            com_res = pd.DataFrame(c_results_list)
            st.table(com_res)
        else:
            st.warning("Nessun dato trovato per le commodities.")
    else:
        st.error("Dati Commodities non disponibili.")

# --- ANALISI FORZA RELATIVA ---
if 'val_res' in locals() and not val_res.empty:
    st.divider()
    st.header("⚖️ Analisi Forza Relativa")
    col_a, col_b = st.columns(2)
    with col_a:
        v1 = st.selectbox("Seleziona Valuta 1", val_res['Asset'].unique(), key="v1")
    with col_b:
        v2 = st.selectbox("Seleziona Valuta 2", val_res['Asset'].unique(), index=1, key="v2")

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


