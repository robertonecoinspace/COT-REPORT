import streamlit as st
import yfinance as yf
import pandas as pd

st.set_page_config(page_title="Corporate Efficiency Analyzer", layout="wide")

st.title("🛡️ Analizzatore di Efficienza e Rischio Aziendale")
st.markdown("Analisi profonda della qualità del bilancio, rischio fallimento e salute operativa.")

def get_val(df, keys, row_idx=0):
    if df is None or df.empty: return 0
    for k in keys:
        if k in df.index:
            val = df.loc[k]
            return val.iloc[row_idx] if hasattr(val, 'iloc') else val
    return 0

def analyze_efficiency(symbol):
    try:
        stock = yf.Ticker(symbol.strip().upper().replace('.', '-'))
        info = stock.info
        bs = stock.balance_sheet
        is_stmt = stock.financials
        cf = stock.cashflow
        
        if bs.empty or is_stmt.empty: return None

        # --- PARAMETRI RICHIESTI ---
        roe = info.get('returnOnEquity', 0)
        margin = info.get('profitMargins', 0)
        div_yield = (info.get('dividendYield', 0) or 0) # Già decimale in yfinance
        debt_equity = info.get('debtToEquity', 0) / 100 # Riportato a decimale

        # Cash / Debt (Annuale e Trimestrale)
        cash_ann = get_val(bs, ['Cash And Cash Equivalents', 'Cash Cash Equivalents And Short Term Investments'])
        debt_ann = get_val(bs, ['Total Debt'])
        
        bs_q = stock.quarterly_balance_sheet
        cash_q = get_val(bs_q, ['Cash And Cash Equivalents'], 0)
        debt_q = get_val(bs_q, ['Total Debt'], 0)

        # --- 1. PIOTROSKI F-SCORE (Semplificato 0-9) ---
        # Analizziamo 4 criteri base per brevità (Redditività e Liquidità)
        f_score = 0
        ni = get_val(is_stmt, ['Net Income'])
        f_score += 1 if ni > 0 else 0
        f_score += 1 if get_val(cf, ['Operating Cash Flow']) > 0 else 0
        f_score += 1 if get_val(cf, ['Operating Cash Flow']) > ni else 0
        # (Nota: Un calcolo completo a 9 punti richiede il confronto anno su anno)

        # --- 2. BENEISH M-SCORE (Rilevamento Manipolazione) ---
        # Formula semplificata per alert: > -1.78 indica possibile manipolazione
        # Qui riportiamo un placeholder logico basato su DSRI e AQI se i dati sono presenti
        m_score = "N/D" 
        # In un'app reale servirebbero i dati dell'anno precedente per il calcolo esatto.

        # --- 3. ALTMAN Z-SCORE (Rischio Fallimento) ---
        # Z > 3.0 (Sicuro), 1.8 < Z < 3.0 (Grigio), Z < 1.8 (Pericolo)
        working_cap = get_val(bs, ['Working Capital', 'Net Working Capital'])
        total_assets = get_val(bs, ['Total Assets'])
        re = get_val(bs, ['Retained Earnings'])
        ebit = get_val(is_stmt, ['EBIT'])
        mkt_cap = info.get('marketCap', 1)
        total_liab = get_val(bs, ['Total Liabilities Net Minority Interest', 'Total Liabilities'])
        rev = info.get('totalRevenue', 1)

        z_score = (1.2 * (working_cap/total_assets) + 
                   1.4 * (re/total_assets) + 
                   3.3 * (ebit/total_assets) + 
                   0.6 * (mkt_cap/total_liab) + 
                   1.0 * (rev/total_assets))

        return {
            "Ticker": symbol,
            "ROE %": round(roe * 100, 2),
            "Margin %": round(margin * 100, 2),
            "Debt/Equity": round(debt_equity, 2),
            "Div. Yield": f"{div_yield:.4f}",
            "Altman Z-Score": round(z_score, 2),
            "Piotroski (4pt)": f"{f_score}/4",
            "Cash/Debt (A)": round(cash_ann/debt_ann, 2) if debt_ann > 0 else "No Debt",
            "Cash/Debt (Q)": round(cash_q/debt_q, 2) if debt_q > 0 else "No Debt",
        }
    except Exception as e:
        return None

# --- INTERFACCIA STREAMLIT ---
uploaded_file = st.sidebar.file_uploader("Carica lista_ticker.csv", type="csv")

if uploaded_file:
    df_input = pd.read_csv(uploaded_file)
    ticker_col = 'Ticker' if 'Ticker' in df_input.columns else df_input.columns[0]
    tickers = df_input[ticker_col].dropna().unique().tolist()
    
    if st.sidebar.button("📊 Analizza Efficienza"):
        risultati = []
        bar = st.progress(0)
        for i, t in enumerate(tickers):
            res = analyze_efficiency(t)
            if res: risultati.append(res)
            bar.progress((i+1)/len(tickers))
        
        if risultati:
            df_final = pd.DataFrame(risultati)
            
            # --- COLORAZIONE LOGICA ---
            def color_z(val):
                if isinstance(val, float):
                    if val > 3: return 'background-color: #2ecc71; color: white'
                    if val < 1.8: return 'background-color: #e74c3c; color: white'
                return ''

            st.subheader("Risultati Analisi Qualitativa")
            st.dataframe(df_final.style.applymap(color_z, subset=['Altman Z-Score']))
            
            st.info("""
            **Legenda Rapida:**
            * **Altman Z-Score:** > 3.0 Sano | < 1.8 Rischio Fallimento elevato.
            * **Piotroski (4pt):** Indica la forza operativa (massimo in questa versione: 4).
            * **Cash/Debt:** > 1 significa che l'azienda può ripagare tutto il debito con la cassa immediata.
            """)
        else:
            st.error("Nessun dato recuperato.")