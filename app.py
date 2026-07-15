import pandas as pd
import yfinance as yf
import matplotlib.pyplot as plt

# 1. Download Intraday Data (5-minute intervals for the last 5 days)
ticker = "AAPL"
data = yf.download(ticker, period="5d", interval="5m")

# Clean up multi-level column index if present in newer yfinance versions
if isinstance(data.columns, pd.MultiIndex):
    data.columns = data.columns.get_level_values(0)

# 2. Calculate Indicators
# Moving Averages
data['EMA_Fast'] = data['Close'].ewm(span=9, adjust=False).mean()
data['EMA_Slow'] = data['Close'].ewm(span=21, adjust=False).mean()

# Relative Strength Index (RSI - 14 period)
delta = data['Close'].diff()
gain = (delta.where(delta > 0, 0)).rolling(window=14).mean()
loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
rs = gain / loss
data['RSI'] = 100 - (100 / (1 + rs))

# 3. Generate Trading Signals
# Buy when Fast EMA > Slow EMA AND RSI is not overbought (< 70)
data['Signal'] = 0
data.loc[(data['EMA_Fast'] > data['EMA_Slow']) & (data['RSI'] < 70), 'Signal'] = 1
# Sell/Short when Fast EMA < Slow EMA OR RSI is overbought (> 70)
data.loc[(data['EMA_Fast'] < data['EMA_Slow']) | (data['RSI'] > 70), 'Signal'] = -1

# Find the exact moments the signal changes
data['Position'] = data['Signal'].diff()

# 4. Plotting the Results (Last 100 rows for clarity)
plot_data = data.tail(100)

plt.figure(figsize=(14, 7))
plt.plot(plot_data['Close'], label='Close Price', color='black', alpha=0.6)
plt.plot(plot_data['EMA_Fast'], label='9 EMA (Fast)', color='blue', linestyle='--')
plt.plot(plot_data['EMA_Slow'], label='21 EMA (Slow)', color='orange', linestyle='--')

# Plot Buy Signals
plt.scatter(plot_data[plot_data['Position'] == 2].index, 
            plot_data['Close'][plot_data['Position'] == 2], 
            label='BUY Signal', marker='^', color='green', s=100)

# Plot Sell Signals
plt.scatter(plot_data[plot_data['Position'] == -2].index, 
            plot_data['Close'][plot_data['Position'] == -2], 
            label='SELL Signal', marker='v', color='red', s=100)

plt.title(f"{ticker} Intraday Trading Signals (5-Min Chart)")
plt.xlabel("Date/Time")
plt.ylabel("Price ($)")
plt.legend()
plt.grid()
plt.show()