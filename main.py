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

# ================= UI STYLE =================
st.markdown("""
<style>
.card {background:#161a23;border-radius:14px;padding:18px;margin-bottom:18px;
box-shadow:0 6px 20px rgba(0,0,0,0.35)}
.kpi {font-size:30px;font-weight:700}
.kpi-label {color:#9aa4b2;font-size:13px}
.green {color:#00c853}
.red {color:#ff5252}
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

if "add_mode" not in st.session_state:
    st.session_state.add_mode = True

# ================= HELPERS =================
def fetch_price(symbol, period="2d"):
    if not symbol:
        return None
    df = yf.download(symbol, period=period, progress=False)
    return None if df.empty else float(df["Close"].iloc[-1])

def fetch_series(symbol, start, end):
    df = yf.download(symbol, start=start, end=end, progress=False)
    return None if df.empty else df["Close"]

# ================= HEADER =================
st.markdown("## 📈 Portfolio Tracker")

# ================= PORTFOLIO ENGINE =================
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
            st.warning(f"No data for {s['Stock']}")
            st.stop()

        close = close.reindex(dates).ffill().dropna()
        if len(close) < 2:
            st.warning(f"Not enough data for {s['Stock']}")
            st.stop()

        qty = int(s["Qty"])
        buy = float(s["Buy Price"])

        invested = qty * buy
        current = qty * float(close.iloc[-1])

        table_rows.append([
            s["Stock"], qty, buy,
            float(close.iloc[-1]),
            invested, current,
            current - invested,
            (current / invested - 1) * 100
        ])

        portfolio_series.append(close * qty)
        invested_total += invested

    portfolio_value = pd.concat(portfolio_series, axis=1).sum(axis=1).dropna()

    if len(portfolio_value) < 2:
        st.warning("Not enough aligned data")
        st.stop()

    # Align benchmark properly (THIS FIXES NIFTY CHART)
    nifty = nifty.reindex(portfolio_value.index).ffill()

    port_ret = (portfolio_value / portfolio_value.iloc[0] - 1) * 100
    nifty_ret = (nifty / nifty.iloc[0] - 1) * 100

    # ================= KPIs =================
    pl = portfolio_value.iloc[-1] - invested_total
    pl_pct = (portfolio_value.iloc[-1]/invested_total - 1)*100
    day_pl = portfolio_value.iloc[-1] - portfolio_value.iloc[-2]
    day_pct = (portfolio_value.iloc[-1]/portfolio_value.iloc[-2] - 1)*100

    st.markdown('<div class="card">', unsafe_allow_html=True)
    c1,c2,c3,c4 = st.columns(4)
    c1.markdown(f'<div class="kpi">₹{portfolio_value.iloc[-1]:,.0f}</div><div class="kpi-label">Portfolio</div>', unsafe_allow_html=True)
    c2.markdown(f'<div class="kpi {"green" if pl>=0 else "red"}">₹{pl:,.0f}</div><div class="kpi-label">Total P/L ({pl_pct:.2f}%)</div>', unsafe_allow_html=True)
    c3.markdown(f'<div class="kpi {"green" if day_pl>=0 else "red"}">₹{day_pl:,.0f}</div><div class="kpi-label">1D ({day_pct:.2f}%)</div>', unsafe_allow_html=True)
    c4.markdown(f'<div class="kpi">{"+" if nifty_ret.iloc[-1]>=0 else ""}{nifty_ret.iloc[-1]:.2f}%</div><div class="kpi-label">NIFTY</div>', unsafe_allow_html=True)
    st.markdown('</div>', unsafe_allow_html=True)

    # ================= CHART =================
    fig = go.Figure()
    fig.add_trace(go.Scatter(x=port_ret.index, y=port_ret, name="Portfolio %", line=dict(width=3)))
    fig.add_trace(go.Scatter(x=nifty_ret.index, y=nifty_ret, name="NIFTY %", line=dict(dash="dash")))
    fig.update_layout(template="plotly_dark", hovermode="x unified", height=450)
    st.plotly_chart(fig, use_container_width=True)

    # ================= TABLE =================
    df = pd.DataFrame(table_rows, columns=[
        "Stock","Qty","Buy Price","CMP","Invested","Current","P/L","P/L %"
    ])

    st.markdown('<div class="card">', unsafe_allow_html=True)
    st.dataframe(
        df,
        use_container_width=True,
        column_config={
            "Buy Price": st.column_config.NumberColumn("Buy Price (₹)", format="₹%.2f"),
            "CMP": st.column_config.NumberColumn("CMP (₹)", format="₹%.2f"),
            "Invested": st.column_config.NumberColumn("Invested (₹)", format="₹%,.0f"),
            "Current": st.column_config.NumberColumn("Current (₹)", format="₹%,.0f"),
            "P/L": st.column_config.NumberColumn("P/L (₹)", format="₹%,.0f"),
            "P/L %": st.column_config.NumberColumn("P/L %", format="%.2f%%"),
        }
    )
    st.markdown('</div>', unsafe_allow_html=True)

# ================= ADD STOCK (BOTTOM, CLEAN UX) =================
st.markdown("---")
st.markdown("### ➕ Add Stock")

c1,c2,c3 = st.columns(3)
with c1:
    stock = st.selectbox("Stock", [""] + list(NIFTY_500.keys()), key="new_stock")
    symbol = NIFTY_500.get(stock)

with c2:
    qty = st.number_input("Quantity", min_value=1, step=1, key="new_qty")

with c3:
    cmp_price = fetch_price(symbol)
    buy_price = st.number_input("Buy Price (₹)", value=cmp_price or 0.0, key="new_price")

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
