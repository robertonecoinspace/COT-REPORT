import streamlit as st
import yfinance as yf
import pandas as pd

# --- CONFIGURAZIONE SOGLIE E LOGICHE ---
# mode: direct (alto è bene), inverse (basso è bene), range (tra min e max è bene)
SOGLIE = {
    "TECH": {
        "Revenue Growth (%)": {"v": 20, "g": 5, "mode": "direct"},
        "PEG Ratio": {"v": 1.2, "g": 2.5, "mode": "inverse"},
        "Operating Margin (%)": {"v": 25, "g": 10, "mode": "direct"},
        "Beta": {"v": 1.3, "g": 0.9, "mode": "direct"}
    },
    "FINANCIAL": {
        "Price to Book": {"v": 1.5, "g": 2.2, "mode": "range", "min_v": 0.8},
        "Efficiency Ratio (%)": {"v": 50, "g": 65, "mode": "inverse"},
        "Equity/Assets Ratio": {"v": 0.15, "g": 0.08, "mode": "direct"},
        "Beta": {"v": 1.2, "g": 0.8, "mode": "direct"}
    },
    "ENERGY": {
        "Net Debt / EBITDA": {"v": 1.5, "g": 3.0, "mode": "inverse"},
        "FCF Yield (%)": {"v": 8, "g": 4, "mode": "direct"},
        "EV / EBITDA": {"v": 6, "g": 10, "mode": "inverse"}
    },
    "RETAIL": {
        "Gross Margin (%)": {"v": 40, "g": 20, "mode": "direct"},
        "Quick Ratio": {"v": 1.2, "g": 0.8, "mode": "direct"},
        "Inventory Turnover": {"v": 10, "g": 5, "mode": "direct"}
    }
}

# --- FUNZIONI DI CALCOLO ---
def get_color(val, soglia_dict):
    mode = soglia_dict["mode"]
    if mode == "direct":
        if val >= soglia_dict["v"]: return "🟢"
        if val >= soglia_dict["g"]: return "🟡"
        return "🔴"
    elif mode == "inverse":
        if val <= soglia_dict["v"]: return "🟢"
        if val <= soglia_dict["g"]: return "🟡"
        return "🔴"
    elif mode == "range":
        if soglia_dict["min_v"] <= val <= soglia_dict["v"]: return "🟢"
        if val <= soglia_dict["g"]: return "🟡"
        return "🔴"
    return "⚪"

def safe_div(n, d):
    return n / d if d and d != 0 else 0

@st.cache_data(ttl=3600)
def fetch_and_analyze(ticker, sector):
    try:
        stock = yf.Ticker(ticker)
        q_fin = stock.quarterly_financials
        q_bs = stock.quarterly_balance_sheet
        q_cf = stock.quarterly_cashflow
        info = stock.info

        def get_val(df, row, idx=0):
            if df is not None and row in df.index and len(df.columns) > idx:
                return df.loc[row].iloc[idx]
            return 0

        res = {}

        if sector == "TECH":
            # Revenue Growth
            rev0, rev1 = get_val(q_fin, 'Total Revenue', 0), get_val(q_fin, 'Total Revenue', 1)
            growth = safe_div(rev0 - rev1, abs(rev1)) * 100
            # Margins
            op0, op1 = get_val(q_fin, 'Operating Income', 0), get_val(q_fin, 'Operating Income', 1)
            m0, m1 = safe_div(op0, rev0) * 100, safe_div(op1, rev1) * 100
            
            res["Revenue Growth (%)"] = (growth, 0) # Ticker info growth non ha T1 diretto qui
            res["PEG Ratio"] = (info.get('pegRatio', 0), 0)
            res["Operating Margin (%)"] = (m0, m0 - m1)
            res["Beta"] = (info.get('beta', 1), 0)

        elif sector == "FINANCIAL":
            # Efficiency Ratio
            opex0, opex1 = get_val(q_fin, 'Operating Expense', 0), get_val(q_fin, 'Operating Expense', 1)
            rev0, rev1 = get_val(q_fin, 'Total Revenue', 0), get_val(q_fin, 'Total Revenue', 1)
            eff0, eff1 = safe_div(opex0, rev0) * 100, safe_div(opex1, rev1) * 100
            # Equity/Assets
            eq0, eq1 = get_val(q_bs, 'Stockholders Equity', 0), get_val(q_bs, 'Stockholders Equity', 1)
            as0, as1 = get_val(q_bs, 'Total Assets', 0), get_val(q_bs, 'Total Assets', 1)
            ea0, ea1 = safe_div(eq0, as0), safe_div(eq1, as1)

            res["Price to Book"] = (info.get('priceToBook', 0), 0)
            res["Efficiency Ratio (%)"] = (eff0, eff0 - eff1)
            res["Equity/Assets Ratio"] = (ea0, ea0 - ea1)
            res["Beta"] = (info.get('beta', 1), 0)

        elif sector == "ENERGY":
            ebitda0, ebitda1 = info.get('ebitda', 1), 1 # EBITDA T1 difficile da info
            debt0, cash0 = info.get('totalDebt', 0), info.get('totalCash', 0)
            nd_ebitda = safe_div(debt0 - cash0, ebitda0)
            fcf0, fcf1 = get_val(q_cf, 'Free Cash Flow', 0), get_val(q_cf, 'Free Cash Flow', 1)
            yield0 = safe_div(fcf0, info.get('marketCap', 1)) * 100
            yield1 = safe_div(fcf1, info.get('marketCap', 1)) * 100

            res["Net Debt / EBITDA"] = (nd_ebitda, 0)
            res["FCF Yield (%)"] = (yield0, yield0 - yield1)
            res["EV / EBITDA"] = (info.get('enterpriseToEbitda', 0), 0)

        elif sector == "RETAIL":
            # Gross Margin
            rev0, rev1 = get_val(q_fin, 'Total Revenue', 0), get_val(q_fin, 'Total Revenue', 1)
            gp0, gp1 = get_val(q_fin, 'Gross Profit', 0), get_val(q_fin, 'Gross Profit', 1)
            gm0, gm1 = safe_div(gp0, rev0) * 100, safe_div(gp1, rev1) * 100
            # Quick Ratio
            ca0, ca1 = get_val(q_bs, 'Total Current Assets', 0), get_val(q_bs, 'Total Current Assets', 1)
            inv0, inv1 = get_val(q_bs, 'Inventory', 0), get_val(q_bs, 'Inventory', 1)
            cl0, cl1 = get_val(q_bs, 'Total Current Liabilities', 0), get_val(q_bs, 'Total Current Liabilities', 1)
            qr0, qr1 = safe_div(ca0 - inv0, cl0), safe_div(ca1 - inv1, cl1)

            res["Gross Margin (%)"] = (gm0, gm0 - gm1)
            res["Quick Ratio"] = (qr0, qr0 - qr1)
            res["Inventory Turnover"] = (safe_div(abs(get_val(q_fin, 'Cost Of Revenue', 0)), inv0), 0)

        return res
    except Exception as e:
        st.error(f"Errore tecnico su {ticker}: {e}")
        return None

# --- UI STREAMLIT ---
st.set_page_config(page_title="Trading Sector Analyzer", layout="wide")
st.title("📊 Terminale Analisi Settoriale")
st.markdown("Analisi fondamentale e di trend per trading di breve termine.")

# Sidebar per caricamento
with st.sidebar:
    st.header("⚙️ Configurazione")
    uploaded_file = st.file_uploader("Carica CSV (colonne: ticker, sector)", type="csv")
    st.info("Esempio CSV:\nticker,sector\nNVDA,TECH\nSCHW,FINANCIAL")

if uploaded_file:
    df_stocks = pd.read_csv(uploaded_file)
    selected_sectors = st.multiselect("Filtra Settori", df_stocks['sector'].unique(), default=df_stocks['sector'].unique())
    
    filtered_df = df_stocks[df_stocks['sector'].isin(selected_sectors)]

    for _, row in filtered_df.iterrows():
        ticker, sector = row['ticker'].upper(), row['sector'].upper()
        
        with st.expander(f"📈 {ticker} - Settore: {sector}", expanded=True):
            data = fetch_and_analyze(ticker, sector)
            
            if data:
                cols = st.columns(len(data))
                for i, (name, values) in enumerate(data.items()):
                    val, delta = values
                    soglia_cfg = SOGLIE[sector].get(name, {"v":0, "g":0, "mode":"direct"})
                    color_icon = get_color(val, soglia_cfg)
                    
                    # Logica colore freccia
                    d_color = "normal" if soglia_cfg["mode"] in ["direct", "range"] else "inverse"
                    
                    cols[i].metric(
                        label=f"{color_icon} {name}",
                        value=f"{val:.2f}",
                        delta=f"{delta:.2f}" if delta != 0 else None,
                        delta_color=d_color
                    )
            else:
                st.warning(f"Dati non disponibili per {ticker}")
else:
    st.warning("Per favore, carica un file CSV per iniziare l'analisi.")










