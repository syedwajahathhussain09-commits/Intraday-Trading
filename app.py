import streamlit as st
import streamlit.components.v1 as components
import pandas as pd
import yfinance as yf
import matplotlib.pyplot as plt

# 1. Page Configuration
st.set_page_config(page_title="Multi-Timeframe Intraday Dashboard", layout="wide")
st.title("📈 Multi-Timeframe Trading Dashboard")

# 2. Enhanced Helper to format tickers specifically for TradingView's API
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
        # TradingView uses BRK.B instead of BRK-B
        clean_nyse = ticker_symbol.replace("-", ".")
        return f"NYSE:{clean_nyse}"
    
    # Fallback default: Let TradingView try to auto-resolve the bare ticker
    return ticker_symbol

# Map selections to (yfinance_interval, yfinance_period, tradingview_interval, resample_rule)
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

# Stock Search Selection
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
    
    # Embed code with added fallbacks and exact sizing
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
          "<div style='padding: 20px; color: red;'><b>TradingView Widget Failed to Load.</b><br>Please check your internet connection or disable ad-blockers / Brave Shields.</div>";
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
            # Download raw data based on the dynamic timeframe settings
            raw_data = yf.download(
                ticker, 
                period=tf_settings['yf_period'], 
                interval=tf_settings['yf_interval']
            )
            
            if isinstance(raw_data.columns, pd.MultiIndex):
                raw_data.columns = raw_data.columns.get_level_values(0)
                
            if raw_data.empty:
                st.error(f"No data returned for {ticker} using timeframe {selected_tf}.")
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
            st.error(f"Error: {e}")
            st.stop()

    # Calculations
    data['EMA_Fast'] = data['Close'].ewm(span=fast_span, adjust=False).mean()
    data['EMA_Slow'] = data['Close'].ewm(span=slow_span, adjust=False).mean()

    delta = data['Close'].diff()
    gain = (delta.where(delta > 0, 0)).rolling(window=rsi_period).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(window=rsi_period).mean()
    rs = gain / loss
    data['RSI'] = 100 - (100 / (1 + rs))

    data['Signal'] = 0
    data.loc[(data['EMA_Fast'] > data['EMA_Slow']) & (data['RSI'] < 70), 'Signal'] = 1
    data.loc[(data['EMA_Fast'] < data['EMA_Slow']) | (data['RSI'] > 70), 'Signal'] = -1
    data['Position'] = data['Signal'].diff()

    # Plotting
    plot_data = data.tail(100)
    fig, ax = plt.subplots(figsize=(14, 5))

    ax.plot(plot_data['Close'], label='Close Price', color='black', alpha=0.6)
    ax.plot(plot_data['EMA_Fast'], label=f'{fast_span} EMA', color='blue', linestyle='--')
    ax.plot(plot_data['EMA_Slow'], label=f'{slow_span} EMA', color='orange', linestyle='--')

    buys = plot_data[plot_data['Position'] == 2]
    ax.scatter(buys.index, buys['Close'], label='BUY Signal', marker='^', color='green', s=150)

    sells = plot_data[plot_data['Position'] == -2]
    ax.scatter(sells.index, sells['Close'], label='SELL Signal', marker='v', color='red', s=150)

    ax.set_title(f"{ticker} Signal History ({selected_tf} Chart)")
    ax.set_xlabel("Date/Time")
    ax.set_ylabel("Price")
    ax.legend()
    ax.grid(True)

    st.pyplot(fig)

    # Metrics
    col1, col2 = st.columns(2)
    with col1:
        last_price = float(data['Close'].iloc[-1])
        st.metric(label=f"{ticker} Last Price", value=f"{last_price:.2f}")
    with col2:
        last_rsi = float(data['RSI'].iloc[-1])
        st.metric(label="RSI", value=f"{last_rsi:.2f}")