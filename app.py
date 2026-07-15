import streamlit as st
import streamlit.components.v1 as components
import pandas as pd
import yfinance as yf
import matplotlib.pyplot as plt

# 1. Page Configuration
st.set_page_config(page_title="Intraday Trading Signals", layout="wide")
st.title("📈 Intraday Trading Dashboard")

# 2. Helper function to format ticker for TradingView
def format_tv_symbol(ticker_symbol):
    # Indian Stocks (NSE)
    if ticker_symbol.endswith(".NS"):
        clean_symbol = ticker_symbol.replace(".NS", "")
        return f"NSE:{clean_symbol}"
    # Default to US markets (You can expand this mapping if needed)
    if ticker_symbol in ["AAPL", "MSFT", "TSLA", "NVDA", "AMZN", "GOOGL", "META", "NFLX"]:
        return f"NASDAQ:{ticker_symbol}"
    if ticker_symbol in ["KO", "BRK-B"]:
        return f"NYSE:{ticker_symbol}"
    return ticker_symbol

# 3. Comprehensive Stock Directory for Search Autocomplete
STOCK_DIRECTORY = {
    "Apple Inc. (AAPL)": "AAPL",
    "Microsoft Corp. (MSFT)": "MSFT",
    "Tesla Inc. (TSLA)": "TSLA",
    "NVIDIA Corp. (NVDA)": "NVDA",
    "Amazon.com Inc. (AMZN)": "AMZN",
    "Alphabet Inc. / Google (GOOGL)": "GOOGL",
    "Meta Platforms (META)": "META",
    "Netflix Inc. (NFLX)": "NFLX",
    "Coca-Cola Co. (KO)": "KO",
    "Reliance Industries Ltd. (RELIANCE.NS)": "RELIANCE.NS",
    "Tata Consultancy Services (TCS.NS)": "TCS.NS",
    "Infosys Ltd. (INFY.NS)": "INFY.NS",
    "HDFC Bank Ltd. (HDFCBANK.NS)": "HDFCBANK.NS",
    "State Bank of India (SBIN.NS)": "SBIN.NS",
    "ICICI Bank Ltd. (ICICIBANK.NS)": "ICICIBANK.NS",
}

# 4. Sidebar Controls
st.sidebar.header("Configuration")

# Main Search Bar
st.sidebar.subheader("Search Stock")
search_query = st.sidebar.selectbox(
    "Type to search stock name or ticker:",
    options=list(STOCK_DIRECTORY.keys()),
    index=0
)
ticker = STOCK_DIRECTORY[search_query]

# Custom override box
custom_ticker = st.sidebar.text_input("Or enter any raw ticker symbol manually:")
if custom_ticker:
    ticker = custom_ticker.strip().upper()

# Parameters for indicators
fast_span = st.sidebar.slider("Fast EMA", min_value=3, max_value=20, value=9)
slow_span = st.sidebar.slider("Slow EMA", min_value=10, max_value=50, value=21)
rsi_period = st.sidebar.slider("RSI Period", min_value=5, max_value=30, value=14)

# Get formatted ticker for TradingView Widget
tv_symbol = format_tv_symbol(ticker)

# Create two tabs: One for Live TradingView, one for custom EMA/RSI logic
tab1, tab2 = st.tabs(["📺 Live TradingView Chart", "📊 Custom EMA/RSI Signals"])

# --- TAB 1: Live Interactive TradingView Chart ---
with tab1:
    st.subheader(f"Live Interactive Widget: {tv_symbol}")
    
    # TradingView Widget HTML code
    tradingview_widget_html = f"""
    <div class="tradingview-widget-container" style="height:100%;width:100%">
      <div id="tradingview_chart" style="height:600px;width:100%"></div>
      <script type="text/javascript" src="https://s3.tradingview.com/tv.js"></script>
      <script type="text/javascript">
      new TradingView.widget({{
        "autosize": true,
        "symbol": "{tv_symbol}",
        "interval": "5",
        "timezone": "Etc/UTC",
        "theme": "light",
        "style": "1",
        "locale": "en",
        "enable_publishing": false,
        "hide_side_toolbar": false,
        "allow_symbol_change": true,
        "container_id": "tradingview_chart"
      }});
      </script>
    </div>
    """
    
    # Render the widget
    components.html(tradingview_widget_html, height=610)

# --- TAB 2: Custom EMA/RSI Calculations & Signals ---
with tab2:
    st.subheader("Your Custom Intraday Backtest Signals")
    
    # Download Intraday Data
    with st.spinner(f"Fetching Python data for {ticker}..."):
        try:
            data = yf.download(ticker, period="5d", interval="5m")
            
            if isinstance(data.columns, pd.MultiIndex):
                data.columns = data.columns.get_level_values(0)
                
            if data.empty:
                st.error(f"No data found for symbol '{ticker}'.")
                st.stop()
        except Exception as e:
            st.error(f"Error: {e}")
            st.stop()

    # Calculations
    data['EMA_Fast'] = data['Close'].ewm(span=fast_span, adjust=False).mean()
    data['EMA_Slow'] = data['Close'].ewm(span=slow_span, adjust=False).mean()

    delta = data['Close'].diff()
    gain = (delta.where(delta > 0, 0)).rolling(window=rsi_period).mean()