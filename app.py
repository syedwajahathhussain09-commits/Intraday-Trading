import streamlit as st
import streamlit.components.v1 as components
import pandas as pd
import yfinance as yf
import matplotlib.pyplot as plt
import time

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

# Helper function to scrape live Index Tickers dynamically
@st.cache_data(ttl=86400) # Cache index composition for 24 hours to keep page loading super fast
def load_index_tickers(index_name):
    try:
        if index_name == "S&P 500 (US - Mixed)":
            url = 'https://en.wikipedia.org/wiki/List_of_S%26P_500_companies'
            table = pd.read_html(url, attrs={'id': 'constituents'})[0]
            # yfinance uses dots instead of dashes for multi-class shares (e.g. BRK.B instead of BRK-B)
            tickers = table['Symbol'].str.replace('.', '-', regex=False).tolist()
            return sorted(tickers)
            
        elif index_name == "NASDAQ 100 (US - Tech)":
            url = 'https://en.wikipedia.org/wiki/Nasdaq-100'
            tables = pd.read_html(url)
            # Find the constituents table
            for t in tables:
                if 'Ticker' in t.columns:
                    return sorted(t['Ticker'].tolist())
            return ["AAPL", "MSFT", "AMZN", "NVDA", "TSLA", "META", "GOOGL", "NFLX", "AMD", "INTC"]

        elif index_name == "FTSE 100 (UK - LSE)":
            url = 'https://en.wikipedia.org/wiki/FTSE_100_Index'
            tables = pd.read_html(url)
            for t in tables:
                if 'EPIC' in t.columns:
                    # LSE tickers on Yahoo Finance need the ".L" suffix
                    return sorted([f"{str(sym).strip()}.L" for sym in t['EPIC'].tolist()])
            return ["SHEL.L", "AZN.L", "HSBA.L", "ULVR.L", "BP.L", "GSK.L", "RIO.L", "LLOY.L"]

        else: # Custom Volatile Watchlist
            return ["TSLA", "NVDA", "AAPL", "PLTR", "COIN", "AMD", "NFLX", "MARA", "MU", "RELIANCE.NS", "SBIN.NS"]
    except Exception as e:
        # Fail-safe backup list if Wikipedia rejects the scraping request
        st.warning(f"Failed to fetch live {index_name} components from Wikipedia (using backup list): {e}")
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
    options=["RSI Range Spotter", "VWAP Pullback", "EMA Crossover"]
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

# 4. Parameters based on Strategy
st.sidebar.subheader("Strategy Settings")
rsi_period = st.sidebar.slider("RSI Period", min_value=5, max_value=30, value=14)

if strategy_type == "RSI Range Spotter":
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
        close_series = data['Close'].squeeze()
        high_series = data['High'].squeeze()
        low_series = data['Low'].squeeze()
        volume_series = data['Volume'].squeeze()

        # Calculate Indicators
        delta = close_series.diff()
        gain = (delta.where(delta > 0, 0)).rolling(window=rsi_period).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(window=rsi_period).mean()
        rs = gain / loss
        data['RSI'] = 100 - (100 / (1 + rs))
        
        data['Vol_SMA'] = volume_series.rolling(window=10).mean()
        data['Signal'] = 0

        if strategy_type == "RSI Range Spotter":
            data.loc[
                (data['RSI'] >= rsi_min) & 
                (data['RSI'] <= rsi_max) & 
                (volume_series > (data['Vol_SMA'] * 0.8)), 
                'Signal'
            ] = 1
            
            data.loc[
                (data['RSI'] > 65), 
                'Signal'
            ] = -1

        elif strategy_type == "VWAP Pullback":
            typical_price = (high_series + low_series + close_series) / 3
            tp_vol = typical_price * volume_series
            dates = data.index.date
            cum_tp_vol = tp_vol.groupby(dates).cumsum()
            cum_vol = volume_series.groupby(dates).cumsum()
            data['VWAP'] = cum_tp_vol / cum_vol
            
            data.loc[
                (close_series > data['VWAP']) & 
                (close_series.shift(1) <= data['VWAP']) & 
                (data['RSI'] < rsi_oversold) & 
                (volume_series > data['Vol_SMA'] * 0.9), 
                'Signal'
            ] = 1
            
            data.loc[
                (close_series < data['VWAP']), 
                'Signal'
            ] = -1

        else:
            # EMA Crossover
            data['EMA_Fast'] = close_series.ewm(span=fast_span, adjust=False).mean()
            data['EMA_Slow'] = close_series.ewm(span=slow_span, adjust=False).mean()
            
            data.loc[
                (data['EMA_Fast'] > data['EMA_Slow']) & 
                (data['RSI'] < 70) & 
                (volume_series > (data['Vol_SMA'] * 0.9)), 
                'Signal'
            ] = 1
            
            data.loc[
                (data['EMA_Fast'] < data['EMA_Slow']) | 
                (data['RSI'] > 70), 
                'Signal'
            ] = -1

        data['Position'] = data['Signal'].diff()

        # =========================================================================
        # LIVE SIGNAL ADVISOR MODULE
        # =========================================================================
        st.markdown("---")
        st.markdown("### 🚨 Live Signal Advisor")
        
        last_row = data.iloc[-1]
        last_price = float(close_series.iloc[-1])
        last_rsi = float(data['RSI'].iloc[-1])
        last_signal = int(last_row['Signal'])
        
        # ATR Calculation
        high_low = high_series - low_series
        high_close = (high_series - close_series.shift()).abs()
        low_close = (low_series - close_series.shift()).abs()
        ranges = pd.concat([high_low, high_close, low_close], axis=1)
        atr_value = float(ranges.max(axis=1).rolling(window=14).mean().iloc[-1])

        col_sig, col_metrics = st.columns([1.5, 2])
        
        with col_sig:
            if last_signal == 1:
                st.success(f"### 🟢 ACTIVE ACTION: BUY / LONG\n**Price:** ${last_price:.2f} | **RSI:** {last_rsi:.1f}")
                stop_loss = last_price - (1.5 * atr_value)
                target = last_price + (3.0 * atr_value)
                st.markdown(f"""
                * **Suggested Entry:** Around `${last_price:.2f}`
                * **Stop Loss (1.5x ATR):** `${stop_loss:.2f}`
                * **Profit Target (3x ATR):** `${target:.2f}`
                """)
            elif last_signal == -1:
                st.error(f"### 🔴 ACTIVE ACTION: SELL / SHORT / EXIT\n**Price:** ${last_price:.2f} | **RSI:** {last_rsi:.1f}")
                stop_loss = last_price + (1.5 * atr_value)
                target = last_price - (3.0 * atr_value)
                st.markdown(f"""
                * **Suggested Entry:** Around `${last_price:.2f}`
                * **Stop Loss (1.5x ATR):** `${stop_loss:.2f}`
                * **Profit Target (3x ATR):** `${target:.2f}`
                """)
            else:
                st.info(f"### ⚪ ACTIVE ACTION: HOLD / NO SIGNAL\n**Price:** ${last_price:.2f} | **RSI:** {last_rsi:.1f}")
                st.write("The strategy parameters are currently neutral. Wait for the next setup crossover or oversold range dip.")

        with col_metrics:
            c1, c2, c3 = st.columns(3)
            c1.metric(label="Last Close Price", value=f"${last_price:.2f}")
            c2.metric(label="Current RSI", value=f"{last_rsi:.1f}")
            c3.metric(label="ATR (14)", value=f"${atr_value:.2f}")

        # =========================================================================
        # PLOTTING THE STRATEGY
        # =========================================================================
        st.markdown("---")
        plot_data = data.tail(100)
        
        fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(14, 8), sharex=True, gridspec_kw={'height_ratios': [3, 1]})

        ax1.plot(plot_data.index, plot_data['Close'], label='Close Price', color='black', alpha=0.7)
        if strategy_type == "VWAP Pullback" and 'VWAP' in plot_data.columns:
            ax1.plot(plot_data.index, plot_data['VWAP'], label='VWAP', color='purple', linewidth=2)
        elif strategy_type == "EMA Crossover" and 'EMA_Fast' in plot_data.columns:
            ax1.plot(plot_data.index, plot_data['EMA_Fast'], label='Fast EMA', color='blue', linestyle='--')
            ax1.plot(plot_data.index, plot_data['EMA_Slow'], label='Slow EMA', color='orange', linestyle='--')

        buys = plot_data[plot_data['Position'] == 2]
        if not buys.empty:
            ax1.scatter(buys.index, buys['Close'], label='BUY Signal', marker='^', color='green', s=200)

        sells = plot_data[plot_data['Position'] == -2]
        if not sells.empty:
            ax1.scatter(sells.index, sells['Close'], label='SELL/EXIT', marker='v', color='red', s=200)

        ax1.set_title(f"{ticker} - {strategy_type} ({selected_tf} Chart)")
        ax1.set_ylabel("Price")
        ax1.legend()
        ax1.grid(True)

        ax2.plot(plot_data.index, plot_data['RSI'], label='RSI', color='teal', linewidth=1.5)
        ax2.axhline(70, color='red', linestyle=':', alpha=0.5)
        ax2.axhline(30, color='green', linestyle=':', alpha=0.5)
        
        if strategy_type == "RSI Range Spotter":
            ax2.axhspan(rsi_min, rsi_max, color='lightgreen', alpha=0.3, label='Buy Zone')
            
        ax2.set_ylabel("RSI")
        ax2.set_ylim(10, 90)
        ax2.legend()
        ax2.grid(True)

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
    st.subheader("🔍 Dynamic Global Index Screener")
    st.write("Scan entire index lists from the NYSE, NASDAQ, and LSE in seconds using dynamically scraped Wikipedia compositions.")
    
    # Selection of which index to scan
    index_selection = st.selectbox(
        "Select Market Index to Scan:",
        options=["NASDAQ 100 (US - Tech)", "S&P 500 (US - Mixed)", "FTSE 100 (UK - LSE)", "Volatile Watchlist (Hybrid)"]
    )
    
    # Load tickers based on choice
    watchlist_tickers = load_index_tickers(index_selection)
    st.info(f"Loaded **{len(watchlist_tickers)}** tickers for {index_selection}.")
    
    # Scan limitation slider to protect API rate-limiting
    scan_limit = st.slider("Limit scan size (Highly recommended to avoid IP ban):", min_value=10, max_value=len(watchlist_tickers), value=min(50, len(watchlist_tickers)))
    
    # Trigger Button
    if st.button("🚀 Run Live Index Scan"):
        screener_results = []
        progress_bar = st.progress(0)
        status_text = st.empty()
        
        # Sub-slice list to keep things within boundaries
        active_scan_list = watchlist_tickers[:scan_limit]
        total_tickers = len(active_scan_list)
        
        for idx, s_ticker in enumerate(active_scan_list):
            status_text.text(f"Scanning {s_ticker} ({idx+1}/{total_tickers})...")
            progress_bar.progress(int((idx + 1) / total_tickers * 100))
            
            try:
                # Download data (shorter period to accelerate screening and reduce traffic)
                s_data = yf.download(
                    s_ticker, 
                    period="5d", 
                    interval=tf_settings['yf_interval'],
                    multi_level_index=False,
                    progress=False
                )
                
                if s_data.empty:
                    continue
                    
                s_close = s_data['Close'].squeeze()
                s_high = s_data['High'].squeeze()
                s_low = s_data['Low'].squeeze()
                s_volume = s_data['Volume'].squeeze()
                
                # Indicator Calculations
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
                
                action = "⚪ HOLD / NEUTRAL"
                
                # Apply Strategy rules
                if strategy_type == "RSI Range Spotter":
                    if (current_rsi >= rsi_min) and (current_rsi <= rsi_max) and (current_vol > current_vol_sma * 0.8):
                        action = "🟢 BUY (OVERSOLD DIP)"
                    elif current_rsi > 65:
                        action = "🔴 SELL (TAKE PROFIT)"
                        
                elif strategy_type == "VWAP Pullback":
                    typical_price = (s_high + s_low + s_close) / 3
                    tp_vol = typical_price * s_volume
                    dates = s_data.index.date
                    cum_tp_vol = tp_vol.groupby(dates).cumsum()
                    cum_vol = s_volume.groupby(dates).cumsum()
                    s_vwap_series = cum_tp_vol / cum_vol
                    current_vwap = float(s_vwap_series.iloc[-1])
                    
                    if (current_price > current_vwap) and (float(s_close.iloc[-2]) <= float(s_vwap_series.iloc[-2])) and (current_rsi < rsi_oversold):
                        action = "🟢 BUY (VWAP SUPPORT TEST)"
                    elif current_price < current_vwap:
                        action = "🔴 SELL (BELLOW VWAP)"
                        
                else: # EMA Crossover
                    s_fast = s_close.ewm(span=fast_span, adjust=False).mean()
                    s_slow = s_close.ewm(span=slow_span, adjust=False).mean()
                    
                    if (float(s_fast.iloc[-1]) > float(s_slow.iloc[-1])) and (current_rsi < 70):
                        action = "🟢 BUY (EMA GOLDEN CROSS)"
                    else:
                        action = "🔴 SELL / NEUTRAL TREND"
                
                screener_results.append({
                    "Stock": s_ticker,
                    "Current Price": f"${current_price:.2f}" if not s_ticker.endswith(".L") else f"£{current_price/100:.2f}",
                    "RSI": round(current_rsi, 1),
                    "Action Status": action,
                    "Timestamp": str(s_data.index[-1].strftime('%H:%M:%S'))
                })
                
                # Tiny rest limit to avoid triggering anti-bot firewalls
                time.sleep(0.05)
                
            except Exception:
                # Silently skip failed downloads to keep the scan progressing
                continue
                
        status_text.success("Scan Completed!")
        
        # Display Results
        if screener_results:
            df_results = pd.DataFrame(screener_results)
            
            def style_status(val):
                if "🟢" in val:
                    return 'background-color: #d4edda; color: #155724; font-weight: bold;'
                elif "🔴" in val:
                    return 'background-color: #f8d7da; color: #721c24; font-weight: bold;'
                return 'background-color: #e2e3e5; color: #383d41;'
            
            styled_df = df_results.style.map(style_status, subset=['Action Status'])
            st.dataframe(styled_df, use_container_width=True, height=500)
            
        else:
            st.warning("Scan finished, but no data could be retrieved.")