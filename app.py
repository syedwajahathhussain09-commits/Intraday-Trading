import streamlit as st
import yfinance as yf
import pandas as pd
import numpy as np
import requests
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import google.generativeai as genai

# ==============================================================================
# --- 1. SECURE CONFIGURATION & CREDENTIAL CHECK (GRACEFUL FAIL) ---
# ==============================================================================
# Check for secrets but don't halt execution if they are missing
GEMINI_API_KEY = st.secrets.get("GEMINI_API_KEY", None)
TELEGRAM_BOT_TOKEN = st.secrets.get("TELEGRAM_BOT_TOKEN", None)
CHAT_ID = st.secrets.get("TELEGRAM_CHAT_ID", "YOUR_TELEGRAM_CHAT_ID")

ai_enabled = False
telegram_enabled = False

if GEMINI_API_KEY:
    try:
        genai.configure(api_key=GEMINI_API_KEY)
        ai_enabled = True
    except Exception:
        pass

if TELEGRAM_BOT_TOKEN:
    telegram_enabled = True

# ==============================================================================
# --- 2. CYBERPUNK TERMINAL UI STYLING ---
# ==============================================================================
st.set_page_config(page_title="QUANT-AI // PRO TERMINAL", layout="wide")

st.markdown("""
    <style>
    /* Dark Terminal Workspace Styling */
    .main { background-color: #0b0f19 !important; color: #c9d1d9; }
    h1, h2, h3 { color: #58a6ff !important; font-family: 'Courier New', monospace !important; font-weight: 700; }
    
    /* Elegant Sidebar with custom scrollbar */
    [data-testid="stSidebar"] {
        background-color: #070a12 !important;
        border-right: 1px solid #1f293d !important;
    }
    [data-testid="stSidebarUserContent"] {
        max-height: 95vh !important;
        overflow-y: auto !important;
        overflow-x: hidden !important;
    }
    [data-testid="stSidebarUserContent"]::-webkit-scrollbar { width: 5px; }
    [data-testid="stSidebarUserContent"]::-webkit-scrollbar-thumb { background: #1f293d; border-radius: 4px; }
    
    /* Metrics glassmorphism containers */
    div[data-testid="stMetric"] {
        background: linear-gradient(135deg, #0f172a, #070a12);
        border: 1px solid #1e293b;
        border-radius: 8px;
        padding: 15px !important;
        box-shadow: 0 4px 12px rgba(0, 0, 0, 0.5);
    }
    div[data-testid="stMetricValue"] {
        font-family: 'Courier New', monospace !important;
        color: #ffffff !important;
    }
    </style>
    """, unsafe_allow_html=True)

# ==============================================================================
# --- 3. HIGH-PERFORMANCE DATA ENGINE ---
# ==============================================================================
@st.cache_data(ttl=120)  # Dynamic caching (2 minutes) to prevent network lag
def fetch_financial_data(symbol):
    try:
        df = yf.download(symbol, period="1y", interval="1d", progress=False)
        if df.empty or len(df) < 50:
            return pd.DataFrame()
            
        # Flatten multi-index headers if present
        if isinstance(df.columns, pd.MultiIndex):
            df.columns = df.columns.droplevel(1)
        df.columns = [str(col).strip() for col in df.columns]
        
        # Base technical metrics
        df['EMA20'] = df['Close'].ewm(span=20, adjust=False).mean()
        df['EMA50'] = df['Close'].ewm(span=50, adjust=False).mean()
        
        # RSI Engine
        delta = df['Close'].diff()
        gain = delta.where(delta > 0, 0.0)
        loss = -delta.where(delta < 0, 0.0)
        avg_gain = gain.rolling(window=14).mean()
        avg_loss = loss.rolling(window=14).mean()
        rs = avg_gain / avg_loss
        df['RSI'] = 100 - (100 / (1 + rs))
        
        return df
    except Exception as e:
        st.error(f"Data Engine failure: {e}")
        return pd.DataFrame()

# ==============================================================================
# --- 4. BACKTESTING & QUANT SIMULATOR ---
# ==============================================================================
def run_crossover_backtest(df):
    """Simulates a 20/50 EMA Crossover strategy"""
    backtest_df = df.copy()
    backtest_df['Signal'] = 0.0
    backtest_df['Signal'] = np.where(backtest_df['EMA20'] > backtest_df['EMA50'], 1.0, 0.0)
    backtest_df['Position'] = backtest_df['Signal'].diff()
    
    # Calculate returns
    backtest_df['Market_Return'] = backtest_df['Close'].pct_change()
    backtest_df['Strategy_Return'] = backtest_df['Market_Return'] * backtest_df['Signal'].shift(1)
    
    # Calculate performance metrics
    cum_market = (1 + backtest_df['Market_Return'].fillna(0)).prod() - 1
    cum_strategy = (1 + backtest_df['Strategy_Return'].fillna(0)).prod() - 1
    
    std_dev = backtest_df['Strategy_Return'].std()
    sharpe = (backtest_df['Strategy_Return'].mean() / std_dev) * np.sqrt(252) if std_dev > 0 else 0.0
    
    trades = backtest_df[backtest_df['Position'] != 0].copy()
    trades['Trade_Return'] = trades['Close'].pct_change()
    win_rate = (trades['Trade_Return'] > 0).mean() * 100 if len(trades) > 0 else 0.0
    
    return {
        "Strategy_Return": round(cum_strategy * 100, 2),
        "Market_Return": round(cum_market * 100, 2),
        "Sharpe_Ratio": round(sharpe, 2),
        "Win_Rate": round(win_rate, 1)
    }

# ==============================================================================
# --- 5. TELEGRAM INTEGRATION ENGINE ---
# ==============================================================================
def dispatch_telegram_alert(symbol, price, action):
    if not telegram_enabled:
        return
    message = f"🔔 **QUANT-AI SYSTEM ALERT**\n\nAsset: `{symbol}`\nExecuted Price: `${price:.2f}`\nAction Profile: **{action}**"
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    payload = {"chat_id": CHAT_ID, "text": message, "parse_mode": "Markdown"}
    try:
        requests.post(url, json=payload)
    except Exception as e:
        st.sidebar.warning(f"Failed to transmit alert profile: {e}")

# ==============================================================================
# --- 6. CORE INTERFACE ARCHITECTURE ---
# ==============================================================================
st.title("📟 QUANT-AI // MODEL INFERENCE TERMINAL")
st.write("Advanced algorithmic analysis engine utilizing machine learning logic arrays.")

st.sidebar.header("🎛️ Terminal Inputs")
symbol = st.sidebar.text_input("Underlying Asset Symbol:", value="AAPL").upper().strip()

df = fetch_financial_data(symbol)

if df.empty:
    st.error("Engine failed to parse historical data structures for the requested asset.")
else:
    current_price = float(df['Close'].iloc[-1])
    current_rsi = float(df['RSI'].iloc[-1])
    current_ema20 = float(df['EMA20'].iloc[-1])
    current_ema50 = float(df['EMA50'].iloc[-1])
    price_change = float(df['Close'].pct_change().iloc[-1] * 100)
    
    if current_price > current_ema20 and current_rsi < 70:
        action_signal = "BUY / ACCUMULATE"
        signal_color = "#00ff66"
    elif current_price < current_ema20 or current_rsi > 70:
        action_signal = "LIQUIDATE / SELL"
        signal_color = "#ff3366"
    else:
        action_signal = "HOLD / NEUTRAL"
        signal_color = "#e2e8f0"

    # Row 1: Real-Time Metric Indicators
    m1, m2, m3, m4 = st.columns(4)
    m1.metric("Asset Spot Price", f"${current_price:.2f}", f"{price_change:+.2f}%")
    m2.metric("RSI (14-Period)", f"{current_rsi:.1f}", "Overbought > 70" if current_rsi > 70 else "Oversold < 30" if current_rsi < 30 else "Neutral")
    m3.metric("EMA (20 vs 50)", f"${current_ema20:.2f}", f"Spread: ${(current_ema20 - current_ema50):.2f}")
    
    with m4:
        st.markdown(f"""
            <div style="background: linear-gradient(135deg, #0f172a, #070a12); border: 1px solid #1e293b; border-radius: 8px; padding: 15px; text-align: center; box-shadow: 0 4px 12px rgba(0,0,0,0.5);">
                <div style="color: #8b949e; font-size: 14px; font-weight: 600; font-family: 'Courier New', monospace;">ALGO DIRECTIONAL SIGNAL</div>
                <div style="color: {signal_color}; font-size: 18px; font-weight: bold; margin-top: 8px; font-family: 'Courier New', monospace;">{action_signal}</div>
            </div>
            """, unsafe_allow_html=True)

   # Row 1: Real-Time Metric Indicators
    m1, m2, m3, m4 = st.columns(4)
    m1.metric("Asset Spot Price", f"${current_price:.2f}", f"{price_change:+.2f}%")
    m2.metric("RSI (14-Period)", f"{current_rsi:.1f}", "Overbought > 70" if current_rsi > 70 else "Oversold < 30" if current_rsi < 30 else "Neutral")
    m3.metric("EMA (20 vs 50)", f"${current_ema20:.2f}", f"Spread: ${(current_ema20 - current_ema50):.2f}")
    
    with m4:
        st.markdown(f"""
            <div style="background: linear-gradient(135deg, #0f172a, #070a12); border: 1px solid #1e293b; border-radius: 8px; padding: 15px; text-align: center; box-shadow: 0 4px 12px rgba(0,0,0,0.5);">
                <div style="color: #8b949e; font-size: 14px; font-weight: 600; font-family: 'Courier New', monospace;">ALGO DIRECTIONAL SIGNAL</div>
                <div style="color: {signal_color}; font-size: 18px; font-weight: bold; margin-top: 8px; font-family: 'Courier New', monospace;">{action_signal}</div>
            </div>
            """, unsafe_allow_html=True)

    # ==============================================================================
    # 📈 PASTED TRADINGVIEW GRAPH GRID (WITH TIMEFRAME TOOLBAR)
    # ==============================================================================
    st.subheader("📈 High-Fidelity Real-Time Signal Mapping Grid")
    
    tradingview_widget_html = f"""
    <div class="tradingview-widget-container" style="height:100%;width:100%;">
      <div id="tradingview_quant_chart" style="height:550px;width:100%;"></div>
      <script type="text/javascript" src="https://s3.tradingview.com/tv.js"></script>
      <script type="text/javascript">
      new TradingView.widget({{
        "width": "100%",
        "height": 550,
        "symbol": "NASDAQ:{symbol}",
        "interval": "D",
        "timezone": "Etc/UTC",
        "theme": "dark",
        "style": "1",
        "locale": "en",
        "toolbar_bg": "#070a12",
        "enable_publishing": false,
        "hide_top_toolbar": false,          
        "hide_side_toolbar": false,         
        "allow_symbol_change": true,        
        "save_image": true,
        "container_id": "tradingview_quant_chart",
        "studies": [
          "EMA@tv-basicstudies",
          "RSI@tv-basicstudies"
        ],
        "time_frames": [                    
          {{ "text": "1d", "resolution": "5" }},
          {{ "text": "5d", "resolution": "30" }},
          {{ "text": "1m", "resolution": "60" }},
          {{ "text": "3m", "resolution": "D" }},
          {{ "text": "1y", "resolution": "W" }}
        ]
      }});
      </script>
    </div>
    """
        
    # Inject the HTML component securely into the main Streamlit canvas
    import streamlit.components.v1 as components
    components.html(tradingview_widget_html, height=560, scrolling=False)

    # Operations Tabs
    tab1, tab2 = st.tabs(["⚙️ Algorithmic Strategy Backtest", "🧠 Advanced AI Narrative Broker"])

    with tab1:
        st.subheader("EMA Crossover Backtest Matrix")
        results = run_crossover_backtest(df)
        
        sc1, sc2, sc3, sc4 = st.columns(4)
        sc1.metric("Strategy Cumulative Return", f"{results['Strategy_Return']}%")
        sc2.metric("Buy & Hold Baseline Return", f"{results['Market_Return']}%")
        sc3.metric("Sharpe Ratio", f"{results['Sharpe_Ratio']}")
        sc4.metric("Strategy Win Rate", f"{results['Win_Rate']}%")

    with tab2:
        st.subheader("Gemini Institutional Investment Memorandum")
        
        if ai_enabled:
            if st.button("Generate Deep Machine-Learning Analysis"):
                with st.spinner("Compiling structural telemetry matrices..."):
                    analysis_prompt = f"""
                    You are an elite quantitative trading model and financial analyst.
                    Analyze the following technical telemetry profile for the asset symbol: {symbol}
                    
                    - Spot Price: ${current_price:.2f} (Daily Change: {price_change:+.2f}%)
                    - Relative Strength Index (RSI-14): {current_rsi:.1f}
                    - Exponential Moving Average (20-EMA): ${current_ema20:.2f}
                    - Exponential Moving Average (50-EMA): ${current_ema50:.2f}
                    - Algorithmic Trading Signal Status: {action_signal}
                    
                    Generate a highly technical market report including a brief trend state analysis, scenario projections, and core risk factors. Maintain a sharp, quantitative tone without generic greetings.
                    """
                    try:
                        model = genai.GenerativeModel("gemini-1.5-flash")
                        response = model.generate_content(analysis_prompt)
                        st.markdown(response.text)
                    except Exception as e:
                        st.error(f"AI Matrix generation failed: {e}")
        else:
            st.info("🔒 **AI Features Locked**")
            st.write("To unlock custom AI-driven market analysis memos, configure your `GEMINI_API_KEY` inside your Streamlit Cloud secrets settings whenever you are ready.")

    # Sidebar alert layout
    st.sidebar.markdown("---")
    st.sidebar.header("🔔 Automated Dispatches")
    
    if telegram_enabled:
        if st.sidebar.button("Send Alert Telegram Broadcast"):
            dispatch_telegram_alert(symbol, current_price, action_signal)
            st.sidebar.success("Signal dispatched to active mobile terminal!")
    else:
        st.sidebar.info("🔒 **Telegram Alerts Locked**")
        st.sidebar.caption("Configure your `TELEGRAM_BOT_TOKEN` inside Streamlit Cloud secrets to push automatic trading signals straight to your mobile devices later.")