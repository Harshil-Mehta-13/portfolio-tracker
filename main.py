import streamlit as st
import pandas as pd
import yfinance as yf
import plotly.graph_objects as go
from datetime import date, timedelta

st.set_page_config(page_title="Portfolio Tracker", layout="wide")

NIFTY_500_URL = "https://archives.nseindia.com/content/indices/ind_nifty500list.csv"
BENCHMARK = "^NSEI"

PERIOD_MAP = {
    "5D": 5,
    "1M": 21,
    "6M": 126,
    "1Y": 252,
    "3Y": 756
}

MONTHS = [
    "January","February","March","April","May","June",
    "July","August","September","October","November","December"
]

@st.cache_data
def load_nifty_500():
    df = pd.read_csv(NIFTY_500_URL)
    df["Symbol"] = df["Symbol"].astype(str) + ".NS"
    return dict(zip(df["Company Name"], df["Symbol"]))

NIFTY_500 = load_nifty_500()

if "portfolio" not in st.session_state:
    st.session_state.portfolio = []

if "dark_mode" not in st.session_state:
    st.session_state.dark_mode = False

def fetch_cmp(symbol):
    df = yf.download(symbol, period="2d", progress=False)
    if df.empty:
        return None
    return float(df["Close"].iloc[-1])

def fetch_history(symbol, start, end):
    df = yf.download(symbol, start=start, end=end, progress=False)
    if df.empty:
        return None
    return df["Close"]

st.markdown("## 📈 Portfolio Tracker")

with st.expander("➕ Add Stock", expanded=False):
    c1, c2, c3, c4 = st.columns([4,1,2,2])

    stock = c1.selectbox("Stock", [""] + list(NIFTY_500.keys()))
    symbol = NIFTY_500.get(stock)

    qty = c2.number_input("Qty", min_value=1, step=1)

    cmp_price = fetch_cmp(symbol) if symbol else None
    buy_price = c3.number_input("Buy Price (₹)", value=cmp_price or 0.0)

    today = date.today()
    d = c4.selectbox("Day", list(range(1,32)), index=today.day-1)
    m = c4.selectbox("Month", MONTHS, index=today.month-1)
    y = c4.selectbox("Year", list(range(2022, today.year+1)),
                     index=len(range(2022, today.year+1))-1)

    if st.button("Add to Portfolio"):
        if stock and buy_price > 0:
            st.session_state.portfolio.append({
                "Stock": stock,
                "Symbol": symbol,
                "Qty": int(qty),
                "Buy Price": float(buy_price),
                "Buy Date": date(y, MONTHS.index(m)+1, d)
            })
            st.success(f"{stock} added")
        else:
            st.warning("Please enter valid details")

if not st.session_state.portfolio:
    st.info("Add a stock to start tracking.")
    st.stop()

period = st.radio("Timeframe", list(PERIOD_MAP.keys()), horizontal=True)

today = date.today()
earliest_buy = min(s["Buy Date"] for s in st.session_state.portfolio)
start_date = max(earliest_buy, today - timedelta(days=PERIOD_MAP[period]*2))

start = pd.Timestamp(start_date)
end = pd.Timestamp(today)

nifty = fetch_history(BENCHMARK, start, end)
if nifty is None or len(nifty) < 2:
    st.warning("Benchmark data not available yet.")
    st.stop()

dates = nifty.index
value_series = []
rows = []
invested_total = 0.0

for s in st.session_state.portfolio:
    close = fetch_history(s["Symbol"], start, end)
    if close is None:
        st.warning(f"No data for {s['Stock']}")
        st.stop()

    close = close.reindex(dates).ffill().dropna()
    if len(close) < 2:
        st.warning(f"Not enough data for {s['Stock']}")
        st.stop()

    qty = s["Qty"]
    buy = s["Buy Price"]

    invested = qty * buy
    current = qty * close.iloc[-1]

    rows.append([
        s["Stock"], qty, buy, close.iloc[-1],
        invested, current,
        current - invested,
        (current / invested - 1) * 100
    ])

    value_series.append(close * qty)
    invested_total += invested

portfolio_value = pd.concat(value_series, axis=1).sum(axis=1).dropna()

if len(portfolio_value) < 2:
    st.warning("Not enough aligned market data yet.")
    st.stop()

base_value = portfolio_value.iloc[0]
port_ret = (portfolio_value / base_value - 1) * 100

nifty = nifty.reindex(portfolio_value.index).ffill()
nifty_ret = (nifty / nifty.iloc[0] - 1) * 100

fig = go.Figure()
fig.add_trace(go.Scatter(x=port_ret.index, y=port_ret, name="Portfolio %"))
fig.add_trace(go.Scatter(x=nifty_ret.index, y=nifty_ret, name="NIFTY %", line=dict(dash="dash")))
fig.update_layout(hovermode="x unified", height=450)

st.plotly_chart(fig, use_container_width=True)

st.dataframe(pd.DataFrame(rows, columns=[
    "Stock","Qty","Buy Price","CMP","Invested","Current","P/L","P/L %"
]), use_container_width=True)
