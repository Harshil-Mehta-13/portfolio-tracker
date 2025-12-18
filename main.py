import streamlit as st
import pandas as pd
import yfinance as yf
import plotly.graph_objects as go
from datetime import date, timedelta

# ================= PAGE =================
st.set_page_config(page_title="Portfolio Tracker", layout="wide")

# ================= CONSTANTS =================
BENCHMARK = "NIFTYBEES.NS"  # stable benchmark
PERIOD_MAP = {"5D":5,"1M":21,"6M":126,"1Y":252,"3Y":756}
MONTHS = ["Jan","Feb","Mar","Apr","May","Jun","Jul","Aug","Sep","Oct","Nov","Dec"]

# ================= SESSION INIT =================
if "portfolio" not in st.session_state:
    st.session_state.portfolio = []

# ================= MIGRATION (CRITICAL FIX) =================
def normalize_portfolio():
    fixed = []
    for s in st.session_state.portfolio:
        fixed.append({
            "symbol": s.get("Symbol") or s.get("symbol"),
            "qty": int(s.get("Qty") or s.get("qty")),
            "buy_price": float(s.get("Buy Price") or s.get("Buy") or s.get("buy_price")),
            "buy_date": s.get("Buy Date") or s.get("Date") or s.get("buy_date"),
        })
    st.session_state.portfolio = fixed

normalize_portfolio()

# ================= HELPERS =================
def fetch_price(symbol):
    df = yf.download(symbol, period="2d", progress=False)
    return None if df.empty else float(df["Close"].iloc[-1])

def fetch_series(symbol, start, end):
    df = yf.download(symbol, start=start, end=end, progress=False)
    return None if df.empty else df["Close"]

# ================= HEADER =================
st.title("📈 Portfolio Tracker")

# ================= ADD STOCK =================
with st.expander("➕ Add Stock", expanded=len(st.session_state.portfolio)==0):

    symbol = st.text_input("Stock Symbol (e.g. INFY.NS)")
    qty = st.number_input("Quantity", min_value=1, step=1)

    cmp = fetch_price(symbol) if symbol else None
    buy_price = st.number_input(
        "Buy Price (₹)",
        value=round(cmp,2) if cmp else 0.0
    )

    d1,d2,d3 = st.columns(3)
    today = date.today()
    with d1:
        day = st.selectbox("Day", list(range(1,32)), index=today.day-1)
    with d2:
        month = st.selectbox("Month", MONTHS, index=today.month-1)
    with d3:
        year = st.selectbox(
            "Year",
            list(range(2020, today.year+1)),
            index=len(range(2020, today.year+1))-1
        )

    if st.button("Add to Portfolio"):
        if symbol and buy_price > 0:
            st.session_state.portfolio.append({
                "symbol": symbol,
                "qty": int(qty),
                "buy_price": float(buy_price),
                "buy_date": date(year, MONTHS.index(month)+1, day)
            })
            st.rerun()

# ================= STOP IF EMPTY =================
if not st.session_state.portfolio:
    st.info("Add a stock to start tracking.")
    st.stop()

# ================= TIMEFRAME =================
period = st.radio("Timeframe", list(PERIOD_MAP.keys()), horizontal=True)

# ================= ENGINE =================
today = date.today()
earliest = min(s["buy_date"] for s in st.session_state.portfolio)

start = pd.Timestamp(max(
    earliest,
    today - timedelta(days=PERIOD_MAP[period]*2)
))
end = pd.Timestamp(today)

# Portfolio series
lines = []
invested = 0.0

for s in st.session_state.portfolio:
    close = fetch_series(s["symbol"], start, end)
    if close is None:
        st.error(f"No data for {s['symbol']}")
        st.stop()

    close = close.dropna()
    lines.append(close * s["qty"])
    invested += s["qty"] * s["buy_price"]

portfolio_value = pd.concat(lines, axis=1).sum(axis=1)

# ================= BENCHMARK =================
nifty = fetch_series(BENCHMARK, start, end)
if nifty is None:
    st.error("Benchmark data unavailable")
    st.stop()

# ALIGN DATES
common = portfolio_value.index.intersection(nifty.index)
portfolio_value = portfolio_value.loc[common]
nifty = nifty.loc[common]

if len(portfolio_value) < 2:
    st.warning("Not enough data to compare.")
    st.stop()

# ================= RETURNS =================
port_ret = (portfolio_value / portfolio_value.iloc[0] - 1) * 100
nifty_ret = (nifty / nifty.iloc[0] - 1) * 100

# ================= KPIs =================
c1,c2,c3,c4 = st.columns(4)
c1.metric("Value", f"₹{portfolio_value.iloc[-1]:,.0f}")
c2.metric("Total P/L", f"₹{portfolio_value.iloc[-1]-invested:,.0f}")
c3.metric("Portfolio %", f"{port_ret.iloc[-1]:.2f}%")
c4.metric("NIFTY %", f"{nifty_ret.iloc[-1]:.2f}%")

# ================= CHART =================
fig = go.Figure()
fig.add_trace(go.Scatter(
    x=port_ret.index,
    y=port_ret,
    name="Portfolio %",
    line=dict(width=3)
))
fig.add_trace(go.Scatter(
    x=nifty_ret.index,
    y=nifty_ret,
    name="NIFTY %",
    line=dict(dash="dash")
))
fig.update_layout(
    template="plotly_dark",
    hovermode="x unified",
    height=450
)
st.plotly_chart(fig, use_container_width=True)
