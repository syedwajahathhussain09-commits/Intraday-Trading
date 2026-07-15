import streamlit as st
import streamlit.components.v1 as components
import pandas as pd
import yfinance as yf
import matplotlib.pyplot as plt

# 1. Page Configuration
st.set_page_config(page_title="Multi-Timeframe Intraday Dashboard", layout="wide")
st.title("📈 Multi-Timeframe Trading Dashboard")

# Dictionary to map user-typed common company names to real ticker symbols
COMMON_NAME_TRANSLATOR = {
    "NETFLIX": "NFLX",
    "APPLE": "AAPL",
    "MICROSOFT": "MSFT",
    "TESLA": "TSLA",
    "NVIDIA": "NVDA",
    "AMAZON": "AMZN",
    "GOOGLE": "GOOGL",
    "META": "META",
    "COCA COLA": "KO",
    "COCACOLA": "KO",
    "RELIANCE": "RELIANCE.NS",
    "TATA": "TCS.NS",
    "TCS": "TCS.NS",
    "INFOSYS": "INFY.NS",
    "HDFC": "HDFCBANK.NS",
    "SBI": "SBIN.NS"
}

# Helper function to format tickers specifically for TradingView's API
def format_tv_symbol(ticker_symbol):
    ticker_symbol = ticker_symbol.strip().upper()
    
    # Check for Indian Stocks (NSE)
    if ticker_symbol.endswith(".NS"):
        clean_symbol = ticker_symbol.replace(".NS", "")
        return f"NSE:{clean_symbol}"
    
    # Common US stocks mapping explicitly
    us_nasdaq = ["AAPL", "MSFT", "TSLA", "NVDA", "AMZN", "GOOGL", "META", "NFLX", "QQQ"]
    us_nyse = ["KO", "BRK.B", "BRK-B", "NKE", "DIS", "SPY"]
    
    if ticker_symbol in us_nasdaq:
        return f"NASDAQ:{ticker_symbol}"
    if ticker_symbol in us_nyse:
        clean_nyse = ticker_symbol.replace("-", ".")
        return f"NYSE:{clean_nyse}"
    
    return ticker_symbol

# Map selections to yfinance settings
TIMEFRAME_MAP = {
    "5 Min": {"yf_interval": "5m", "yf_period": "5d", "tv_interval": "5", "resample": None},
    "15 Min": {"yf_interval": "15m", "yf_period": "1mo", "tv_interval": "15", "resample": None},
    "30 Min": {"yf_interval": "30m", "yf_period": "1mo", "tv_interval": "30", "resample": None},
    "1 Hour": {"yf_interval": "60m", "yf_period": "2y", "tv_interval": "60", "resample": None},
    "4 Hour": {"yf_interval": "60m", "yf_period": "2y", "tv_interval": "240", "resample": "4H"},
    "1 Day": {"yf_interval": "1d", "yf_period": "5y", "tv_interval": "D", "resample": None},
    "1 Month": {"yf_interval": "1mo", "yf_period": "max", "tv_interval": "M", "resample": None}
}

# Comprehensive Stock Directory
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

# 3. Sidebar Controls
st.sidebar.header("Configuration")

# Stock Search Selection
search_query = st.sidebar.selectbox(
    "Search Stock Name or Ticker:",
    options=list(STOCK_DIRECTORY.keys()),
    index=7  # Change index to 7 (Netflix) by default so you can see it working immediately!
)
ticker = STOCK_DIRECTORY[search_query]

# Custom override box
custom_ticker = st.sidebar.text_input("Or enter any raw ticker symbol manually:")
if custom_ticker:
    clean_custom = custom_ticker.strip().upper()
    # Check if they typed a common company name instead of the symbol
    if clean_custom in COMMON_NAME_TRANSLATOR:
        ticker = COMMON_NAME_TRANSLATOR[clean_custom]
        st.sidebar.info(f"Auto-corrected '{custom_ticker}' to official ticker: **{ticker}**")
    else:
        ticker = clean_custom

# Timeframe Selector
selected_tf = st.sidebar.selectbox(
    "Select Chart Timeframe:",
    options=list(TIMEFRAME_MAP.keys()),
    index=0 
)

tf_settings = TIMEFRAME_MAP[selected_tf]

# Strategy Parameters
fast_span = st.sidebar.slider("Fast EMA", min_value=3, max_value=20, value=9)
slow_span = st.sidebar.slider("Slow EMA", min_value=10, max_value=50, value=21)
rsi_period = st.sidebar.slider("RSI Period", min_value=5, max_value=30, value=14)

# Format the symbol for TradingView
tv_symbol = format_tv_symbol(ticker)

# Create Tabs
tab1, tab2 = st.tabs(["📺 Live TradingView Chart", "📊 Python EMA/RSI Signals"])

# --- TAB 1: Live Interactive TradingView Chart ---
with tab1:
    st.subheader(f"Live {selected_tf} Chart: {tv_symbol}")
    
    tradingview_widget_html = f"""
    <div class="tradingview-widget-container" style="height:600px; width:100%; margin:0 auto;">
      <div id="tradingview_chart" style="height:580px; width:100%;"></div>
      <script type="text/javascript" src="https://s3.tradingview.com/tv.js"></script>
      <script type="text/javascript">
      try {{
        new TradingView.widget({{
          "width": "100%",
          "height": 580,
          "symbol": "{tv_symbol}",
          "interval": "{tf_settings['tv_interval']}",
          "timezone": "Etc/UTC",
          "theme": "light",
          "style": "1",
          "locale": "en",
          "toolbar_bg": "#f1f3f6",
          "enable_publishing": false,
          "hide_side_toolbar": false,
          "allow_symbol_change": true,
          "container_id": "tradingview_chart"
        }});
      }} catch(err) {{
        document.getElementById('tradingview_chart').innerHTML = 
          "<div style='padding: 20px; color: red;'><b>TradingView Widget Failed to Load.</b></div>";
      }}
      </script>
    </div>
    """
    components.html(tradingview_widget_html, height=600)

# --- TAB 2: Custom Backtest Signals ---
with tab2:
    st.subheader(f"Custom Signal Logic ({selected_tf})")
    
    with st.spinner(f"Downloading {selected_tf} data for {ticker}..."):
        try:
            raw_data = yf.download(
                ticker, 
                period=tf_settings['yf_period'], 
                interval=tf_settings['yf_interval']
            )
            
            if isinstance(raw_data.columns, pd.MultiIndex):
                raw_data.columns = raw_data.columns.get_level_values(0)
                
            if raw_data.empty:
                st.error(f"No data returned for symbol '{ticker}' using {selected_tf} timeframe.")
                st.stop()
                
            # Handle 4-Hour resampling if chosen
            if tf_settings['resample']:
                data = raw_data.resample(tf_settings['resample']).agg({
                    'Open': 'first',
                    'High': 'max',
                    'Low': 'min',
                    'Close': 'last',
                    'Volume': 'sum'
                }).dropna()
            else:
                data = raw_data.copy()
                
        except Exception as e:
            st.error(f"Error loading yfinance data: {e}")
            st.stop()

    # =========================================================================
    # 1. CALCULATIONS & INDICATORS
    # =========================================================================
    
    # EMAs
    data['EMA_Fast'] = data['Close'].ewm(span=fast_span, adjust=False).mean()
    data['EMA_Slow'] = data['Close'].ewm(span=slow_span, adjust=False).mean()

    # RSI
    delta = data['Close'].diff()
    gain = (delta.where(delta > 0, 0)).rolling(window=rsi_period).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(window=rsi_period).mean()
    rs = gain / loss
    data['RSI'] = 100 - (100 / (1 + rs))

    # Average True Range (ATR - 14 Period) for Volatility/Stop Loss
    high_low = data['High'] - data['Low']
    high_close = (data['High'] - data['Close'].shift()).abs()
    low_close = (data['Low'] - data['Close'].shift()).abs()
    ranges = pd.concat([high_low, high_close, low_close], axis=1)
    data['ATR'] = ranges.max(axis=1).rolling(window=14).mean()

    # 20-Period Volume Moving Average (to filter low-volume traps)
    data['Vol_SMA'] = data['Volume'].rolling(window=20).mean()

    # =========================================================================
    # 2. UPGRADED SIGNAL GENERATION
    # =========================================================================
    data['Signal'] = 0
    
    # Strong BUY Condition: 
    # Fast EMA > Slow EMA AND RSI not overbought (< 70) AND Volume is higher than average
    data.loc[
        (data['EMA_Fast'] > data['EMA_Slow']) & 
        (data['RSI'] < 70) & 
        (data['Volume'] > data['Vol_SMA']), 
        'Signal'
    ] = 1
    
    # Strong SELL/EXIT Condition: 
    # Fast EMA < Slow EMA OR RSI is overbought (> 70)
    data.loc[
        (data['EMA_Fast'] < data['EMA_Slow']) | 
        (data['RSI'] > 70), 
        'Signal'
    ] = -1
    
    # Capture exactly when the signal flips (Buy/Sell arrows)
    data['Position'] = data['Signal'].diff()