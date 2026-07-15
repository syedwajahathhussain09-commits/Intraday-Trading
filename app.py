import streamlit as st
import streamlit.components.v1 as components
import pandas as pd
import yfinance as yf
import matplotlib.pyplot as plt

# 1. Page Configuration
st.set_page_config(page_title="Intraday Strategy Dashboard", layout="wide")
st.title("📈 Professional Intraday Trading Dashboard")

# Dictionary to map user-typed common company names to real ticker symbols
COMMON_NAME_TRANSLATOR = {
    "NETFLIX": "NFLX", "APPLE": "AAPL", "MICROSOFT": "MSFT",
    "TESLA": "TSLA", "NVIDIA": "NVDA", "AMAZON": "AMZN",
    "GOOGLE": "GOOGL", "META": "META", "COCA COLA": "KO",
    "COCACOLA": "KO", "RELIANCE": "RELIANCE.NS", "TATA": "TCS.NS",
    "TCS": "TCS.NS", "INFOSYS": "INFY.NS", "HDFC": "HDFCBANK.NS",
    "SBI": "SBIN.NS"
}

# Helper function to format tickers for TradingView
def format_tv_symbol(ticker_symbol):
    ticker_symbol = ticker_symbol.strip().upper()
    if ticker_symbol.endswith(".NS"):
        return f"NSE:{ticker_symbol.replace('.NS', '')}"
    
    us_nasdaq = ["AAPL", "MSFT", "TSLA", "NVDA", "AMZN", "GOOGL", "META", "NFLX", "QQQ"]
    us_nyse = ["KO", "BRK.B", "BRK-B", "NKE", "DIS", "SPY"]
    
    if ticker_symbol in us_nasdaq:
        return f"NASDAQ:{ticker_symbol}"
    if ticker_symbol in us_nyse:
        return f"NYSE:{ticker_symbol.replace('-', '.')}"
    return ticker_symbol

# Map selections to yfinance settings
TIMEFRAME_MAP = {
    "5 Min": {"yf_interval": "5m", "yf_period": "5d", "tv_interval": "5"},
    "15 Min": {"yf_interval": "15m", "yf_period": "1mo", "tv_interval": "15"},
    "30 Min": {"yf_interval": "30m", "yf_period": "1mo", "tv_interval": "30"},
    "1 Hour": {"yf_interval": "60m", "yf_period": "2y", "tv_interval": "60"},
    "1 Day": {"yf_interval": "1d", "yf_period": "5y", "tv_interval": "D"}
}

# Comprehensive Stock Directory
STOCK_DIRECTORY = {
    "Apple Inc. (AAPL)": "AAPL",
    "Microsoft Corp. (MSFT)": "MSFT",
    "Tesla Inc. (TSLA)": "TSLA",
    "NVIDIA Corp. (NVDA)": "NVDA",
    "Amazon.com Inc. (AMZN)": "AMZN",
    "Netflix Inc. (NFLX)": "NFLX",
    "Reliance Industries Ltd. (RELIANCE.NS)": "RELIANCE.NS",
    "Tata Consultancy Services (TCS.NS)": "TCS.NS",
    "State Bank of India (SBIN.NS)": "SBIN.NS",
}

# =========================================================================
# SIDEBAR CONTROLS
# =========================================================================
st.sidebar.header("Configuration")

# 1. Strategy Selector
strategy_type = st.sidebar.selectbox(
    "Choose Strategy:",
    options=["VWAP Pullback", "EMA Crossover"]
)

# 2. Stock Selection
search_query = st.sidebar.selectbox(
    "Search Stock Name or Ticker:",
    options=list(STOCK_DIRECTORY.keys()),
    index=5  # Default to Netflix
)
ticker = STOCK_DIRECTORY[search_query]

custom_ticker = st.sidebar.text_input("Or enter any raw ticker symbol manually:")
if custom_ticker:
    clean_custom = custom_ticker.strip().upper()
    if clean_custom in COMMON_NAME_TRANSLATOR:
        ticker = COMMON_NAME_TRANSLATOR[clean_custom]
        st.sidebar.info(f"Auto-corrected to: **{ticker}**")
    else:
        ticker = clean_custom

# 3. Timeframe Selection
selected_tf = st.sidebar.selectbox(
    "Select Chart Timeframe:",
    options=list(TIMEFRAME_MAP.keys()),
    index=0 
)
tf_settings = TIMEFRAME_MAP[selected_tf]

# 4. Parameters based on Strategy
st.sidebar.subheader("Strategy Settings")
if strategy_type == "EMA Crossover":
    fast_span = st.sidebar.slider("Fast EMA", min_value=3, max_value=20, value=9)
    slow_span = st.sidebar.slider("Slow EMA", min_value=10, max_value=50, value=21)
    rsi_period = st.sidebar.slider("RSI Period", min_value=5, max_value=30, value=14)
else:
    # VWAP Pullback parameters
    rsi_period = st.sidebar.slider("RSI Period", min_value=5, max_value=30, value=14)
    rsi_oversold = st.sidebar.slider("RSI Entry Threshold (Max)", min_value=30, max_value=70, value=60)

# Format for TV widget
tv_symbol = format_tv_symbol(ticker)

# Create Tabs
tab1, tab2 = st.tabs(["📺 Live TradingView Chart", "📊 Python Strategy Signals"])

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

# --- TAB 2: Custom Strategy Backtest Signals ---
with tab2:
    st.subheader(f"{strategy_type} Strategy Analysis ({selected_tf})")
    
    with st.spinner(f"Downloading {selected_tf} data for {ticker}..."):
        try:
            # Force standard single index
            raw_data = yf.download(
                ticker, 
                period=tf_settings['yf_period'], 
                interval=tf_settings['yf_interval'],
                multi_level_index=False
            )
            
            if raw_data.empty:
                st.error(f"No data returned for symbol '{ticker}'.")
                st.stop()
                
            data = raw_data.copy()
                
        except Exception as e:
            st.error(f"Error loading data: {e}")
            st.stop()

    try:
        # Extract series explicitly to avoid shape mismatches
        close_series = data['Close'].squeeze()
        high_series = data['High'].squeeze()
        low_series = data['Low'].squeeze()
        volume_series = data['Volume'].squeeze()

        # Calculate Common Indicators
        delta = close_series.diff()
        gain = (delta.where(delta > 0, 0)).rolling(window=rsi_period).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(window=rsi_period).mean()
        rs = gain / loss
        data['RSI'] = 100 - (100 / (1 + rs))
        
        data['Vol_SMA'] = volume_series.rolling(window=10).mean()
        data['Signal'] = 0

        # =========================================================================
        # EXECUTE SELECTED STRATEGY
        # =========================================================================
        if strategy_type == "VWAP Pullback":
            # Calculate Daily Resetting VWAP
            # Grouping by date ensures VWAP calculation restarts at 0 each day
            typical_price = (high_series + low_series + close_series) / 3
            tp_vol = typical_price * volume_series
            
            # Use Index Dates to Group
            dates = data.index.date
            cum_tp_vol = tp_vol.groupby(dates).cumsum()
            cum_vol = volume_series.groupby(dates).cumsum()
            
            data['VWAP'] = cum_tp_vol / cum_vol
            
            # BUY setup: Close price pulls back down near VWAP (but stays above or hits it)
            # AND RSI is not overbought (< rsi_oversold) AND volume is healthy
            data.loc[
                (close_series > data['VWAP']) & 
                (close_series.shift(1) <= data['VWAP']) &  # Price crossed back above VWAP
                (data['RSI'] < rsi_oversold) & 
                (volume_series > data['Vol_SMA'] * 0.9), 
                'Signal'
            ] = 1
            
            # SELL/EXIT: Price breaks clearly below the VWAP support line
            data.loc[
                (close_series < data['VWAP']), 
                'Signal'
            ] = -1

        else:
            # EMA Crossover Strategy
            data['EMA_Fast'] = close_series.ewm(span=fast_span, adjust=False).mean()
            data['EMA_Slow'] = close_series.ewm(span=slow_span, adjust=False).mean()
            
            # BUY
            data.loc[
                (data['EMA_Fast'] > data['EMA_Slow']) & 
                (data['RSI'] < 70) & 
                (volume_series > (data['Vol_SMA'] * 0.9)), 
                'Signal'
            ] = 1
            
            # SELL
            data.loc[
                (data['EMA_Fast'] < data['EMA_Slow']) | 
                (data['RSI'] > 70), 
                'Signal'
            ] = -1

        # Calculate exact trigger points where signal flips
        data['Position'] = data['Signal'].diff()

        # =========================================================================
        # PLOTTING THE STRATEGY
        # =========================================================================
        plot_data = data.tail(100)
        fig, ax = plt.subplots(figsize=(14, 5))

        ax.plot(plot_data.index, plot_data['Close'], label='Close Price', color='black', alpha=0.7)
        
        # Plot indicators dynamically based on selected strategy
        if strategy_type == "VWAP Pullback":
            ax.plot(plot_data.index, plot_data['VWAP'], label='VWAP (Daily Reset)', color='purple', linewidth=2)
        else:
            ax.plot(plot_data.index, plot_data['EMA_Fast'], label=f'{fast_span} EMA', color='blue', linestyle='--')
            ax.plot(plot_data.index, plot_data['EMA_Slow'], label=f'{slow_span} EMA', color='orange', linestyle='--')

        # Plot Buy Arrows
        buys = plot_data[plot_data['Position'] == 2]
        if not buys.empty:
            ax.scatter(buys.index, buys['Close'], label='BUY (Pullback)', marker='^', color='green', s=200)

        # Plot Sell/Exit Arrows
        sells = plot_data[plot_data['Position'] == -2]
        if not sells.empty:
            ax.scatter(sells.index, sells['Close'], label='SELL/EXIT', marker='v', color='red', s=200)

        ax.set_title(f"{ticker} - {strategy_type} ({selected_tf} Chart)")
        ax.set_xlabel("Date/Time")
        ax.set_ylabel("Price")
        ax.legend()
        ax.grid(True)

        st.pyplot(fig)

        # Metrics
        col1, col2 = st.columns(2)
        with col1:
            last_price = float(close_series.iloc[-1])
            st.metric(label=f"{ticker} Price", value=f"{last_price:.2f}")
        with col2:
            last_rsi = float(data['RSI'].iloc[-1])
            st.metric(label="Current RSI", value=f"{last_rsi:.2f}")

    except Exception as calculation_error:
        st.error(f"Error calculating strategy: {calculation_error}")