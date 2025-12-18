import streamlit as st
import pandas as pd
import yfinance as yf
import plotly.graph_objects as go
from datetime import date, timedelta

# ================= PAGE =================
st.set_page_config(page_title="Portfolio Tracker", layout="wide")

# ================= CONSTANTS =================
BENCHMARK = "NIFTYBEES.NS"   # ✅ FIXED
PERIOD_MAP = {"5D": 5, "1M": 21, "6M": 126, "1Y": 252, "3Y": 756}
MONTHS = ["Jan","Feb","Mar","Apr","May","Jun","Jul","Aug","Sep","Oct","Nov","Dec"]

# ================= SESSION =================
if "portfolio" not in st.session_state:
    st.session_state.portfolio = []

# ================= HELPERS =================
def price(symbol, period="2d"):
    df = yf.download(symbol, period=period, progress=False)
    if df.empty:
        return None
    return float(df["Close"].iloc[-1])

def series(symbol, start, end):
    df = yf.download(symbol, start=start, end=end, progress=False)
    if df.empty:
        return None
    return df["Close"]

# ================= HEADER =================
st.title("📈 Portfolio Tracker")

# ================= ADD STOCK =================
with st.expander("➕ Add Stock", expanded=len(st.session_state.portfolio)==0):
    stock = st.text_input("Stock symbol (example: INFY.NS)")
    qty = st.number_input("Quantity", min_value=1, step=1)
    cmp = price(stock) if stock else 0.0
    buy = st.number_input("Buy Price (₹)", value=round(cmp,2) if cmp else 0.0)

    d1, d2, d3 = st.columns(3)
    today = date.today()
    with d1: day = st.selectbox("Day", list(range(1,32)), index=today.day-1)
    with d2: month = st.selectbox("Month", MONTHS, index=today.month-1)
    with d3: year = st.selectbox("Year", list(range(2020,today.year+1)),
                                  index=len(range(2020,today.year+1))-1)

    if st.button("Add to Portfolio"):
        if stock and buy>0:
            st.session_state.portfolio.append({
                "Symbol": stock,
                "Qty": qty,
                "Buy": buy,
                "Date": date(year, MONTHS.index(month)+1, day)
            })
            st.rerun()

# ================= PORTFOLIO =================
if not st.session_state.portfolio:
    st.info("Add at least one stock to see portfolio analytics.")
    st.stop()

period = st.radio("Timeframe", list(PERIOD_MAP.keys()), horizontal=True)

# ================= ENGINE =================
today = date.today()

# ✅ FIX: defensive date extraction (ONLY CHANGE)
def get_date(s):
    return s.get("Date")

dates = [get_date(s) for s in st.session_state.portfolio if get_date(s) is not None]
earliest = min(dates)

start = pd.Timestamp(max(earliest, today - timedelta(days=PERIOD_MAP[period]*2)))
end = pd.Timestamp(today)

portfolio_lines = []
invested = 0

for s in st.session_state.portfolio:
    srs = series(s["Symbol"], start, end)
    if srs is None:
        st.error(f"No data for {s['Symbol']}")
        st.stop()
    srs = srs.dropna()
    portfolio_lines.append(srs * s["Qty"])
    invested += s["Qty"] * s["Buy"]

portfolio_value = pd.concat(portfolio_lines, axis=1).sum(axis=1)

# ================= NIFTY =================
nifty = series(BENCHMARK, start, end)
if nifty is None:
    st.error("NIFTY data unavailable")
    st.stop()

# ✅ ALIGN DATES PROPERLY
common_dates = portfolio_value.index.intersection(nifty.index)
portfolio_value = portfolio_value.loc[common_dates]
nifty = nifty.loc[common_dates]

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
    x=port_ret.index, y=port_ret,
    name="Portfolio %",
    line=dict(width=3)
))
fig.add_trace(go.Scatter(
    x=nifty_ret.index, y=nifty_ret,
    name="NIFTY %",
    line=dict(dash="dash")
))
fig.update_layout(
    template="plotly_dark",
    hovermode="x unified",
    height=450,
    yaxis_title="% Return"
)
st.plotly_chart(fig, use_container_width=True)
