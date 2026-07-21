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

# =========================================================================
# SHARED HELPER FUNCTIONS
# (previously duplicated ~3x across Tab 2 / single-scan / batch-scan)
# =========================================================================

def format_vol(v):
    """Human readable volume string, e.g. 1.23M / 4.5K."""
    try:
        v = float(v)
    except (TypeError, ValueError):
        return "N/A"
    if v >= 1_000_000_000:
        return f"{v / 1_000_000_000:.2f}B"
    elif v >= 1_000_000:
        return f"{v / 1_000_000:.2f}M"
    elif v >= 1_000:
        return f"{v / 1_000:.1f}K"
    return str(int(v))


def format_price(ticker_symbol, price):
    """LSE tickers are quoted in pence by yfinance; show as GBP."""
    if ticker_symbol.endswith(".L"):
        return f"£{price / 100:.2f}"
    return f"${price:.2f}"


def compute_indicators(df, rsi_period, fast_span, slow_span):
    """Adds RSI, EMA_Fast, EMA_Slow, VWAP, Vol_SMA columns to a raw OHLCV dataframe."""
    df = df.copy()
    close = df['Close'].squeeze()
    high = df['High'].squeeze()
    low = df['Low'].squeeze()
    volume = df['Volume'].squeeze()

    delta = close.diff()
    gain = (delta.where(delta > 0, 0)).rolling(window=rsi_period).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(window=rsi_period).mean()
    rs = gain / loss
    rsi = 100 - (100 / (1 + rs))
    # Fix: when both gain and loss are 0 (flat / no-trade bars), rs is 0/0 = NaN.
    # Treat that as a neutral RSI of 50 instead of letting NaN silently break signal logic.
    flat_mask = (gain == 0) & (loss == 0)
    rsi = rsi.where(~flat_mask, 50)
    df['RSI'] = rsi

    df['Vol_SMA'] = volume.rolling(window=10).mean()
    df['EMA_Fast'] = close.ewm(span=fast_span, adjust=False).mean()
    df['EMA_Slow'] = close.ewm(span=slow_span, adjust=False).mean()

    typical_price = (high + low + close) / 3
    tp_vol = typical_price * volume
    dates = df.index.date
    cum_tp_vol = tp_vol.groupby(dates).cumsum()
    cum_vol = volume.groupby(dates).cumsum()
    df['VWAP'] = cum_tp_vol / cum_vol

    return df


def compute_signal(df, strategy_type, params):
    """Adds a 'Signal' column (1 = buy, -1 = sell, 0 = neutral) based on chosen strategy.
    Requires compute_indicators() to have been run first."""
    df = df.copy()
    close = df['Close'].squeeze()
    volume = df['Volume'].squeeze()
    df['Signal'] = 0

    if strategy_type == "All-in-One Confluence":
        df.loc[
            (df['EMA_Fast'] > df['EMA_Slow']) &
            (close > df['VWAP']) &
            (df['RSI'] >= 40) & (df['RSI'] <= 65) &
            (volume > (df['Vol_SMA'] * 0.8)),
            'Signal'
        ] = 1
        df.loc[
            (df['EMA_Fast'] < df['EMA_Slow']) |
            (close < df['VWAP']) |
            (df['RSI'] > 70),
            'Signal'
        ] = -1

    elif strategy_type == "RSI Range Spotter":
        df.loc[
            (df['RSI'] >= params['rsi_min']) &
            (df['RSI'] <= params['rsi_max']) &
            (volume > (df['Vol_SMA'] * 0.8)),
            'Signal'
        ] = 1
        df.loc[(df['RSI'] > 65), 'Signal'] = -1

    elif strategy_type == "VWAP Pullback":
        df.loc[
            (close > df['VWAP']) &
            (close.shift(1) <= df['VWAP']) &
            (df['RSI'] < params['rsi_oversold']) &
            (volume > df['Vol_SMA'] * 0.9),
            'Signal'
        ] = 1
        df.loc[(close < df['VWAP']), 'Signal'] = -1

    else:  # EMA Crossover
        df.loc[
            (df['EMA_Fast'] > df['EMA_Slow']) &
            (df['RSI'] < 70) &
            (volume > (df['Vol_SMA'] * 0.9)),
            'Signal'
        ] = 1
        df.loc[(df['EMA_Fast'] < df['EMA_Slow']) | (df['RSI'] > 70), 'Signal'] = -1

    return df


def detect_patterns(df):
    """Adds vectorized 'Pattern' / 'Pattern_Signal' columns for every bar.
    Requires 'RSI' to already be present (from compute_indicators)."""
    df = df.copy()
    close = df['Close'].squeeze()
    open_ = df['Open'].squeeze()
    high = df['High'].squeeze()
    low = df['Low'].squeeze()
    rsi = df['RSI']

    body = (close - open_).abs()
    candle_range = (high - low).replace(0, 0.00001)
    upper_shadow = high - df[['Close', 'Open']].max(axis=1).squeeze()
    lower_shadow = df[['Close', 'Open']].min(axis=1).squeeze() - low

    df['Pattern'] = "⚪ No Pattern"
    df['Pattern_Signal'] = 0

    is_hammer = (lower_shadow > (2 * body)) & (upper_shadow < (0.1 * candle_range)) & (rsi < 40)
    df.loc[is_hammer, 'Pattern'] = "🟢 BULLISH HAMMER"
    df.loc[is_hammer, 'Pattern_Signal'] = 1

    is_star = (upper_shadow > (2 * body)) & (lower_shadow < (0.1 * candle_range)) & (rsi > 60)
    df.loc[is_star, 'Pattern'] = "🔴 BEARISH SHOOTING STAR"
    df.loc[is_star, 'Pattern_Signal'] = -1

    prev_close = close.shift(1)
    prev_open = open_.shift(1)
    is_bull_eng = (prev_close < prev_open) & (close > open_) & (open_ <= prev_close) & (close >= prev_open)
    is_bear_eng = (prev_close > prev_open) & (close < open_) & (open_ >= prev_close) & (close <= prev_open)
    df.loc[is_bull_eng, 'Pattern'] = "🟢 BULLISH ENGULFING"
    df.loc[is_bull_eng, 'Pattern_Signal'] = 1
    df.loc[is_bear_eng, 'Pattern'] = "🔴 BEARISH ENGULFING"
    df.loc[is_bear_eng, 'Pattern_Signal'] = -1

    return df


def build_scan_row(symbol, df, strategy_type, rsi_period, fast_span, slow_span, params):
    """Runs the full indicator -> signal -> pattern pipeline on one symbol's
    OHLCV dataframe and returns a single summary dict for the screener table.
    Returns None (with a reason) if the data is unusable."""
    if df is None or df.empty or len(df) < 2:
        return None, "insufficient data"

    try:
        df = compute_indicators(df, rsi_period, fast_span, slow_span)
        df = compute_signal(df, strategy_type, params)
        df = detect_patterns(df)

        current_price = float(df['Close'].iloc[-1])
        current_rsi = float(df['RSI'].iloc[-1])
        current_vol = float(df['Volume'].iloc[-1])
        current_vol_sma = float(df['Vol_SMA'].iloc[-1]) if not pd.isna(df['Vol_SMA'].iloc[-1]) else 0.0

        vol_ratio = current_vol / current_vol_sma if current_vol_sma > 0 else 1.0
        if vol_ratio >= 2.0:
            vol_alert = f"⚡ SURGE ({vol_ratio:.1f}x)"
        elif vol_ratio >= 1.5:
            vol_alert = f"🔥 HIGH ({vol_ratio:.1f}x)"
        else:
            vol_alert = "⚪ NORMAL"

        last_signal = int(df['Signal'].iloc[-1])
        action = "🟢 STRATEGY BUY" if last_signal == 1 else ("🔴 STRATEGY SELL" if last_signal == -1 else "⚪ HOLD / NEUTRAL")

        return {
            "Stock": symbol,
            "Current Price": format_price(symbol, current_price),
            "Volume": format_vol(current_vol),
            "Volume Alert": vol_alert,
            "RSI": round(current_rsi, 1),
            "Candle Pattern": df['Pattern'].iloc[-1],
            "Strategy Signal": action,
            "Timestamp": str(df.index[-1].strftime('%H:%M:%S'))
        }, None
    except Exception as e:
        return None, str(e)


def scan_tickers(tickers, tf_settings, strategy_type, rsi_period, fast_span, slow_span, params,
                  batch_size=10, progress_placeholder=None, progress_bar=None):
    """Batched, threaded download + analysis for a list of tickers.
    Used by both the single-symbol quick scan and the full index scan.
    Returns (results_list, failed_list) so failures are visible instead of silently dropped."""
    results = []
    failed = []

    batches = [tickers[i:i + batch_size] for i in range(0, len(tickers), batch_size)]
    total_batches = len(batches)
    total_tickers = len(tickers)
    processed = 0

    for batch_idx, batch in enumerate(batches):
        if progress_placeholder is not None:
            progress_placeholder.text(f"Downloading batch {batch_idx + 1} of {total_batches} ({len(batch)} symbols)...")

        try:
            bulk_data = yf.download(
                tickers=batch,
                period="5d",
                interval=tf_settings['yf_interval'],
                threads=True,   # fix: was False, made large scans extremely slow
                progress=False,
                timeout=15
            )
        except Exception as e:
            failed.extend([(t, f"batch download error: {e}") for t in batch])
            processed += len(batch)
            if progress_bar is not None:
                progress_bar.progress(min(1.0, processed / total_tickers))
            continue

        if bulk_data.empty:
            failed.extend([(t, "no data returned") for t in batch])
            processed += len(batch)
            if progress_bar is not None:
                progress_bar.progress(min(1.0, processed / total_tickers))
            continue

        for sym in batch:
            processed += 1
            if progress_bar is not None:
                progress_bar.progress(min(1.0, processed / total_tickers))
            try:
                if len(batch) > 1:
                    s_data = bulk_data.xs(sym, axis=1, level=1).dropna()
                else:
                    s_data = bulk_data.dropna()
            except Exception as e:
                failed.append((sym, f"column extraction error: {e}"))
                continue

            row, reason = build_scan_row(sym, s_data, strategy_type, rsi_period, fast_span, slow_span, params)
            if row is not None:
                results.append(row)
            else:
                failed.append((sym, reason))

        time.sleep(0.2)

    return results, failed


# Helper function to scrape live Index Tickers dynamically with robust fallback parsing
@st.cache_data(ttl=86400)  # Cache lists for 24 hours
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
            return ["AAPL", "MSFT", "AMZN", "NVDA", "TSLA", "META", "GOOGL", "GOOG", "NFLX", "AMD", "INTC", "PYPL", "ADBE", "COST", "PEP", "AVGO", "CSCO", "TMUS", "CMCSA", "AMGN"]

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

        else:  # Custom Volatile Watchlist
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

# Stock Directory
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

st.sidebar.subheader("Strategy Settings")
rsi_period = st.sidebar.slider("RSI Period", min_value=5, max_value=30, value=14)

fast_span = 9
slow_span = 21
# Defaults for params not relevant to every strategy (compute_signal only reads
# the keys used by the branch that matches strategy_type).
strat_params = {"rsi_min": 30, "rsi_max": 35, "rsi_oversold": 60}

if strategy_type == "All-in-One Confluence":
    st.sidebar.markdown("**Confluence Strategy Controls**")
    fast_span = st.sidebar.slider("Fast EMA", min_value=3, max_value=20, value=9)
    slow_span = st.sidebar.slider("Slow EMA", min_value=10, max_value=50, value=21)
    st.sidebar.info("Uses Price > VWAP, EMA Crossover, and RSI (40-65) for signal confirmation.")

elif strategy_type == "RSI Range Spotter":
    st.sidebar.markdown("**RSI Target Zone (Buy)**")
    strat_params["rsi_min"] = st.sidebar.slider("RSI Min Floor", min_value=10, max_value=50, value=30)
    strat_params["rsi_max"] = st.sidebar.slider("RSI Max Ceiling", min_value=15, max_value=60, value=35)

elif strategy_type == "VWAP Pullback":
    strat_params["rsi_oversold"] = st.sidebar.slider("RSI Entry Threshold (Max)", min_value=30, max_value=70, value=60)

elif strategy_type == "EMA Crossover":
    fast_span = st.sidebar.slider("Fast EMA", min_value=3, max_value=20, value=9)
    slow_span = st.sidebar.slider("Slow EMA", min_value=10, max_value=50, value=21)

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

# --- TAB 2: Custom Strategy Backtest Signals ---
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
        close_series = data['Close'].squeeze()
        volume_series = data['Volume'].squeeze()

        # Shared pipeline: indicators -> signal -> patterns
        data = compute_indicators(data, rsi_period, fast_span, slow_span)
        data = compute_signal(data, strategy_type, strat_params)
        data = detect_patterns(data)

        # Fix: track any transition INTO a nonzero signal state, not just a
        # jump straight from -1 to 1 (diff == ±2). The original version used
        # data['Signal'].diff() and only kept rows where diff was exactly 2 or
        # -2, which silently dropped the far more common 0->1 / 1->0 / 0->-1
        # transitions from the "Recent Signal Execution Logs" table below.
        data['Prev_Signal'] = data['Signal'].shift(1).fillna(0)
        entered_long = (data['Signal'] == 1) & (data['Prev_Signal'] != 1)
        entered_short = (data['Signal'] == -1) & (data['Prev_Signal'] != -1)

        # CANDLESTICK PATTERN DETECTOR
        st.markdown("---")
        st.markdown("### 🕯️ Automatic Candlestick Pattern Recognition")

        latest_candle = data.iloc[-1]
        latest_pattern = latest_candle['Pattern']

        if "🟢" in latest_pattern:
            st.success(f"**Current Candle Pattern:** {latest_pattern} detected on the {selected_tf} timeframe! Look for Potential Long Entry.")
        elif "🔴" in latest_pattern:
            st.error(f"**Current Candle Pattern:** {latest_pattern} detected on the {selected_tf} timeframe! Look for Potential Short/Exit.")
        else:
            st.info(f"**Current Candle Pattern:** No clear reversal candlestick pattern formed on the current {selected_tf} bar.")

        # LIVE SIGNAL ADVISOR MODULE
        st.markdown("---")
        st.markdown("### 🚨 Live Signal Advisor & Market Session Status")

        try:
            live_ticker = yf.Ticker(ticker)
            fast = live_ticker.fast_info
            info = live_ticker.info

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
            pct_change = (price_change / prev_close) * 100 if prev_close else 0.0
        except Exception:
            last_price = float(close_series.iloc[-1])
            price_change = 0.0
            pct_change = 0.0

        chg_color = "🟢" if price_change >= 0 else "🔴"
        st.info(f"**Live Extended Market Price:** `${last_price:.2f}` ({chg_color} `{price_change:+.2f}` / `{pct_change:+.2f}%`) | **Last Bar Timestamp:** `{data.index[-1].strftime('%Y-%m-%d %H:%M EST')}`")

        high_low = data['High'].squeeze() - data['Low'].squeeze()
        high_close = (data['High'].squeeze() - close_series.shift()).abs()
        low_close = (data['Low'].squeeze() - close_series.shift()).abs()
        ranges = pd.concat([high_low, high_close, low_close], axis=1)
        atr_value = float(ranges.max(axis=1).rolling(window=14).mean().iloc[-1])

        last_signal = int(data['Signal'].iloc[-1])
        last_rsi = float(data['RSI'].iloc[-1])

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
            total_session_vol = float(today_data['Volume'].sum())
            last_bar_vol = float(today_data['Volume'].iloc[-1])
        except Exception:
            total_session_vol = float(volume_series.iloc[-1])
            last_bar_vol = float(volume_series.iloc[-1])

        formatted_total_vol = format_vol(total_session_vol)
        formatted_bar_vol = format_vol(last_bar_vol)

        last_vol = float(volume_series.iloc[-1])
        vol_avg = float(data['Vol_SMA'].iloc[-1]) if not pd.isna(data['Vol_SMA'].iloc[-1]) else 0.0
        vol_ratio = last_vol / vol_avg if vol_avg > 0 else 1.0

        last_bar_time = data.index[-1]
        is_extended_hours = (last_bar_time.hour < 9 or (last_bar_time.hour == 9 and last_bar_time.minute < 30)) or (last_bar_time.hour >= 16)

        if is_extended_hours and vol_ratio >= 2.0:
            st.warning(f"⚡ **EXTENDED HOURS VOLUME SURGE DETECTED!** Latest volume is **{vol_ratio:.1f}x** higher than average ({formatted_bar_vol} vs avg {format_vol(vol_avg)}).")
        elif vol_ratio >= 2.5:
            st.info(f"🔥 **HIGH VOLUME SPIKE:** Trading volume is **{vol_ratio:.1f}x** above the 10-period moving average.")

        col_m1, col_m2, col_m3, col_m4 = st.columns(4)
        col_m1.metric("Live Price", f"${last_price:.2f}", f"{price_change:+.2f} ({pct_change:+.2f}%)")
        col_m2.metric("Current RSI", f"{float(data['RSI'].iloc[-1]):.1f}")
        col_m3.metric("Session Volume", formatted_total_vol, delta=f"Last Bar: {formatted_bar_vol}")
        col_m4.metric("Strategy Signal", "BUY" if last_signal == 1 else ("SELL" if last_signal == -1 else "NEUTRAL"))

        # PLOTTING
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

        # RECENT TRADES HISTORY LOG (fixed to catch all entries, not just ±2 jumps)
        st.markdown("### 📜 Recent Signal Execution Logs")
        history = data[entered_long | entered_short].copy()

        if not history.empty:
            history['Action'] = np.where(history['Signal'] == 1, "🟢 BUY / LONG", "🔴 SELL / EXIT")
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

    if "scan_results" not in st.session_state:
        st.session_state.scan_results = None
    if "scan_failed" not in st.session_state:
        st.session_state.scan_failed = []

    # OPTION 1: QUICK SINGLE CUSTOM STOCK SCANNER
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
            results, failed = scan_tickers(
                [single_search_symbol], tf_settings, strategy_type,
                rsi_period, fast_span, slow_span, strat_params
            )
            if results:
                st.session_state.scan_results = results
                st.session_state.scan_failed = failed
                st.success(f"Single stock analysis completed for {single_search_symbol}!")
            else:
                reason = failed[0][1] if failed else "unknown error"
                st.error(f"Could not retrieve/analyze data for '{single_search_symbol}': {reason}")

    # OPTION 2: FULL MARKET INDEX SCREENER
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
        value=num_tickers
    )

    if st.button("🚀 Run Live Index Scan"):
        if scan_limit == 0:
            st.warning("Scan limit is set to 0. Please increase the limit to scan stocks.")
        elif num_tickers == 0:
            st.error("No tickers available to scan for this index right now.")
        else:
            progress_placeholder = st.empty()
            progress_bar = st.progress(0)

            active_scan_list = list(watchlist_tickers)[:scan_limit]

            screener_results, failed_tickers = scan_tickers(
                active_scan_list, tf_settings, strategy_type,
                rsi_period, fast_span, slow_span, strat_params,
                batch_size=10, progress_placeholder=progress_placeholder, progress_bar=progress_bar
            )

            progress_placeholder.success(
                f"Successfully scanned {len(screener_results)} of {len(active_scan_list)} stocks"
                + (f" ({len(failed_tickers)} failed)." if failed_tickers else ".")
            )
            st.session_state.scan_results = screener_results
            st.session_state.scan_failed = failed_tickers

    # Fix: failures used to be swallowed with bare `except: continue`.
    # Surface them so the user knows a scan wasn't silently incomplete.
    if st.session_state.scan_failed:
        with st.expander(f"⚠️ {len(st.session_state.scan_failed)} symbol(s) failed to scan — click to view"):
            failed_df = pd.DataFrame(st.session_state.scan_failed, columns=["Symbol", "Reason"])
            st.dataframe(failed_df, use_container_width=True)

    # RENDER DATA TABLE
    if st.session_state.scan_results is not None and len(st.session_state.scan_results) > 0:
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
    elif st.session_state.scan_results is not None:
        st.info("The scan completed but returned no usable rows. Check the failed-symbols panel above.")