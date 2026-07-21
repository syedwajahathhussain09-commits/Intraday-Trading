import streamlit as st
import streamlit.components.v1 as components
import pandas as pd
import yfinance as yf
import matplotlib.pyplot as plt
import time
import urllib.request
import io

# 1. Page Configuration
st.set_page_config(page_title="Global Intraday Screener", layout="wide")
st.title("📈 Global Intraday Trading & Screener Dashboard")

# Dictionary to map user-typed common company names to real ticker symbols
COMMON_NAME_TRANSLATOR = {
    "NETFLIX": "NFLX", "APPLE": "AAPL", "MICROSOFT": "MSFT",
    "TESLA": "TSLA", "NVIDIA": "NVDA", "AMAZON": "AMZN",
    "GOOGLE": "GOOGL", "META": "META", "COCA COLA": "KO",
    "RELIANCE": "RELIANCE.NS", "TATA": "TCS.NS", "TCS": "TCS.NS",
    "INFOSYS": "INFY.NS", "HDFC": "HDFCBANK.NS", "SBI": "SBIN.NS",
    "COINBASE": "COIN", "PALANTIR": "PLTR", "MARATHON": "MARA",
    "AMD": "AMD", "MICRON": "MU"
}

# Helper function to scrape live Index Tickers dynamically with a browser user-agent
@st.cache_data(ttl=86400) # Cache lists for 24 hours
def load_index_tickers(index_name):
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/115.0.0.0 Safari/537.36'
    }
    try:
        if index_name == "S&P 500 (US - Mixed)":
            url = 'https://en.wikipedia.org/wiki/List_of_S%26P_500_companies'
            req = urllib.request.Request(url, headers=headers)
            with urllib.request.urlopen(req) as response:
                html = response.read().decode('utf-8')
            table = pd.read_html(io.StringIO(html), attrs={'id': 'constituents'})[0]
            tickers = table['Symbol'].str.replace('.', '-', regex=False).tolist()
            return sorted(tickers)
            
        elif index_name == "NASDAQ 100 (US - Tech)":
            url = 'https://en.wikipedia.org/wiki/Nasdaq-100'
            req = urllib.request.Request(url, headers=headers)
            with urllib.request.urlopen(req) as response:
                html = response.read().decode('utf-8')
            tables = pd.read_html(io.StringIO(html))
            for t in tables:
                if 'Ticker' in t.columns:
                    return sorted(t['Ticker'].tolist())
            return ["AAPL", "MSFT", "AMZN", "NVDA", "TSLA", "META", "GOOGL", "NFLX", "AMD", "INTC"]

        elif index_name == "FTSE 100 (UK - LSE)":
            url = 'https://en.wikipedia.org/wiki/FTSE_100_Index'
            req = urllib.request.Request(url, headers=headers)
            with urllib.request.urlopen(req) as response:
                html = response.read().decode('utf-8')
            tables = pd.read_html(io.StringIO(html))
            for t in tables:
                if 'EPIC' in t.columns:
                    return sorted([f"{str(sym).strip()}.L" for sym in t['EPIC'].tolist()])
            return ["SHEL.L", "AZN.L", "HSBA.L", "ULVR.L", "BP.L", "GSK.L", "RIO.L", "LLOY.L"]

        else: # Custom Volatile Watchlist
            return ["TSLA", "NVDA", "AAPL", "PLTR", "COIN", "AMD", "NFLX", "MARA", "MU", "RELIANCE.NS", "SBIN.NS"]
            
    except Exception as e:
        st.warning(f"Failed to fetch live {index_name} components: {e}")
        return ["TSLA", "NVDA", "AAPL", "MSFT", "AMD", "PLTR", "COIN", "NFLX"]

# Helper function to format tickers for TradingView
def format_tv_symbol(ticker_symbol):
    ticker_symbol = ticker_symbol.strip().upper()
    if ticker_symbol.endswith(".NS"):
        return f"NSE:{ticker_symbol.replace('.NS', '')}"
    if ticker_symbol.endswith(".L"):
        return f"LSE:{ticker_symbol.replace('.L', '')}"
    
    us_nasdaq = ["AAPL", "MSFT", "TSLA", "NVDA", "AMZN", "GOOGL", "META", "NFLX", "QQQ", "COIN", "PLTR", "MARA", "AMD", "MU"]
    us_nyse = ["KO", "BRK.B", "BRK-B", "NKE", "DIS", "SPY"]
    
    if ticker_symbol in us_nasdaq:
        return f"NASDAQ:{ticker_symbol}"
    if ticker_symbol in us_nyse:
        return f"NYSE:{ticker_symbol.replace('-', '.').replace('_', '.')}"
    return ticker_symbol

# Map selections to yfinance settings
TIMEFRAME_MAP = {
    "5 Min": {"yf_interval": "5m", "yf_period": "5d", "tv_interval": "5"},
    "15 Min": {"yf_interval": "15m", "yf_period": "1mo", "tv_interval": "15"},
    "30 Min": {"yf_interval": "30m", "yf_period": "1mo", "tv_interval": "30"},
    "1 Hour": {"yf_interval": "60m", "yf_period": "2y", "tv_interval": "60"},
    "1 Day": {"yf_interval": "1d", "yf_period": "5y", "tv_interval": "D"}
}

# Comprehensive Stock Directory for Manual search dropdown
STOCK_DIRECTORY = {
    "Tesla Inc. (TSLA)": "TSLA",
    "NVIDIA Corp. (NVDA)": "NVDA",
    "Apple Inc. (AAPL)": "AAPL",
    "Microsoft Corp. (MSFT)": "MSFT",
    "Palantir (PLTR)": "PLTR",
    "Coinbase (COIN)": "COIN",
    "Netflix Inc. (NFLX)": "NFLX",
    "State Bank of India (SBIN.NS)": "SBIN.NS",
}

# =========================================================================
# SIDEBAR CONTROLS
# =========================================================================
st.sidebar.header("Configuration")

# 1. Strategy Selector
strategy_type = st.sidebar.selectbox(
    "Choose Strategy:",
    options=["All-in-One Confluence", "RSI Range Spotter", "VWAP Pullback", "EMA Crossover"]
)

# 2. Stock Selection (For Tab 1 & Tab 2)
search_query = st.sidebar.selectbox(
    "Search Single Stock:",
    options=list(STOCK_DIRECTORY.keys()),
    index=0 
)
ticker = STOCK_DIRECTORY[search_query]

custom_ticker = st.sidebar.text_input("Or enter raw symbol (e.g. BARC.L or SBIN.NS):")
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

# --- EXTENDED HOURS TOGGLE ---
include_extended_hours = st.sidebar.checkbox(
    "🌅/🌙 Include Pre & Post-Market Data",
    value=True,
    help="Enable to track trading activity outside regular market hours (4:00 AM - 8:00 PM EST)."
)

# 4. Parameters based on Strategy
st.sidebar.subheader("Strategy Settings")
rsi_period = st.sidebar.slider("RSI Period", min_value=5, max_value=30, value=14)

# Set defaults for EMA spans so they are always defined
fast_span = 9
slow_span = 21

if strategy_type == "All-in-One Confluence":
    st.sidebar.markdown("**Confluence Strategy Controls**")
    fast_span = st.sidebar.slider("Fast EMA", min_value=3, max_value=20, value=9)
    slow_span = st.sidebar.slider("Slow EMA", min_value=10, max_value=50, value=21)
    st.sidebar.info("Uses Price > VWAP, EMA Crossover, and RSI (40-65) for signal confirmation.")

elif strategy_type == "RSI Range Spotter":
    st.sidebar.markdown("**RSI Target Zone (Buy)**")
    rsi_min = st.sidebar.slider("RSI Min Floor", min_value=10, max_value=50, value=30)
    rsi_max = st.sidebar.slider("RSI Max Ceiling", min_value=15, max_value=60, value=35)
    
elif strategy_type == "VWAP Pullback":
    rsi_oversold = st.sidebar.slider("RSI Entry Threshold (Max)", min_value=30, max_value=70, value=60)
    
elif strategy_type == "EMA Crossover":
    fast_span = st.sidebar.slider("Fast EMA", min_value=3, max_value=20, value=9)
    slow_span = st.sidebar.slider("Slow EMA", min_value=10, max_value=50, value=21)

# Format for TV widget
tv_symbol = format_tv_symbol(ticker)

# Create Tabs
tab1, tab2, tab3 = st.tabs(["📺 Live TradingView Chart", "📊 Python Strategy Signals", "🔍 Real-Time Index Screener"])

## --- TAB 1: Live Interactive TradingView Chart ---
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
          "extended_hours": true,
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
            raw_data = yf.download(
                ticker, 
                period=tf_settings['yf_period'], 
                interval=tf_settings['yf_interval'],
                prepost=include_extended_hours,  # <--- PASSES EXTENDED HOURS TOGGLE
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
        close_series = data['Close'].squeeze()
        high_series = data['High'].squeeze()
        low_series = data['Low'].squeeze()
        volume_series = data['Volume'].squeeze()

        # Calculate Basic Indicators
        delta = close_series.diff()
        gain = (delta.where(delta > 0, 0)).rolling(window=rsi_period).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(window=rsi_period).mean()
        rs = gain / loss
        data['RSI'] = 100 - (100 / (1 + rs))
        
        data['Vol_SMA'] = volume_series.rolling(window=10).mean()
        data['Signal'] = 0
        
# Calculate Basic Indicators
        delta = close_series.diff()
        gain = (delta.where(delta > 0, 0)).rolling(window=rsi_period).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(window=rsi_period).mean()
        rs = gain / loss
        data['RSI'] = 100 - (100 / (1 + rs))
        
        data['Vol_SMA'] = volume_series.rolling(window=10).mean()
        data['Signal'] = 0

        # Calculate Common Moving Averages & VWAP for Confluence Check
        data['EMA_Fast'] = close_series.ewm(span=fast_span, adjust=False).mean()
        data['EMA_Slow'] = close_series.ewm(span=slow_span, adjust=False).mean()
        
        typical_price = (high_series + low_series + close_series) / 3
        tp_vol = typical_price * volume_series
        dates = data.index.date
        cum_tp_vol = tp_vol.groupby(dates).cumsum()
        cum_vol = volume_series.groupby(dates).cumsum()
        data['VWAP'] = cum_tp_vol / cum_vol

        # =========================================================================
        # STRATEGY SIGNAL ROUTING (ADD ALL-IN-ONE CONFLUENCE RIGHT HERE)
        # =========================================================================
        if strategy_type == "All-in-One Confluence":
            # 1. Buy when: EMA Fast > Slow + Price > VWAP + Healthy RSI (40-65) + Above Average Volume
            data.loc[
                (data['EMA_Fast'] > data['EMA_Slow']) & 
                (close_series > data['VWAP']) & 
                (data['RSI'] >= 40) & (data['RSI'] <= 65) &
                (volume_series > (data['Vol_SMA'] * 0.8)), 
                'Signal'
            ] = 1
            
            # 2. Sell / Exit when: EMA Fast drops below Slow OR Price drops below VWAP OR RSI overbought (> 70)
            data.loc[
                (data['EMA_Fast'] < data['EMA_Slow']) | 
                (close_series < data['VWAP']) | 
                (data['RSI'] > 70), 
                'Signal'
            ] = -1

        elif strategy_type == "RSI Range Spotter":
            data.loc[
                (data['RSI'] >= rsi_min) & 
                (data['RSI'] <= rsi_max) & 
                (volume_series > (data['Vol_SMA'] * 0.8)), 
                'Signal'
            ] = 1
            data.loc[(data['RSI'] > 65), 'Signal'] = -1

        elif strategy_type == "VWAP Pullback":
            data.loc[
                (close_series > data['VWAP']) & 
                (close_series.shift(1) <= data['VWAP']) & 
                (data['RSI'] < rsi_oversold) & 
                (volume_series > data['Vol_SMA'] * 0.9), 
                'Signal'
            ] = 1
            data.loc[(close_series < data['VWAP']), 'Signal'] = -1

        else: # EMA Crossover
            data.loc[
                (data['EMA_Fast'] > data['EMA_Slow']) & 
                (data['RSI'] < 70) & 
                (volume_series > (data['Vol_SMA'] * 0.9)), 
                'Signal'
            ] = 1
            data.loc[(data['EMA_Fast'] < data['EMA_Slow']) | (data['RSI'] > 70), 'Signal'] = -1

        data['Position'] = data['Signal'].diff()

        # =========================================================================
        # AUTOMATIC CANDLESTICK PATTERN DETECTOR
        # =========================================================================
        st.markdown("---")
        st.markdown("### 🕯️ Automatic Candlestick Pattern Recognition")
        
        body = (close_series - data['Open'].squeeze()).abs()
        candle_range = high_series - low_series
        candle_range = candle_range.replace(0, 0.00001) 
        
        upper_shadow = high_series - data[['Close', 'Open']].max(axis=1).squeeze()
        lower_shadow = data[['Close', 'Open']].min(axis=1).squeeze() - low_series
        
        data['Pattern'] = "⚪ No Pattern"
        data['Pattern_Signal'] = 0
        
        # 1. Hammer Detection
        is_hammer = (lower_shadow > (2 * body)) & (upper_shadow < (0.1 * candle_range)) & (data['RSI'] < 40)
        data.loc[is_hammer, 'Pattern'] = "🟢 BULLISH HAMMER"
        data.loc[is_hammer, 'Pattern_Signal'] = 1
        
        # 2. Shooting Star Detection
        is_shooting_star = (upper_shadow > (2 * body)) & (lower_shadow < (0.1 * candle_range)) & (data['RSI'] > 60)
        data.loc[is_shooting_star, 'Pattern'] = "🔴 BEARISH SHOOTING STAR"
        data.loc[is_shooting_star, 'Pattern_Signal'] = -1
        
        # 3. Engulfing Detection
        prev_close = close_series.shift(1)
        prev_open = data['Open'].squeeze().shift(1)
        curr_close = close_series
        curr_open = data['Open'].squeeze()
        
        is_bullish_engulfing = (prev_close < prev_open) & (curr_close > curr_open) & (curr_open <= prev_close) & (curr_close >= prev_open)
        is_bearish_engulfing = (prev_close > prev_open) & (curr_close < curr_open) & (curr_open >= prev_close) & (curr_close <= prev_open)
        
        data.loc[is_bullish_engulfing, 'Pattern'] = "🟢 BULLISH ENGULFING"
        data.loc[is_bullish_engulfing, 'Pattern_Signal'] = 1
        data.loc[is_bearish_engulfing, 'Pattern'] = "🔴 BEARISH ENGULFING"
        data.loc[is_bearish_engulfing, 'Pattern_Signal'] = -1

        # Display Latest Candle Findings
        latest_candle = data.iloc[-1]
        latest_pattern = latest_candle['Pattern']
        
        if "🟢" in latest_pattern:
            st.success(f"**Current Candle Pattern:** {latest_pattern} detected on the {selected_tf} timeframe! Look for Potential Long Entry.")
        elif "🔴" in latest_pattern:
            st.error(f"**Current Candle Pattern:** {latest_pattern} detected on the {selected_tf} timeframe! Look for Potential Short/Exit.")
        else:
            st.info(f"**Current Candle Pattern:** No clear reversal candlestick pattern formed on the current {selected_tf} bar.")

        # =========================================================================
        # LIVE SIGNAL ADVISOR MODULE (WITH EXTENDED HOURS METRICS)
        # =========================================================================
        st.markdown("---")
        st.markdown("### 🚨 Live Signal Advisor & Market Session Status")
        
        try:
            live_ticker = yf.Ticker(ticker)
            fast = live_ticker.fast_info
            info = live_ticker.info
            
            # Prioritize official preMarketPrice/postMarketPrice if available, else fast_info
            pre_price = info.get('preMarketPrice')
            post_price = info.get('postMarketPrice')
            
            if pre_price is not None and pre_price > 0:
                last_price = float(pre_price)
            elif post_price is not None and post_price > 0:
                last_price = float(post_price)
            else:
                last_price = float(fast['last_price'])

            prev_close = float(fast['previous_close'])
            price_change = last_price - prev_close
            pct_change = (price_change / prev_close) * 100
        except Exception:
            last_price = float(close_series.iloc[-1])
            price_change = 0.0
            pct_change = 0.0

        # Display Live Session Price Banner
        chg_color = "🟢" if price_change >= 0 else "🔴"
        st.info(f"**Live Extended Market Price:** `${last_price:.2f}` ({chg_color} `{price_change:+.2f}` / `{pct_change:+.2f}%`) | **Last Bar Timestamp:** `{data.index[-1].strftime('%Y-%m-%d %H:%M EST')}`")
        
        # ATR Calculation
        high_low = high_series - low_series
        high_close = (high_series - close_series.shift()).abs()
        low_close = (low_series - close_series.shift()).abs()
        ranges = pd.concat([high_low, high_close, low_close], axis=1)
        atr_value = float(ranges.max(axis=1).rolling(window=14).mean().iloc[-1])

        col_sig, col_metrics = st.columns([1.5, 2])
        
        with col_sig:
            if last_signal == 1:
                st.success(f"### 🟢 ACTIVE ACTION: BUY / LONG\n**Live Price:** ${last_price:.2f} | **RSI:** {last_rsi:.1f}")
                stop_loss = last_price - (1.5 * atr_value)
                target = last_price + (3.0 * atr_value)
                st.markdown(f"""
                * **Suggested Entry:** Around `${last_price:.2f}`
                * **Stop Loss (1.5x ATR):** `${stop_loss:.2f}`
                * **Profit Target (3x ATR):** `${target:.2f}`
                """)
            elif last_signal == -1:
                st.error(f"### 🔴 ACTIVE ACTION: SELL / SHORT / EXIT\n**Live Price:** ${last_price:.2f} | **RSI:** {last_rsi:.1f}")
                stop_loss = last_price + (1.5 * atr_value)
                target = last_price - (3.0 * atr_value)
                st.markdown(f"""
                * **Suggested Entry:** Around `${last_price:.2f}`
                * **Stop Loss (1.5x ATR):** `${stop_loss:.2f}`
                * **Profit Target (3x ATR):** `${target:.2f}`
                """)
            else:
                st.info(f"### ⚪ ACTIVE ACTION: HOLD / NO SIGNAL\n**Live Price:** ${last_price:.2f} | **RSI:** {last_rsi:.1f}")
                st.write("The strategy parameters are currently neutral. Wait for the next setup crossover or oversold range dip.")

        try:
            latest_date = data.index[-1].date()
            today_data = data[data.index.date == latest_date]
            
            # Cumulative total volume traded so far today (including pre/post-market)
            total_session_vol = float(today_data['Volume'].sum())
            last_bar_vol = float(today_data['Volume'].iloc[-1])
        except Exception:
            total_session_vol = float(volume_series.iloc[-1])
            last_bar_vol = float(volume_series.iloc[-1])

        # Format Volume helper
        def format_vol(v):
            if v >= 1_000_000_000:
                return f"{v / 1_000_000_000:.2f}B"
            elif v >= 1_000_000:
                return f"{v / 1_000_000:.2f}M"
            elif v >= 1_000:
                return f"{v / 1_000:.1f}K"
            return str(int(v))

        formatted_total_vol = format_vol(total_session_vol)
        formatted_bar_vol = format_vol(last_bar_vol)

        # --- UPDATE METRIC CARDS ---
        col_m1, col_m2, col_m3, col_m4 = st.columns(4)
        col_m1.metric("Live Price", f"${last_price:.2f}", f"{price_change:+.2f} ({pct_change:+.2f}%)")
        col_m2.metric("Current RSI", f"{float(data['RSI'].iloc[-1]):.1f}")
        col_m3.metric("Session Volume", formatted_total_vol, delta=f"Last Bar: {formatted_bar_vol}")
        col_m4.metric("Strategy Signal", "BUY" if data['Signal'].iloc[-1] == 1 else ("SELL" if data['Signal'].iloc[-1] == -1 else "NEUTRAL"))

        # =========================================================================
        # PLOTTING THE STRATEGY
        # =========================================================================
        st.markdown("---")
        plot_data = data.tail(100)
        # Update subplot grid to 3 rows (Price, RSI, Volume)
        fig, (ax1, ax2, ax3) = plt.subplots(3, 1, figsize=(12, 10), sharex=True, gridspec_kw={'height_ratios': [3, 1, 1]})
        
        # [Ax1: Price Plotting Code Remains Same...]
        ax1.plot(plot_data.index, plot_data['Close'], label='Close Price', color='black', alpha=0.7)
        if strategy_type in ["VWAP Pullback", "All-in-One Confluence"] and 'VWAP' in plot_data.columns:
            ax1.plot(plot_data.index, plot_data['VWAP'], label='VWAP', color='purple', linewidth=2)
        if strategy_type in ["EMA Crossover", "All-in-One Confluence"] and 'EMA_Fast' in plot_data.columns:
            ax1.plot(plot_data.index, plot_data['EMA_Fast'], label='Fast EMA', color='blue', linestyle='--')
            ax1.plot(plot_data.index, plot_data['EMA_Slow'], label='Slow EMA', color='orange', linestyle='--')
        ax1.set_title(f"{ticker} - {selected_tf} Price & Signals", fontsize=14, fontweight='bold')
        ax1.legend(loc='upper left')
        ax1.grid(True, alpha=0.3)

        # [Ax2: RSI Plotting]
        ax2.plot(plot_data.index, plot_data['RSI'], label='RSI', color='orange')
        ax2.axhline(70, color='red', linestyle='--', alpha=0.5)
        ax2.axhline(30, color='green', linestyle='--', alpha=0.5)
        ax2.set_ylabel("RSI")
        ax2.grid(True, alpha=0.3)

        # [Ax3: NEW VOLUME BARS PLOT]
        # Volume Subplot displaying extended session bars
        colors = ['green' if c >= o else 'red' for c, o in zip(plot_data['Close'], plot_data['Open'])]
        ax3.bar(plot_data.index, plot_data['Volume'], color=colors, alpha=0.6, width=0.003)
        ax3.set_ylabel("Volume")
        ax3.grid(True, alpha=0.3)
        st.pyplot(fig)

        # =========================================================================
        # RECENT TRADES HISTORY LOG
        # =========================================================================
        st.markdown("### 📜 Recent Signal Execution Logs")
        history = data[data['Position'].isin([2, -2])].copy()
        
        if not history.empty:
            history['Action'] = history['Position'].apply(lambda x: "🟢 BUY / LONG" if x == 2 else "🔴 SELL / EXIT")
            history['Price'] = history['Close'].round(2)
            history['RSI_at_Trigger'] = history['RSI'].round(1)
            
            history_display = history[['Action', 'Price', 'RSI_at_Trigger']].tail(5).sort_index(ascending=False)
            st.dataframe(history_display, use_container_width=True)
        else:
            st.info("No signal crossovers found in the loaded historical window.")

    except Exception as calculation_error:
        st.error(f"Error calculating strategy: {calculation_error}")


# --- TAB 3: Real-Time Index Screener ---
with tab3:
    st.subheader("🔍 High-Speed Global Index Screener")
    st.write("Scan entire market indices or run an on-demand real-time check on any custom stock symbol.")
    
    # Initialize session state storage so data persists when filtering
    if "scan_results" not in st.session_state:
        st.session_state.scan_results = None

    # =========================================================================
    # OPTION 1: QUICK SINGLE CUSTOM STOCK SCANNER
    # =========================================================================
    st.markdown("### 🎯 Option 1: Quick Scan a Single Custom Stock")
    col_search, col_search_btn = st.columns([3, 1])
    
    with col_search:
        single_search_symbol = st.text_input(
            "Enter raw symbol to scan immediately (e.g. TSLA, INF.L, RELIANCE.NS):", 
            key="screener_single_symbol_input"
        ).strip().upper()
        
    with col_search_btn:
        st.write(" ") 
        st.write(" ") 
        run_single_scan = st.button("🔍 Scan Single Stock")

    if run_single_scan and single_search_symbol:
        with st.spinner(f"Running high-precision scan for {single_search_symbol}..."):
            try:
                s_data = yf.download(
                    tickers=single_search_symbol,
                    period="5d",
                    interval=tf_settings['yf_interval'],
                    threads=False,
                    progress=False
                )
                
                if s_data.empty:
                    st.error(f"Could not retrieve data for '{single_search_symbol}'. Please verify the ticker format.")
                else:
                    s_close = s_data['Close'].squeeze()
                    s_high = s_data['High'].squeeze()
                    s_low = s_data['Low'].squeeze()
                    s_open = s_data['Open'].squeeze()
                    s_volume = s_data['Volume'].squeeze()
                    
                    s_delta = s_close.diff()
                    s_gain = (s_delta.where(s_delta > 0, 0)).rolling(window=rsi_period).mean()
                    s_loss = (-s_delta.where(s_delta < 0, 0)).rolling(window=rsi_period).mean()
                    s_rs = s_gain / s_loss
                    s_rsi = 100 - (100 / (1 + s_rs))
                    s_vol_sma = s_volume.rolling(window=10).mean()
                    
                    current_price = float(s_close.iloc[-1])
                    current_rsi = float(s_rsi.iloc[-1])
                    current_vol = float(s_volume.iloc[-1])
                    current_vol_sma = float(s_vol_sma.iloc[-1])
                    
                    # Format Volume K/M/B
                    if current_vol >= 1_000_000_000:
                        vol_str = f"{current_vol / 1_000_000_000:.2f}B"
                    elif current_vol >= 1_000_000:
                        vol_str = f"{current_vol / 1_000_000:.2f}M"
                    elif current_vol >= 1_000:
                        vol_str = f"{current_vol / 1_000:.1f}K"
                    else:
                        vol_str = str(int(current_vol))
                    
                    s_body = (s_close - s_open).abs()
                    s_range = s_high - s_low
                    s_range = s_range.replace(0, 0.00001)
                    s_upper_shadow = s_high - s_data[['Close', 'Open']].max(axis=1).squeeze()
                    s_lower_shadow = s_data[['Close', 'Open']].min(axis=1).squeeze() - s_low
                    
                    detected_pattern = "⚪ No Pattern"
                    if (s_lower_shadow.iloc[-1] > (2 * s_body.iloc[-1])) and (s_upper_shadow.iloc[-1] < (0.1 * s_range.iloc[-1])) and (current_rsi < 40):
                        detected_pattern = "🟢 BULLISH HAMMER"
                    elif (s_upper_shadow.iloc[-1] > (2 * s_body.iloc[-1])) and (s_lower_shadow.iloc[-1] < (0.1 * s_range.iloc[-1])) and (current_rsi > 60):
                        detected_pattern = "🔴 BEARISH SHOOTING STAR"
                    else:
                        p_close, p_open = s_close.iloc[-2], s_open.iloc[-2]
                        c_close, c_open = s_close.iloc[-1], s_open.iloc[-1]
                        if (p_close < p_open) and (c_close > c_open) and (c_open <= p_close) and (c_close >= p_open):
                            detected_pattern = "🟢 BULLISH ENGULFING"
                        elif (p_close > p_open) and (c_close < c_open) and (c_open >= p_close) and (c_close <= p_open):
                            detected_pattern = "🔴 BEARISH ENGULFING"
                    
                    action = "⚪ HOLD / NEUTRAL"
                    if strategy_type == "All-in-One Confluence":
                        s_fast = s_close.ewm(span=fast_span, adjust=False).mean()
                        s_slow = s_close.ewm(span=slow_span, adjust=False).mean()
                        typical_price = (s_high + s_low + s_close) / 3
                        tp_vol = typical_price * s_volume
                        dates = s_data.index.date
                        cum_tp_vol = tp_vol.groupby(dates).cumsum()
                        cum_vol = s_volume.groupby(dates).cumsum()
                        s_vwap = cum_tp_vol / cum_vol
                        
                        if (float(s_fast.iloc[-1]) > float(s_slow.iloc[-1])) and (current_price > float(s_vwap.iloc[-1])) and (40 <= current_rsi <= 65) and (current_vol > current_vol_sma * 0.8):
                            action = "🟢 STRATEGY BUY"
                        elif (float(s_fast.iloc[-1]) < float(s_slow.iloc[-1])) or (current_price < float(s_vwap.iloc[-1])) or (current_rsi > 70):
                            action = "🔴 STRATEGY SELL"

                    elif strategy_type == "RSI Range Spotter":
                        if (current_rsi >= rsi_min) and (current_rsi <= rsi_max) and (current_vol > current_vol_sma * 0.8):
                            action = "🟢 STRATEGY BUY"
                        elif current_rsi > 65:
                            action = "🔴 STRATEGY SELL"
                            
                    elif strategy_type == "VWAP Pullback":
                        typical_price = (s_high + s_low + s_close) / 3
                        tp_vol = typical_price * s_volume
                        dates = s_data.index.date
                        cum_tp_vol = tp_vol.groupby(dates).cumsum()
                        cum_vol = s_volume.groupby(dates).cumsum()
                        s_vwap_series = cum_tp_vol / cum_vol
                        current_vwap = float(s_vwap_series.iloc[-1])
                        
                        if (current_price > current_vwap) and (float(s_close.iloc[-2]) <= float(s_vwap_series.iloc[-2])) and (current_rsi < rsi_oversold):
                            action = "🟢 STRATEGY BUY"
                        elif current_price < current_vwap:
                            action = "🔴 STRATEGY SELL"
                            
                    else: # EMA Crossover
                        s_fast = s_close.ewm(span=fast_span, adjust=False).mean()
                        s_slow = s_close.ewm(span=slow_span, adjust=False).mean()
                        if (float(s_fast.iloc[-1]) > float(s_slow.iloc[-1])) and (current_rsi < 70):
                            action = "🟢 STRATEGY BUY"
                        else:
                            action = "🔴 STRATEGY SELL"
                    
                    st.session_state.scan_results = [{
                        "Stock": single_search_symbol,
                        "Current Price": f"${current_price:.2f}" if not single_search_symbol.endswith(".L") else f"£{current_price/100:.2f}",
                        "Volume": vol_str,
                        "RSI": round(current_rsi, 1),
                        "Candle Pattern": detected_pattern,
                        "Strategy Signal": action,
                        "Timestamp": str(s_data.index[-1].strftime('%H:%M:%S'))
                    }]
                    st.success(f"Single stock analysis completed for {single_search_symbol}!")
            except Exception as single_err:
                st.error(f"Error executing custom stock lookup: {single_err}")

    # =========================================================================
    # OPTION 2: FULL MARKET INDEX SCREENER
    # =========================================================================
    st.markdown("---")
    st.markdown("### 📊 Option 2: Full Market Index / Watchlist Scan")
    
    index_selection = st.selectbox(
        "Select Market Index to Scan:",
        options=["NASDAQ 100 (US - Tech)", "S&P 500 (US - Mixed)", "FTSE 100 (UK - LSE)", "Volatile Watchlist (Hybrid)"],
        key="screener_index_selector"
    )
    
    watchlist_tickers = load_index_tickers(index_selection)
    st.info(f"Loaded **{len(watchlist_tickers)}** tickers for {index_selection}.")
    
    num_tickers = len(watchlist_tickers)
    slider_max = max(1, num_tickers)
    
    scan_limit = st.slider(
        "Limit scan size (Up to maximum watchlist length):", 
        min_value=0, 
        max_value=slider_max, 
        value=min(100, num_tickers)
    )
    
    if st.button("🚀 Run Live Index Scan"):
        if scan_limit == 0:
            st.warning("Scan limit is set to 0. Please increase the limit to scan stocks.")
        else:
            screener_results = []
            progress_placeholder = st.empty()
            progress_bar = st.progress(0)
            
            active_scan_list = list(watchlist_tickers)[:scan_limit]
            total_tickers = len(active_scan_list)
            
            BATCH_SIZE = 10  
            ticker_batches = [active_scan_list[i:i + BATCH_SIZE] for i in range(0, len(active_scan_list), BATCH_SIZE)]
            total_batches = len(ticker_batches)
            
            processed_count = 0
            
            for batch_idx, batch in enumerate(ticker_batches):
                progress_placeholder.text(f"Downloading batch {batch_idx + 1} of {total_batches} ({len(batch)} symbols)...")
                
                try:
                    bulk_data = yf.download(
                        tickers=batch,
                        period="5d",
                        interval=tf_settings['yf_interval'],
                        threads=False,   
                        progress=False,
                        timeout=10
                    )
                    
                    if bulk_data.empty:
                        processed_count += len(batch)
                        continue
                        
                    for s_ticker in batch:
                        processed_count += 1
                        progress_bar.progress(int((processed_count) / total_tickers * 100))
                        
                        try:
                            if len(batch) > 1:
                                s_data = bulk_data.xs(s_ticker, axis=1, level=1).dropna()
                            else:
                                s_data = bulk_data.dropna()
                                
                            if s_data.empty:
                                continue
                            
                            s_close = s_data['Close'].squeeze()
                            s_high = s_data['High'].squeeze()
                            s_low = s_data['Low'].squeeze()
                            s_open = s_data['Open'].squeeze()
                            s_volume = s_data['Volume'].squeeze()
                            
                            s_delta = s_close.diff()
                            s_gain = (s_delta.where(s_delta > 0, 0)).rolling(window=rsi_period).mean()
                            s_loss = (-s_delta.where(s_delta < 0, 0)).rolling(window=rsi_period).mean()
                            s_rs = s_gain / s_loss
                            s_rsi = 100 - (100 / (1 + s_rs))
                            s_vol_sma = s_volume.rolling(window=10).mean()
                            
                            current_price = float(s_close.iloc[-1])
                            current_rsi = float(s_rsi.iloc[-1])
                            current_vol = float(s_volume.iloc[-1])
                            current_vol_sma = float(s_vol_sma.iloc[-1])
                            
                            if current_vol >= 1_000_000_000:
                                vol_str = f"{current_vol / 1_000_000_000:.2f}B"
                            elif current_vol >= 1_000_000:
                                vol_str = f"{current_vol / 1_000_000:.2f}M"
                            elif current_vol >= 1_000:
                                vol_str = f"{current_vol / 1_000:.1f}K"
                            else:
                                vol_str = str(int(current_vol))
                            
                            s_body = (s_close - s_open).abs()
                            s_range = s_high - s_low
                            s_range = s_range.replace(0, 0.00001)
                            s_upper_shadow = s_high - s_data[['Close', 'Open']].max(axis=1).squeeze()
                            s_lower_shadow = s_data[['Close', 'Open']].min(axis=1).squeeze() - s_low
                            
                            detected_pattern = "⚪ No Pattern"
                            if (s_lower_shadow.iloc[-1] > (2 * s_body.iloc[-1])) and (s_upper_shadow.iloc[-1] < (0.1 * s_range.iloc[-1])) and (current_rsi < 40):
                                detected_pattern = "🟢 BULLISH HAMMER"
                            elif (s_upper_shadow.iloc[-1] > (2 * s_body.iloc[-1])) and (s_lower_shadow.iloc[-1] < (0.1 * s_range.iloc[-1])) and (current_rsi > 60):
                                detected_pattern = "🔴 BEARISH SHOOTING STAR"
                            else:
                                p_close, p_open = s_close.iloc[-2], s_open.iloc[-2]
                                c_close, c_open = s_close.iloc[-1], s_open.iloc[-1]
                                if (p_close < p_open) and (c_close > c_open) and (c_open <= p_close) and (c_close >= p_open):
                                    detected_pattern = "🟢 BULLISH ENGULFING"
                                elif (p_close > p_open) and (c_close < c_open) and (c_open >= p_close) and (c_close <= p_open):
                                    detected_pattern = "🔴 BEARISH ENGULFING"
                            
                            action = "⚪ HOLD / NEUTRAL"
                            if strategy_type == "All-in-One Confluence":
                                s_fast = s_close.ewm(span=fast_span, adjust=False).mean()
                                s_slow = s_close.ewm(span=slow_span, adjust=False).mean()
                                typical_price = (s_high + s_low + s_close) / 3
                                tp_vol = typical_price * s_volume
                                dates = s_data.index.date
                                cum_tp_vol = tp_vol.groupby(dates).cumsum()
                                cum_vol = s_volume.groupby(dates).cumsum()
                                s_vwap = cum_tp_vol / cum_vol
                                
                                if (float(s_fast.iloc[-1]) > float(s_slow.iloc[-1])) and (current_price > float(s_vwap.iloc[-1])) and (40 <= current_rsi <= 65) and (current_vol > current_vol_sma * 0.8):
                                    action = "🟢 STRATEGY BUY"
                                elif (float(s_fast.iloc[-1]) < float(s_slow.iloc[-1])) or (current_price < float(s_vwap.iloc[-1])) or (current_rsi > 70):
                                    action = "🔴 STRATEGY SELL"

                            elif strategy_type == "RSI Range Spotter":
                                if (current_rsi >= rsi_min) and (current_rsi <= rsi_max) and (current_vol > current_vol_sma * 0.8):
                                    action = "🟢 STRATEGY BUY"
                                elif current_rsi > 65:
                                    action = "🔴 STRATEGY SELL"
                                    
                            elif strategy_type == "VWAP Pullback":
                                typical_price = (s_high + s_low + s_close) / 3
                                tp_vol = typical_price * s_volume
                                dates = s_data.index.date
                                cum_tp_vol = tp_vol.groupby(dates).cumsum()
                                cum_vol = s_volume.groupby(dates).cumsum()
                                s_vwap_series = cum_tp_vol / cum_vol
                                current_vwap = float(s_vwap_series.iloc[-1])
                                
                                if (current_price > current_vwap) and (float(s_close.iloc[-2]) <= float(s_vwap_series.iloc[-2])) and (current_rsi < rsi_oversold):
                                    action = "🟢 STRATEGY BUY"
                                elif current_price < current_vwap:
                                    action = "🔴 STRATEGY SELL"
                                    
                            else: 
                                s_fast = s_close.ewm(span=fast_span, adjust=False).mean()
                                s_slow = s_close.ewm(span=slow_span, adjust=False).mean()
                                if (float(s_fast.iloc[-1]) > float(s_slow.iloc[-1])) and (current_rsi < 70):
                                    action = "🟢 STRATEGY BUY"
                                else:
                                    action = "🔴 STRATEGY SELL"
                            
                            screener_results.append({
                                "Stock": s_ticker,
                                "Current Price": f"${current_price:.2f}" if not s_ticker.endswith(".L") else f"£{current_price/100:.2f}",
                                "Volume": vol_str,
                                "RSI": round(current_rsi, 1),
                                "Candle Pattern": detected_pattern,
                                "Strategy Signal": action,
                                "Timestamp": str(s_data.index[-1].strftime('%H:%M:%S'))
                            })
                            
                        except Exception:
                            continue
                    time.sleep(0.5) 
                except Exception:
                    processed_count += len(batch)
                    continue
                    
            progress_placeholder.success(f"Successfully scanned {len(screener_results)} stocks!")
            st.session_state.scan_results = screener_results

    # =========================================================================
    # RENDER DATA TABLE & INSTANT SEARCH FILTER
    # =========================================================================
    if st.session_state.scan_results is not None:
        df_results = pd.DataFrame(st.session_state.scan_results)
        
        st.markdown("---")
        st.subheader("🎯 Filter Displayed Table Results")
        search_filter = st.text_input("Type a string to instantly filter columns below:", key="live_table_search_box").strip().upper()
        
        if search_filter:
            df_results = df_results[
                df_results['Stock'].str.contains(search_filter, case=False, na=False) |
                df_results['Candle Pattern'].str.contains(search_filter, case=False, na=False) |
                df_results['Strategy Signal'].str.contains(search_filter, case=False, na=False)
            ]
        
        def style_status(val):
            if "🟢" in str(val):
                return 'background-color: #d4edda; color: #155724; font-weight: bold;'
            elif "🔴" in str(val):
                return 'background-color: #f8d7da; color: #721c24; font-weight: bold;'
            return 'background-color: #e2e3e5; color: #383d41;'
        
        styled_df = df_results.style.map(style_status, subset=['Candle Pattern', 'Strategy Signal'])
        st.data_editor(styled_df, use_container_width=True, height=500, disabled=True)