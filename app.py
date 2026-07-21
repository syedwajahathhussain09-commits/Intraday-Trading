import streamlit as st
import streamlit.components.v1 as components
import pandas as pd
import numpy as np
import yfinance as yf
import matplotlib.pyplot as plt
import time
import urllib.request
import io

# 1. Page Configuration
st.set_page_config(page_title="Global Intraday Screener", layout="wide")
st.title("📈 Global Intraday Trading & Screener Dashboard")

COMMON_NAME_TRANSLATOR = {
    "NETFLIX": "NFLX", "APPLE": "AAPL", "MICROSOFT": "MSFT",
    "TESLA": "TSLA", "NVIDIA": "NVDA", "AMAZON": "AMZN",
    "GOOGLE": "GOOGL", "META": "META", "COCA COLA": "KO",
    "RELIANCE": "RELIANCE.NS", "TATA": "TCS.NS", "TCS": "TCS.NS",
    "INFOSYS": "INFY.NS", "HDFC": "HDFCBANK.NS", "SBI": "SBIN.NS",
    "COINBASE": "COIN", "PALANTIR": "PLTR", "MARATHON": "MARA",
    "AMD": "AMD", "MICRON": "MU"
}

# Fix #5: Resilient dynamic scraping with exchange mapping
@st.cache_data(ttl=86400)
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
                cols = [str(c).lower() for c in t.columns]
                if any(x in cols for x in ['ticker', 'symbol']):
                    col_name = t.columns[cols.index('ticker')] if 'ticker' in cols else t.columns[cols.index('symbol')]
                    tickers = t[col_name].dropna().astype(str).str.replace('.', '-', regex=False).tolist()
                    tickers = [s.strip() for s in tickers if s.strip().isalpha()]
                    if len(tickers) > 50:
                        return sorted(list(set(tickers)))
            return ["AAPL", "MSFT", "AMZN", "NVDA", "TSLA", "META", "GOOGL", "GOOG", "NFLX", "AMD", "INTC", "PYPL", "ADBE", "COST", "PEP"]

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

        else:
            return ["TSLA", "NVDA", "AAPL", "PLTR", "COIN", "AMD", "NFLX", "MARA", "MU", "RELIANCE.NS", "SBIN.NS"]
            
    except Exception as e:
        st.warning(f"Failed to fetch live {index_name} components: {e}")
        return ["TSLA", "NVDA", "AAPL", "MSFT", "AMD", "PLTR", "COIN", "NFLX"]

# Fix #5: TradingView Symbol Formatter
def format_tv_symbol(ticker_symbol):
    ticker_symbol = ticker_symbol.strip().upper()
    if ticker_symbol.endswith(".NS"):
        return f"NSE:{ticker_symbol.replace('.NS', '')}"
    if ticker_symbol.endswith(".L"):
        return f"LSE:{ticker_symbol.replace('.L', '')}"
    
    # Handle US Symbols
    clean_sym = ticker_symbol.replace('-', '.').replace('_', '.')
    return f"NASDAQ:{clean_sym}" if ticker_symbol in ["AAPL", "MSFT", "TSLA", "NVDA", "AMZN", "GOOGL", "META", "NFLX", "QQQ", "COIN", "PLTR", "AMD"] else f"NYSE:{clean_sym}"

# Fix #2: Unified Calculation Engine Function
def compute_signals(df, strategy_type, params):
    """
    Unified calculation engine for RSI, VWAP, EMAs, Candlestick Patterns, and Strategy Signals.
    Returns calculated dataframe along with the latest state metadata dictionary.
    """
    if df.empty or len(df) < 2:
        return df, None

    data = df.copy()
    close_series = data['Close'].squeeze()
    high_series = data['High'].squeeze()
    low_series = data['Low'].squeeze()
    open_series = data['Open'].squeeze()
    volume_series = data['Volume'].squeeze()

    rsi_period = params.get('rsi_period', 14)
    fast_span = params.get('fast_span', 9)
    slow_span = params.get('slow_span', 21)

    # 1. RSI with Fix #7 (0/0 division & NaN Handling)
    delta = close_series.diff()
    gain = (delta.where(delta > 0, 0)).rolling(window=rsi_period).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(window=rsi_period).mean()
    rs = gain / loss
    data['RSI'] = (100 - (100 / (1 + rs))).fillna(50)  # Handles NaN gracefully

    data['Vol_SMA'] = volume_series.rolling(window=10).mean()
    data['Signal'] = 0

    # 2. Moving Averages & VWAP
    data['EMA_Fast'] = close_series.ewm(span=fast_span, adjust=False).mean()
    data['EMA_Slow'] = close_series.ewm(span=slow_span, adjust=False).mean()

    typical_price = (high_series + low_series + close_series) / 3
    tp_vol = typical_price * volume_series
    dates = data.index.date
    cum_tp_vol = tp_vol.groupby(dates).cumsum()
    cum_vol = volume_series.groupby(dates).cumsum()
    data['VWAP'] = (cum_tp_vol / cum_vol).replace([np.inf, -np.inf], np.nan).ffill()

    # 3. Strategy Signals
    if strategy_type == "All-in-One Confluence":
        data.loc[
            (data['EMA_Fast'] > data['EMA_Slow']) & 
            (close_series > data['VWAP']) & 
            (data['RSI'] >= 40) & (data['RSI'] <= 65) &
            (volume_series > (data['Vol_SMA'] * 0.8)), 
            'Signal'
        ] = 1
        
        data.loc[
            (data['EMA_Fast'] < data['EMA_Slow']) | 
            (close_series < data['VWAP']) | 
            (data['RSI'] > 70), 
            'Signal'
        ] = -1

    elif strategy_type == "RSI Range Spotter":
        data.loc[
            (data['RSI'] >= params.get('rsi_min', 30)) & 
            (data['RSI'] <= params.get('rsi_max', 35)) & 
            (volume_series > (data['Vol_SMA'] * 0.8)), 
            'Signal'
        ] = 1
        data.loc[(data['RSI'] > 65), 'Signal'] = -1

    elif strategy_type == "VWAP Pullback":
        data.loc[
            (close_series > data['VWAP']) & 
            (close_series.shift(1) <= data['VWAP']) & 
            (data['RSI'] < params.get('rsi_oversold', 60)) & 
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

    # Fix #1: Position transitions correctly track all state changes (0->1, 1->0, 0->-1, 1->-1)
    data['Position'] = data['Signal'].diff()

    # 4. Candlestick Pattern Detector
    body = (close_series - open_series).abs()
    candle_range = (high_series - low_series).replace(0, 0.00001)
    upper_shadow = high_series - data[['Close', 'Open']].max(axis=1).squeeze()
    lower_shadow = data[['Close', 'Open']].min(axis=1).squeeze() - low_series

    data['Pattern'] = "⚪ No Pattern"
    
    is_hammer = (lower_shadow > (2 * body)) & (upper_shadow < (0.1 * candle_range)) & (data['RSI'] < 40)
    data.loc[is_hammer, 'Pattern'] = "🟢 BULLISH HAMMER"
    
    is_shooting_star = (upper_shadow > (2 * body)) & (lower_shadow < (0.1 * candle_range)) & (data['RSI'] > 60)
    data.loc[is_shooting_star, 'Pattern'] = "🔴 BEARISH SHOOTING STAR"
    
    prev_close, prev_open = close_series.shift(1), open_series.shift(1)
    is_bullish_engulfing = (prev_close < prev_open) & (close_series > open_series) & (open_series <= prev_close) & (close_series >= prev_open)
    is_bearish_engulfing = (prev_close > prev_open) & (close_series < open_series) & (open_series >= prev_close) & (close_series <= prev_open)
    
    data.loc[is_bullish_engulfing, 'Pattern'] = "🟢 BULLISH ENGULFING"
    data.loc[is_bearish_engulfing, 'Pattern'] = "🔴 BEARISH ENGULFING"

    # Volume Alert Calculation
    current_vol = float(volume_series.iloc[-1])
    current_vol_sma = float(data['Vol_SMA'].iloc[-1])
    vol_surge_ratio = current_vol / current_vol_sma if current_vol_sma > 0 else 1.0
    
    if vol_surge_ratio >= 2.0:
        vol_alert = f"⚡ SURGE ({vol_surge_ratio:.1f}x)"
    elif vol_surge_ratio >= 1.5:
        vol_alert = f"🔥 HIGH ({vol_surge_ratio:.1f}x)"
    else:
        vol_alert = "⚪ NORMAL"

    # Action Mapping
    current_sig = data['Signal'].iloc[-1]
    action = "🟢 STRATEGY BUY" if current_sig == 1 else ("🔴 STRATEGY SELL" if current_sig == -1 else "⚪ HOLD / NEUTRAL")

    latest_info = {
        "price": float(close_series.iloc[-1]),
        "rsi": float(data['RSI'].iloc[-1]),
        "volume": current_vol,
        "vol_alert": vol_alert,
        "pattern": data['Pattern'].iloc[-1],
        "action": action,
        "signal": current_sig,
        "timestamp": str(data.index[-1].strftime('%H:%M:%S'))
    }

    return data, latest_info

TIMEFRAME_MAP = {
    "5 Min": {"yf_interval": "5m", "yf_period": "5d", "tv_interval": "5"},
    "15 Min": {"yf_interval": "15m", "yf_period": "1mo", "tv_interval": "15"},
    "30 Min": {"yf_interval": "30m", "yf_period": "1mo", "tv_interval": "30"},
    "1 Hour": {"yf_interval": "60m", "yf_period": "2y", "tv_interval": "60"},
    "1 Day": {"yf_interval": "1d", "yf_period": "5y", "tv_interval": "D"}
}

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

strategy_type = st.sidebar.selectbox(
    "Choose Strategy:",
    options=["All-in-One Confluence", "RSI Range Spotter", "VWAP Pullback", "EMA Crossover"]
)

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

selected_tf = st.sidebar.selectbox(
    "Select Chart Timeframe:",
    options=list(TIMEFRAME_MAP.keys()),
    index=0 
)
tf_settings = TIMEFRAME_MAP[selected_tf]

include_extended_hours = st.sidebar.checkbox(
    "🌅/🌙 Include Pre & Post-Market Data",
    value=True,
    help="Enable to track trading activity outside regular market hours (4:00 AM - 8:00 PM EST)."
)

# Strategy Parameters
st.sidebar.subheader("Strategy Settings")
params = {}
params['rsi_period'] = st.sidebar.slider("RSI Period", min_value=5, max_value=30, value=14)

if strategy_type == "All-in-One Confluence":
    params['fast_span'] = st.sidebar.slider("Fast EMA", min_value=3, max_value=20, value=9)
    params['slow_span'] = st.sidebar.slider("Slow EMA", min_value=10, max_value=50, value=21)
elif strategy_type == "RSI Range Spotter":
    params['rsi_min'] = st.sidebar.slider("RSI Min Floor", min_value=10, max_value=50, value=30)
    params['rsi_max'] = st.sidebar.slider("RSI Max Ceiling", min_value=15, max_value=60, value=35)
elif strategy_type == "VWAP Pullback":
    params['rsi_oversold'] = st.sidebar.slider("RSI Entry Threshold (Max)", min_value=30, max_value=70, value=60)
elif strategy_type == "EMA Crossover":
    params['fast_span'] = st.sidebar.slider("Fast EMA", min_value=3, max_value=20, value=9)
    params['slow_span'] = st.sidebar.slider("Slow EMA", min_value=10, max_value=50, value=21)

tv_symbol = format_tv_symbol(ticker)
tab1, tab2, tab3 = st.tabs(["📺 Live TradingView Chart", "📊 Python Strategy Signals", "🔍 Real-Time Index Screener"])

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

# --- TAB 2: Custom Strategy Signals ---
with tab2:
    st.subheader(f"{strategy_type} Strategy Analysis ({selected_tf})")
    
    with st.spinner(f"Downloading {selected_tf} data for {ticker}..."):
        try:
            raw_data = yf.download(
                ticker, 
                period=tf_settings['yf_period'], 
                interval=tf_settings['yf_interval'],
                prepost=include_extended_hours,
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
        # Call Centralized Calculation Engine
        data, latest_info = compute_signals(data, strategy_type, params)
        
        # Display Candlestick Findings
        latest_pattern = latest_info['pattern']
        if "🟢" in latest_pattern:
            st.success(f"**Current Candle Pattern:** {latest_pattern} detected on the {selected_tf} timeframe!")
        elif "🔴" in latest_pattern:
            st.error(f"**Current Candle Pattern:** {latest_pattern} detected on the {selected_tf} timeframe!")
        else:
            st.info(f"**Current Candle Pattern:** No clear reversal candlestick pattern formed on the current {selected_tf} bar.")

        # Live Advisor Module
        st.markdown("---")
        st.markdown("### 🚨 Live Signal Advisor & Market Session Status")
        
        # Fix #6: Use fast_info exclusively (Fast & Reliable)
        try:
            live_ticker = yf.Ticker(ticker)
            fast = live_ticker.fast_info
            last_price = float(fast['last_price'])
            prev_close = float(fast['previous_close'])
            price_change = last_price - prev_close
            pct_change = (price_change / prev_close) * 100
        except Exception:
            last_price = latest_info['price']
            price_change, pct_change = 0.0, 0.0

        chg_color = "🟢" if price_change >= 0 else "🔴"
        st.info(f"**Live Price:** `${last_price:.2f}` ({chg_color} `{price_change:+.2f}` / `{pct_change:+.2f}%`) | **Last Bar Timestamp:** `{data.index[-1].strftime('%Y-%m-%d %H:%M EST')}`")
        
        # ATR Calculation
        close_s, high_s, low_s = data['Close'].squeeze(), data['High'].squeeze(), data['Low'].squeeze()
        high_low = high_s - low_s
        high_close = (high_s - close_s.shift()).abs()
        low_close = (low_s - close_s.shift()).abs()
        ranges = pd.concat([high_low, high_close, low_close], axis=1)
        atr_value = float(ranges.max(axis=1).rolling(window=14).mean().iloc[-1])

        last_signal = latest_info['signal']
        last_rsi = latest_info['rsi']

        col_sig, col_metrics = st.columns([1.5, 2])
        with col_sig:
            if last_signal == 1:
                st.success(f"### 🟢 ACTIVE ACTION: BUY / LONG\n**Live Price:** ${last_price:.2f} | **RSI:** {last_rsi:.1f}")
                st.markdown(f"""
                * **Suggested Entry:** Around `${last_price:.2f}`
                * **Stop Loss (1.5x ATR):** `${last_price - (1.5 * atr_value):.2f}`
                * **Profit Target (3x ATR):** `${last_price + (3.0 * atr_value):.2f}`
                """)
            elif last_signal == -1:
                st.error(f"### 🔴 ACTIVE ACTION: SELL / SHORT / EXIT\n**Live Price:** ${last_price:.2f} | **RSI:** {last_rsi:.1f}")
                st.markdown(f"""
                * **Suggested Entry:** Around `${last_price:.2f}`
                * **Stop Loss (1.5x ATR):** `${last_price + (1.5 * atr_value):.2f}`
                * **Profit Target (3x ATR):** `${last_price - (3.0 * atr_value):.2f}`
                """)
            else:
                st.info(f"### ⚪ ACTIVE ACTION: HOLD / NO SIGNAL\n**Live Price:** ${last_price:.2f} | **RSI:** {last_rsi:.1f}")

        # Session Volume Formatting
        def format_vol(v):
            if v >= 1_000_000_000: return f"{v / 1_000_000_000:.2f}B"
            elif v >= 1_000_000: return f"{v / 1_000_000:.2f}M"
            elif v >= 1_000: return f"{v / 1_000:.1f}K"
            return str(int(v))

        formatted_bar_vol = format_vol(latest_info['volume'])
        col_m1, col_m2, col_m3, col_m4 = st.columns(4)
        col_m1.metric("Live Price", f"${last_price:.2f}", f"{price_change:+.2f} ({pct_change:+.2f}%)")
        col_m2.metric("Current RSI", f"{last_rsi:.1f}")
        col_m3.metric("Bar Volume", formatted_bar_vol, delta=latest_info['vol_alert'])
        col_m4.metric("Strategy Signal", "BUY" if last_signal == 1 else ("SELL" if last_signal == -1 else "NEUTRAL"))

        # Plotting
        st.markdown("---")
        plot_data = data.tail(100)
        fig, (ax1, ax2, ax3) = plt.subplots(3, 1, figsize=(12, 10), sharex=True, gridspec_kw={'height_ratios': [3, 1, 1]})
        
        ax1.plot(plot_data.index, plot_data['Close'], label='Close Price', color='black', alpha=0.7)
        if strategy_type in ["VWAP Pullback", "All-in-One Confluence"] and 'VWAP' in plot_data.columns:
            ax1.plot(plot_data.index, plot_data['VWAP'], label='VWAP', color='purple', linewidth=2)
        if strategy_type in ["EMA Crossover", "All-in-One Confluence"] and 'EMA_Fast' in plot_data.columns:
            ax1.plot(plot_data.index, plot_data['EMA_Fast'], label='Fast EMA', color='blue', linestyle='--')
            ax1.plot(plot_data.index, plot_data['EMA_Slow'], label='Slow EMA', color='orange', linestyle='--')
        ax1.set_title(f"{ticker} - {selected_tf} Price & Signals", fontsize=14, fontweight='bold')
        ax1.legend(loc='upper left')
        ax1.grid(True, alpha=0.3)

        ax2.plot(plot_data.index, plot_data['RSI'], label='RSI', color='orange')
        ax2.axhline(70, color='red', linestyle='--', alpha=0.5)
        ax2.axhline(30, color='green', linestyle='--', alpha=0.5)
        ax2.set_ylabel("RSI")
        ax2.grid(True, alpha=0.3)

        colors = ['green' if c >= o else 'red' for c, o in zip(plot_data['Close'], plot_data['Open'])]
        ax3.bar(plot_data.index, plot_data['Volume'], color=colors, alpha=0.6, width=0.003)
        ax3.set_ylabel("Volume")
        ax3.grid(True, alpha=0.3)
        st.pyplot(fig)

        # Fix #1: Execution Logs capture ALL state transitions (nonzero Position diffs)
        st.markdown("### 📜 Recent Signal Execution Logs")
        history = data[data['Position'].notnull() & (data['Position'] != 0)].copy()
        
        if not history.empty:
            def log_action(pos):
                if pos in [1, 2]: return "🟢 BUY ENTRY"
                elif pos in [-1, -2]: return "🔴 SELL / EXIT"
                return "⚪ NEUTRAL TRANSITION"

            history['Action'] = history['Position'].apply(log_action)
            history['Price'] = history['Close'].round(2)
            history['RSI_at_Trigger'] = history['RSI'].round(1)
            
            history_display = history[['Action', 'Price', 'RSI_at_Trigger']].tail(10).sort_index(ascending=False)
            st.dataframe(history_display, use_container_width=True)
        else:
            st.info("No signal state changes found in the loaded historical window.")

    except Exception as calculation_error:
        st.error(f"Error calculating strategy: {calculation_error}")

# --- TAB 3: Real-Time Index Screener ---
with tab3:
    st.subheader("🔍 High-Speed Global Index Screener")
    st.write("Scan entire market indices or run an on-demand real-time check on any custom stock symbol.")
    
    if "scan_results" not in st.session_state:
        st.session_state.scan_results = None

    # OPTION 1: QUICK SINGLE CUSTOM STOCK SCANNER
    st.markdown("### 🎯 Option 1: Quick Scan a Single Custom Stock")
    col_search, col_search_btn = st.columns([3, 1])
    
    with col_search:
        single_search_symbol = st.text_input(
            "Enter raw symbol to scan immediately (e.g. TSLA, BARC.L, RELIANCE.NS):", 
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
                    st.error(f"Could not retrieve data for '{single_search_symbol}'.")
                else:
                    # Use Central Compute Engine
                    _, s_info = compute_signals(s_data, strategy_type, params)
                    
                    # Fix #8: LSE pricing comment/format
                    price_fmt = f"£{s_info['price']/100:.2f}" if single_search_symbol.endswith(".L") else f"${s_info['price']:.2f}"

                    st.session_state.scan_results = [{
                        "Stock": single_search_symbol,
                        "Current Price": price_fmt,
                        "Volume": format_vol(s_info['volume']),
                        "Volume Alert": s_info['vol_alert'],
                        "RSI": round(s_info['rsi'], 1),
                        "Candle Pattern": s_info['pattern'],
                        "Strategy Signal": s_info['action'],
                        "Timestamp": s_info['timestamp']
                    }]
                    st.success(f"Single stock analysis completed for {single_search_symbol}!")
            except Exception as single_err:
                st.error(f"Error executing custom stock lookup: {single_err}")

    # OPTION 2: FULL MARKET INDEX SCREENER
    st.markdown("---")
    st.markdown("### 📊 Option 2: Full Market Index / Watchlist Scan")
    
    index_selection = st.selectbox(
        "Select Market Index to Scan:",
        options=["NASDAQ 100 (US - Tech)", "S&P 500 (US - Mixed)", "FTSE 100 (UK - LSE)", "Volatile Watchlist (Hybrid)"],
        key="screener_index_selector"
    )
    
    watchlist_tickers = load_index_tickers(index_selection)
    num_tickers = len(watchlist_tickers)
    
    # Fix #8: Slider bounds protection
    slider_max = max(1, num_tickers)
    st.info(f"Loaded **{num_tickers}** tickers for {index_selection}.")
    
    scan_limit = st.slider(
        "Limit scan size (Up to maximum watchlist length):", 
        min_value=1 if num_tickers > 0 else 0, 
        max_value=slider_max, 
        value=min(100, slider_max)
    )
    
    if st.button("🚀 Run Live Index Scan"):
        if scan_limit == 0:
            st.warning("Scan limit is set to 0. Please increase the limit.")
        else:
            screener_results = []
            failed_tickers = []  # Fix #4: Capture failed downloads explicitly
            
            progress_placeholder = st.empty()
            progress_bar = st.progress(0)
            
            active_scan_list = list(watchlist_tickers)[:scan_limit]
            total_tickers = len(active_scan_list)
            
            # Fix #3: Multi-threaded batching (50 symbols per batch, threads=True)
            BATCH_SIZE = 50  
            ticker_batches = [active_scan_list[i:i + BATCH_SIZE] for i in range(0, len(active_scan_list), BATCH_SIZE)]
            total_batches = len(ticker_batches)
            processed_count = 0
            
            for batch_idx, batch in enumerate(ticker_batches):
                progress_placeholder.text(f"Downloading batch {batch_idx + 1} of {total_batches} ({len(batch)} symbols)...")
                
                try:
                    # Fix #3: Enabled threading for fast network execution
                    bulk_data = yf.download(
                        tickers=batch,
                        period="5d",
                        interval=tf_settings['yf_interval'],
                        threads=True,   
                        progress=False,
                        timeout=15
                    )
                    
                    if bulk_data.empty:
                        failed_tickers.extend(batch)
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
                                
                            if s_data.empty or len(s_data) < 2:
                                failed_tickers.append(s_ticker)
                                continue
                            
                            # Fix #2: Compute signals using unified engine
                            _, s_info = compute_signals(s_data, strategy_type, params)
                            
                            price_fmt = f"£{s_info['price']/100:.2f}" if s_ticker.endswith(".L") else f"${s_info['price']:.2f}"

                            screener_results.append({
                                "Stock": s_ticker,
                                "Current Price": price_fmt,
                                "Volume": format_vol(s_info['volume']),
                                "Volume Alert": s_info['vol_alert'],
                                "RSI": round(s_info['rsi'], 1),
                                "Candle Pattern": s_info['pattern'],
                                "Strategy Signal": s_info['action'],
                                "Timestamp": s_info['timestamp']
                            })
                            
                        except Exception:
                            failed_tickers.append(s_ticker)
                            continue
                except Exception:
                    failed_tickers.extend(batch)
                    processed_count += len(batch)
                    continue
                    
            progress_placeholder.success(f"Successfully scanned {len(screener_results)} stocks!")
            st.session_state.scan_results = screener_results

            # Fix #4: Show failed symbols expander
            if failed_tickers:
                with st.expander(f"⚠️ Failed or Missing Symbols ({len(failed_tickers)})"):
                    st.write(", ".join(failed_tickers))

    # RENDER DATA TABLE
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
            if "🟢" in str(val): return 'background-color: #d4edda; color: #155724; font-weight: bold;'
            elif "🔴" in str(val): return 'background-color: #f8d7da; color: #721c24; font-weight: bold;'
            return 'background-color: #e2e3e5; color: #383d41;'
        
        styled_df = df_results.style.map(style_status, subset=['Candle Pattern', 'Strategy Signal'])
        st.data_editor(styled_df, use_container_width=True, height=500, disabled=True)