import streamlit as st
import pandas as pd
import yfinance as yf
import plotly.graph_objects as go
from datetime import date, timedelta

st.set_page_config(page_title="Portfolio Tracker", layout="wide")

# ================= CONSTANTS =================
NIFTY_500_URL = "https://archives.nseindia.com/content/indices/ind_nifty500list.csv"
BENCHMARK = "^NSEI"

PERIOD_MAP = {"5D":5,"1M":21,"6M":126,"1Y":252,"3Y":756}
MONTHS = ["January","February","March","April","May","June",
          "July","August","September","October","November","December"]

# ================= DARK UI =================
st.markdown("""
<style>
.card{background:#161a23;border-radius:14px;padding:18px;margin-bottom:18px;
box-shadow:0 6px 20px rgba(0,0,0,0.35)}
.kpi{font-size:28px;font-weight:700}
.kpi-label{color:#9aa4b2;font-size:13px}
.green{color:#00c853}
.red{color:#ff5252}
</style>
""", unsafe_allow_html=True)

# ================= DATA =================
@st.cache_data
def load_nifty_500():
    df = pd.read_csv(NIFTY_500_URL)
    df["Symbol"] = df["Symbol"].astype(str) + ".NS"
    return dict(zip(df["Company Name"], df["Symbol"]))

NIFTY_500 = load_nifty_500()

if "portfolio" not in st.session_state:
    st.session_state.portfolio = []

# ================= HELPERS =================
def fetch_cmp(symbol):
    df = yf.download(symbol, period="2d", progress=False)
    return None if df.empty else float(df["Close"].iloc[-1])

def fetch_history(symbol, start, end):
    df = yf.download(symbol, start=start, end=end, progress=False)
    return None if df.empty else df["Close"]

# ================= HEADER =================
st.markdown("## 📈 Portfolio Tracker")

# ================= ADD STOCK =================
with st.expander("➕ Add Stock", expanded=False):

    stock = st.selectbox("Stock", [""] + list(NIFTY_500.keys()), key="stock")
    symbol = NIFTY_500.get(stock)

    qty = st.number_input("Quantity", min_value=1, step=1, key="qty")

    cmp_price = fetch_cmp(symbol) if symbol else None
    buy_price = st.number_input("Buy Price (₹)", value=cmp_price or 0.0, key="price")

    today = date.today()
    d = st.selectbox("Day", list(range(1,32)), index=today.day-1)
    m = st.selectbox("Month", MONTHS, index=today.month-1)
    y = st.selectbox("Year", list(range(2022,today.year+1)),
                     index=len(range(2022,today.year+1))-1)

    if st.button("Add to Portfolio", use_container_width=True):
        if stock and buy_price > 0:
            st.session_state.portfolio.append({
                "Stock": stock,
                "Symbol": symbol,
                "Qty": int(qty),
                "Buy Price": float(buy_price),
                "Buy Date": date(y, MONTHS.index(m)+1, d)
            })
            st.experimental_rerun()

# ================= STOP IF EMPTY =================
if not st.session_state.portfolio:
    st.info("Add a stock to start tracking.")
    st.stop()

# ================= TIMEFRAME =================
period = st.radio("Timeframe", list(PERIOD_MAP.keys()), horizontal=True)

today = date.today()
earliest_buy = min(s["Buy Date"] for s in st.session_state.portfolio)
start = pd.Timestamp(max(earliest_buy, today - timedelta(days=PERIOD_MAP[period]*2)))
end = pd.Timestamp(today)

# ================= ENGINE =================
nifty = fetch_history(BENCHMARK, start, end)
if nifty is None or len(nifty) < 2:
    st.warning("NIFTY data not available.")
    st.stop()

dates = nifty.index
series_list, rows = [], []
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

    qty, buy = s["Qty"], s["Buy Price"]
    invested = qty * buy
    current = qty * close.iloc[-1]

    rows.append([
        s["Stock"], qty, buy, close.iloc[-1],
        invested, current,
        current-invested,
        (current/invested-1)*100
    ])

    series_list.append(close * qty)
    invested_total += invested

portfolio_value = pd.concat(series_list, axis=1).sum(axis=1).dropna()
if len(portfolio_value) < 2:
    st.warning("Not enough aligned market data.")
    st.stop()

# ================= KPIs =================
pl_total = portfolio_value.iloc[-1] - invested_total
pl_pct = (portfolio_value.iloc[-1]/invested_total - 1)*100
day_change = portfolio_value.iloc[-1] - portfolio_value.iloc[-2]
day_pct = (portfolio_value.iloc[-1]/portfolio_value.iloc[-2] - 1)*100

nifty = nifty.reindex(portfolio_value.index).ffill()
nifty_ret = (nifty/nifty.iloc[0] - 1)*100
nifty_last = float(nifty_ret.iloc[-1])

st.markdown('<div class="card">', unsafe_allow_html=True)
c1,c2,c3,c4 = st.columns(4)
c1.markdown(f'<div class="kpi">₹{portfolio_value.iloc[-1]:,.0f}</div><div class="kpi-label">Portfolio</div>', unsafe_allow_html=True)
c2.markdown(f'<div class="kpi {"green" if pl_total>=0 else "red"}">₹{pl_total:,.0f}</div><div class="kpi-label">Total P/L ({pl_pct:.2f}%)</div>', unsafe_allow_html=True)
c3.markdown(f'<div class="kpi {"green" if day_change>=0 else "red"}">₹{day_change:,.0f}</div><div class="kpi-label">1D ({day_pct:.2f}%)</div>', unsafe_allow_html=True)
c4.markdown(f'<div class="kpi {"green" if nifty_last>=0 else "red"}">{nifty_last:.2f}%</div><div class="kpi-label">NIFTY</div>', unsafe_allow_html=True)
st.markdown('</div>', unsafe_allow_html=True)

# ================= CHART =================
fig = go.Figure()
fig.add_trace(go.Scatter(x=portfolio_value.index, y=(portfolio_value/portfolio_value.iloc[0]-1)*100,
                         name="Portfolio %", line=dict(width=3)))
fig.add_trace(go.Scatter(x=nifty_ret.index, y=nifty_ret, name="NIFTY %",
                         line=dict(dash="dash")))
fig.update_layout(template="plotly_dark", hovermode="x unified", height=450)
st.plotly_chart(fig, use_container_width=True)

# ================= TABLE (STREAMLIT NATIVE) =================
df = pd.DataFrame(rows, columns=[
    "Stock","Qty","Buy Price","CMP","Invested","Current","P/L","P/L %"
])

st.markdown('<div class="card">', unsafe_allow_html=True)
st.markdown("### 📋 Portfolio")

st.dataframe(
    df,
    use_container_width=True,
    column_config={
        "Buy Price": st.column_config.NumberColumn("Buy Price (₹)", format="₹%.2f"),
        "CMP": st.column_config.NumberColumn("CMP (₹)", format="₹%.2f"),
        "Invested": st.column_config.NumberColumn("Invested (₹)", format="₹%,.0f"),
        "Current": st.column_config.NumberColumn("Current Value (₹)", format="₹%,.0f"),
        "P/L": st.column_config.NumberColumn("P/L (₹)", format="₹%,.0f"),
        "P/L %": st.column_config.NumberColumn("P/L %", format="%.2f%%"),
    }
)
st.markdown('</div>', unsafe_allow_html=True)
