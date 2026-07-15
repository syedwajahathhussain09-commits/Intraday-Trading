import streamlit as st
import streamlit.components.v1 as components
import pandas as pd
import yfinance as yf
import matplotlib.pyplot as plt

# 1. Page Configuration
st.set_page_config(page_title="Multi-Timeframe Intraday Dashboard", layout="wide")
st.title("📈 Multi-Timeframe Trading Dashboard")

# 2. Helper functions for Ticker and Timeframe mapping
def format_tv_symbol(ticker_symbol):
    if ticker_symbol.endswith(".NS"):
        return f"NSE:{ticker_symbol.replace('.NS', '')}"
    if ticker_symbol in ["AAPL", "MSFT", "TSLA", "NVDA", "AMZN", "GOOGL", "META", "NFLX"]:
        return f"NASDAQ:{ticker_symbol}"
    if ticker_symbol in ["KO", "BRK-B"]:
        return f"NYSE:{ticker_symbol}"
    return ticker_symbol

# Map Streamlit selections to (yfinance_interval, yfinance_period, tradingview_interval)
TIMEFRAME_MAP = {
    "5 Min": {"yf_interval": "5m", "yf_period": "5d", "tv_interval": "5", "resample": None},
    "15 Min": {"yf_interval": "15m", "yf_period": "1mo", "tv_interval": "15", "resample": None},
    "30 Min": {"yf_interval": "30m", "yf_period": "1mo", "tv_interval": "30", "resample": None},
    "1 Hour": {"yf_interval": "60m", "yf_period": "2y", "tv_interval": "60", "resample": None},
    "4 Hour": {"yf_interval": "60m", "yf_period": "2y", "tv_interval": "240", "resample": "4H"},
    "1 Day": {"yf_interval": "1d", "yf_period": "5y", "tv_interval": "D", "resample": None},
    "1 Month": {"yf_interval": "1mo", "yf_period": "max", "tv_interval": "M", "resample": None}
}

# 3. Comprehensive Stock Directory
STOCK_DIRECTORY = {
    "Apple Inc. (AAPL)": "AAPL",
    "Microsoft Corp. (MSFT)": "MSFT",
    "Tesla Inc. (TSLA)": "TSLA",
    "NVIDIA Corp. (NVDA)": "NVDA",
    "Amazon.com Inc. (AMZN)": "AMZN",
    "Alphabet Inc. / Google (GOOGL)": "GOOGL",
    "Meta Platforms (META)": "META",
    "Netflix Inc. (NFLX)": "NFLX",
    "Reliance Industries Ltd. (RELIANCE.NS)": "RELIANCE.NS",
    "Tata Consultancy Services (TCS.NS)": "TCS.NS",
    "Infosys Ltd. (INFY.NS)": "INFY.NS",
    "HDFC Bank Ltd. (HDFCBANK.NS)": "HDFCBANK.NS",
    "State Bank of India (SBIN.NS)": "SBIN.NS",
}

# 4. Sidebar Controls
st.sidebar.header("Configuration")

# Stock Search
search_query = st.sidebar.selectbox(
    "Search Stock Name or Ticker:",
    options=list(STOCK_DIRECTORY.keys()),
    index=0
)
ticker = STOCK_DIRECTORY[search_query]

# Custom override box
custom_ticker = st.sidebar.text_input("Or enter any raw ticker symbol manually:")
if custom_ticker:
    ticker = custom_ticker.strip().upper()

# Timeframe Selector
selected_tf = st.sidebar.selectbox(
    "Select Chart Timeframe:",
    options=list(TIMEFRAME_MAP.keys()),
    index=0  # Defaults to 5 Min
)

tf_settings = TIMEFRAME_MAP[selected_tf]

# Strategy Parameters
fast_span = st.sidebar.slider("Fast EMA", min_value=3, max_value=20, value=9)
slow_span = st.sidebar.slider("Slow EMA", min_value=10, max_value=50, value=21)
rsi_period = st.sidebar.slider("RSI Period", min_value=5, max_value=30, value=14)

# Get formatted ticker for TV
tv_symbol = format_tv_symbol(ticker)

# Create Tabs
tab1, tab2 = st.tabs(["📺 Live TradingView Chart", "📊 Python EMA/RSI Signals"])

# --- TAB 1: Live Interactive TradingView Chart ---
with tab1:
    st.subheader(f"Live {selected_tf} Chart: {tv_symbol}")
    
    # Dynamic