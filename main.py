import streamlit as st
import pandas as pd
import yfinance as yf
import plotly.graph_objects as go
from datetime import date, timedelta

st.set_page_config(page_title="Portfolio Tracker", layout="wide")

# ================= CONFIG =================
BENCHMARK = "^NSEI"
NIFTY_500_URL = "https://archives.nseindia.com/content/indices/ind_nifty500list.csv"
PERIOD_MAP = {"5D":5,"1M":21,"6M":126,"1Y":252,"3Y":756}
MONTHS = ["Jan","Feb","Mar","Apr","May","Jun","Jul","Aug","Sep","Oct","Nov","Dec"]

# ================= STYLE =================
st.markdown("""
<style>
.card {background:#161a23;border-radius:14px;padding:18px;margin-bottom:18px;
box-shadow:0 6px 20px rgba(0,0,0,0.35)}
.kpi {font-size:30px;font-weight:700}
.kpi-label {color:#9aa4b2;font-size:13px}
.green {color:#00c853}
.red {color:#ff5252}
.small {font-size:13px;color:#9aa4b2}
</style>
""", unsafe_allow_html=True)

# ================= DATA =================
@st.cache_data
def load_nifty500():
    df = pd.read_csv(NIFTY_500_URL)
    df["Symbol"] = df["Symbol"].astype(str) + ".NS"
    return dict(zip(df["Company Name"], df["Symbol"]))

NIFTY_500 = load_nifty500()

# ================= SESSION =================
if "portfolio" not in st.session_state:
    st.session_state.portfolio = []

# ================= HELPERS =================
def fetch_price(symbol):
    if not symbol:
        return None
    df = yf.download(symbol, period="2d", progress=False)
    return None if df.empty else round(float(df["Close"].iloc[-1]), 2)

def fetch_series(symbol, start, end):
    df = yf.download(symbol, start=start, end=end, progress=False)
    return None if df.empty else df["Close"]

def fetch_52w(symbol):
    df = yf.download(symbol, period="1y", progress=False)
    if df.empty:
        return None, None
    return round(df["High"].max(),2), round(df["Low"].min(),2)

# ================= HEADER =================
st.markdown("## 📈 Portfolio Tracker")

# ================= ENGINE =================
if st.session_state.portfolio:

    period = st.radio("Timeframe", list(PERIOD_MAP.keys()), horizontal=True)

    today = date.today()
    earliest = min(s["Buy Date"] for s in st.session_state.portfolio)
    start = pd.Timestamp(max(earliest, today - timedelta(days=PERIOD_MAP[period]*2)))
    end = pd.Timestamp(today)

    nifty = fetch_series(BENCHMARK, start, end)
    if nifty is None:
        st.warning("NIFTY data unavailable")
        st.stop()

    dates = nifty.index
    portfolio_series = []
    table_rows = []
    invested_total = 0.0

    for s in st.session_state.portfolio:
        close = fetch_series(s["Symbol"], start, end)
        if close is None:
            st.stop()

        close = close.reindex(dates).ffill().dropna()
        qty = int(s["Qty"])
        buy = float(s["Buy Price"])

        invested = round(qty * buy, 2)
        current = round(qty * close.iloc[-1], 2)
        pl = round(current - invested, 2)
        pl_pct = round((current/invested - 1)*100, 2)

        hi52, lo52 = fetch_52w(s["Symbol"])

        table_rows.append([
            s["Stock"], qty, round(buy,2),
            round(close.iloc[-1],2),
            invested, current, pl, pl_pct,
            hi52, lo52
        ])

        portfolio_series.append(close * qty)
        invested_total += invested

    portfolio_value = pd.concat(portfolio_series, axis=1).sum(axis=1).dropna()
    nifty = nifty.reindex(portfolio_value.index).ffill()

    port_ret = (portfolio_value/portfolio_value.iloc[0]-1)*100
    nifty_ret = (nifty/nifty.iloc[0]-1)*100

    port_last = round(float(port_ret.iloc[-1]),2)
    nifty_last = round(float(nifty_ret.iloc[-1]),2)

    # ================= KPIs =================
    pl_total = round(portfolio_value.iloc[-1]-invested_total,2)
    pl_pct_total = round((portfolio_value.iloc[-1]/invested_total-1)*100,2)
    day_pl = round(portfolio_value.iloc[-1]-portfolio_value.iloc[-2],2)
    day_pct = round((portfolio_value.iloc[-1]/portfolio_value.iloc[-2]-1)*100,2)

    st.markdown('<div class="card">', unsafe_allow_html=True)
    c1,c2,c3,c4,c5 = st.columns(5)
    c1.markdown(f'<div class="kpi">₹{portfolio_value.iloc[-1]:,.0f}</div><div class="kpi-label">Value</div>', unsafe_allow_html=True)
    c2.markdown(f'<div class="kpi {"green" if pl_total>=0 else "red"}">₹{pl_total:,.0f}</div><div class="kpi-label">Total P/L</div>', unsafe_allow_html=True)
    c3.markdown(f'<div class="kpi {"green" if pl_pct_total>=0 else "red"}">{pl_pct_total:.2f}%</div><div class="kpi-label">Portfolio %</div>', unsafe_allow_html=True)
    c4.markdown(f'<div class="kpi {"green" if day_pl>=0 else "red"}">₹{day_pl:,.0f}</div><div class="kpi-label">1D</div>', unsafe_allow_html=True)
    c5.markdown(f'<div class="kpi {"green" if nifty_last>=0 else "red"}">{nifty_last:.2f}%</div><div class="kpi-label">NIFTY</div>', unsafe_allow_html=True)
    st.markdown('</div>', unsafe_allow_html=True)

    # ================= CHART =================
    fig = go.Figure()
    fig.add_trace(go.Scatter(x=port_ret.index, y=port_ret, name="Portfolio %", line=dict(width=3)))
    fig.add_trace(go.Scatter(x=nifty_ret.index, y=nifty_ret, name="NIFTY %", line=dict(dash="dash")))
    fig.update_layout(template="plotly_dark", hovermode="x unified", height=450)
    st.plotly_chart(fig, use_container_width=True)

    # ================= TABLE =================
    df = pd.DataFrame(table_rows, columns=[
        "Stock","Qty","Buy Price","CMP","Invested","Current","P/L","P/L %",
        "52W High","52W Low"
    ])

    st.markdown('<div class="card">', unsafe_allow_html=True)
    st.dataframe(
        df,
        use_container_width=True,
        column_config={
            "Buy Price": st.column_config.NumberColumn("Buy Price", format="₹%.2f"),
            "CMP": st.column_config.NumberColumn("CMP", format="₹%.2f"),
            "Invested": st.column_config.NumberColumn("Invested", format="₹%,.0f"),
            "Current": st.column_config.NumberColumn("Current", format="₹%,.0f"),
            "P/L": st.column_config.NumberColumn("P/L", format="₹%,.0f"),
            "P/L %": st.column_config.NumberColumn("P/L %", format="%.2f%%"),
            "52W High": st.column_config.NumberColumn("52W High", format="₹%.2f"),
            "52W Low": st.column_config.NumberColumn("52W Low", format="₹%.2f"),
        }
    )
    st.markdown('</div>', unsafe_allow_html=True)

    # ================= INSIGHTS =================
    best = df.sort_values("P/L %", ascending=False).iloc[0]
    worst = df.sort_values("P/L %").iloc[0]

    st.markdown('<div class="card">', unsafe_allow_html=True)
    st.markdown("### 🔍 Insights")
    st.markdown(f"- **Best performer:** {best['Stock']} ({best['P/L %']}%)")
    st.markdown(f"- **Worst performer:** {worst['Stock']} ({worst['P/L %']}%)")
    st.markdown(f"- **Portfolio vs NIFTY:** {port_last-nifty_last:+.2f}% outperformance")
    st.markdown('</div>', unsafe_allow_html=True)

# ================= ADD STOCK =================
expanded = len(st.session_state.portfolio) == 0
with st.expander("➕ Add Stock", expanded=expanded):

    c1,c2,c3 = st.columns(3)
    with c1:
        stock = st.selectbox("Stock", [""] + list(NIFTY_500.keys()))
        symbol = NIFTY_500.get(stock)
    with c2:
        qty = st.number_input("Quantity", min_value=1, step=1)
    with c3:
        cmp = fetch_price(symbol)
        buy_price = st.number_input("Buy Price (₹)", value=cmp or 0.0)

    d1,d2,d3 = st.columns(3)
    today = date.today()
    with d1:
        day = st.selectbox("Day", list(range(1,32)), index=today.day-1)
    with d2:
        month = st.selectbox("Month", MONTHS, index=today.month-1)
    with d3:
        year = st.selectbox("Year", list(range(2022,today.year+1)),
                            index=len(range(2022,today.year+1))-1)

    if st.button("Add to Portfolio", use_container_width=True):
        if stock and buy_price > 0:
            st.session_state.portfolio.append({
                "Stock": stock,
                "Symbol": symbol,
                "Qty": int(qty),
                "Buy Price": float(buy_price),
                "Buy Date": date(year, MONTHS.index(month)+1, day)
            })
            st.rerun()
