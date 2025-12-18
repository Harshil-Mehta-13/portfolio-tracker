    import streamlit as st
import pandas as pd
import yfinance as yf
import plotly.graph_objects as go
from datetime import date, timedelta

# ================= PAGE CONFIG =================
st.set_page_config(
    page_title="Portfolio Tracker",
    layout="wide",
    initial_sidebar_state="collapsed"
)

# ================= CONSTANTS =================
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

# ================= DATA =================
@st.cache_data
def load_nifty_500():
    df = pd.read_csv(NIFTY_500_URL)
    df["Symbol"] = df["Symbol"].astype(str) + ".NS"
    return dict(zip(df["Company Name"], df["Symbol"]))

NIFTY_500 = load_nifty_500()

# ================= SESSION =================
if "portfolio" not in st.session_state:
    st.session_state.portfolio = []

if "dark_mode" not in st.session_state:
    st.session_state.dark_mode = False

# ================= HELPERS =================
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

# ================= HEADER =================
col1, col2 = st.columns([6,1])
with col1:
    st.markdown("## 📈 Portfolio Tracker")
with col2:
    st.session_state.dark_mode = st.toggle("🌙", value=st.session_state.dark_mode)

# ================= ADD STOCK =================
with st.expander("➕ Add Stock", expanded=False):
    c1, c2, c3, c4 = st.columns([4,1,2,2])

    with c1:
        stock = st.selectbox(
            "Stock",
            options=[""] + list(NIFTY_500.keys()),
            index=0
        )

    symbol = NIFTY_500.get(stock)

    with c2:
        qty = st.number_input("Qty", min_value=1, step=1)

    cmp_price = fetch_cmp(symbol) if symbol else None

    with c3:
        buy_price = st.number_input(
            "Buy Price (₹)",
            value=cmp_price if cmp_price else 0.0,
            step=0.1
        )

    today = date.today()
    with c4:
        d = st.selectbox("Day", list(range(1,32)), index=today.day-1)
        m = st.selectbox("Month", MONTHS, index=today.month-1)
        y = st.selectbox(
            "Year",
            list(range(2022, today.year+1)),
            index=len(range(2022, today.year+1))-1
        )

    if st.button("Add to Portfolio", use_container_width=True):
        if stock and buy_price > 0:
            st.session_state.portfolio.append({
                "Stock": stock,
                "Symbol": symbol,
                "Qty": int(qty),
                "Buy Price": float(buy_price),
                "Buy Date": date(y, MONTHS.index(m)+1, d)
            })
            st.success(f"{stock} added to portfolio")
        else:
            st.warning("Please select a stock and valid buy price")

# ================= STOP IF EMPTY =================
if not st.session_state.portfolio:
    st.info("Add a stock to start tracking your portfolio.")
    st.stop()

# ================= TIMEFRAME =================
period = st.radio(
    "Timeframe",
    options=list(PERIOD_MAP.keys()),
    horizontal=True
)

# ================= ENGINE =================
today = date.today()
earliest_buy = min(s["Buy Date"] for s in st.session_state.portfolio)
start_date = max(earliest_buy, today - timedelta(days=PERIOD_MAP[period]*2))

start = pd.Timestamp(start_date)
end = pd.Timestamp(today)

# Fetch benchmark
nifty = fetch_history(BENCHMARK, start, end)
if nifty is None or len(nifty) < 2:
    st.error("Benchmark data not available.")
    st.stop()

dates = nifty.index

# 🔐 BUILD PORTFOLIO VALUE SAFELY
value_series = []
rows = []
invested_total = 0.0

for s in st.session_state.portfolio:
    close = fetch_history(s["Symbol"], start, end)
    if close is None:
        st.error(f"Data not available for {s['Stock']}")
        st.stop()

    close = close.reindex(dates).ffill().dropna()
    if len(close) < 2:
        st.warning(f"Not enough market data yet for {s['Stock']}")
        st.stop()

    qty = s["Qty"]
    buy = s["Buy Price"]

    invested = qty * buy
    current = qty * close.iloc[-1]
    day_pl = qty * (close.iloc[-1] - close.iloc[-2])
    day_pct = (close.iloc[-1] / close.iloc[-2] - 1) * 100

    rows.append([
        s["Stock"], qty, buy, close.iloc[-1],
        invested, current,
        current - invested,
        (current / invested - 1) * 100,
        day_pl, day_pct
    ])

    value_series.append(close * qty)
    invested_total += invested

# 🔐 ALIGN & SUM
portfolio_value = pd.concat(value_series, axis=1).sum(axis=1)
portfolio_value = portfolio_value.dropna()

if len(portfolio_value) < 2:
    st.warning("Not enough aligned market data to compute portfolio performance yet.")
    st.stop()

base_value = portfolio_value.iloc[0]

port_ret = (portfolio_value / base_value - 1) * 100
nifty = nifty.reindex(portfolio_value.index).ffill()
nifty_ret = (nifty / nifty.iloc[0] - 1) * 100

# ================= KPIs =================
c1, c2, c3, c4 = st.columns(4)

c1.metric("Portfolio Value", f"₹{portfolio_value.iloc[-1]:,.0f}")
c2.metric(
    "Total P/L",
    f"₹{portfolio_value.iloc[-1]-invested_total:,.0f}",
    f"{(portfolio_value.iloc[-1]/invested_total-1)*100:.2f}%"
)
c3.metric(
    "1D Change",
    f"₹{portfolio_value.iloc[-1]-portfolio_value.iloc[-2]:,.0f}",
    f"{(portfolio_value.iloc[-1]/portfolio_value.iloc[-2]-1)*100:.2f}%"
)
c4.metric("NIFTY", f"{nifty_ret.iloc[-1]:.2f}%")

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
    line=dict(width=2, dash="dash")
))

fig.update_layout(
    hovermode="x unified",
    xaxis=dict(showspikes=True, spikemode="across"),
    yaxis_title="% Return",
    height=480,
    template="plotly_dark" if st.session_state.dark_mode else "plotly_white"
)

st.plotly_chart(fig, use_container_width=True)

# ================= TABLES =================
table = pd.DataFrame(rows, columns=[
    "Stock","Qty","Buy Price","CMP",
    "Invested","Current",
    "Total P/L","Total P/L %",
    "1D P/L","1D %"
])

gainers = table[table["1D %"] > 0].sort_values("1D %", ascending=False).head(5)
losers = table[table["1D %"] < 0].sort_values("1D %").head(5)

st.markdown("### 📋 Portfolio")
st.dataframe(table, use_container_width=True)

col1, col2 = st.columns(2)
with col1:
    st.markdown("### 🔼 Top Gainers")
    st.dataframe(gainers, use_container_width=True)
with col2:
    st.markdown("### 🔽 Top Losers")
    st.dataframe(losers, use_container_width=True)
