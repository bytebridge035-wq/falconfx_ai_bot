#!/usr/bin/env python3
"""Quick 4H test on best pairs."""
import sys
sys.path.insert(0, 'scripts')
from backtest import FalconFXBacktester, load_kaggle_data

# Test 4H timeframe
import pandas as pd

df_4h = pd.read_csv('data/TIMEFRAME_15M.csv')  # Use 15M as proxy, or we can resample 1H

# Actually let's resample 1H to get more bars for existing results
df_1h = pd.read_csv('data/TIMEFRAME_1H.csv')
df_1h['time'] = pd.to_datetime(df_1h['time'])
df_1h = df_1h.set_index('time')

# Resample to 4H
df_4h = df_1h.groupby('EURJPY').resample('4h').agg({
    'EURJPY': 'first',
    'H-EURJPY': 'max', 
    'L-EURJPY': 'min',
    'V-EURJPY': 'sum'
}).dropna()

# Reconstruct OHLC
df_4h['open'] = df_4h['EURJPY']
df_4h['high'] = df_4h['H-EURJPY']
df_4h['low'] = df_4h['L-EURJPY']
df_4h['close'] = df_4h['EURJPY'].shift(-1)
df_4h.loc[df_4h.index[-1], 'close'] = df_4h['EURJPY'].iloc[-1]
df_4h = df_4h.drop(columns=['EURJPY', 'H-EURJPY', 'L-EURJPY', 'V-EURJPY'])
df_4h = df_4h.reset_index()
df_4h['time'] = df_4h['timestamp'] if 'timestamp' in df_4h.columns else df_4h.iloc[:, 0]
# Ensure time is datetime
if 'time' in df_4h.columns:
    df_4h['time'] = pd.to_datetime(df_4h['time'])

print(f"4H resampled: {len(df_4h)} bars")
print(f"Columns: {list(df_4h.columns)}")

# Run backtest
for sl in [5, 8, 10, 13, 15]:
    bt = FalconFXBacktester(swing_lookback=sl, tp_ratio=3.0)
    r = bt.run(df_4h)
    if r.get('total_trades', 0) > 0:
        print(f"  swing={sl:>3}: trades={r['total_trades']:>3}, WR={r['win_rate']:>5.1f}%, PF={r['profit_factor']:>5.2f}, PnL={r['total_pnl_r']:>7.2f}R")
    else:
        print(f"  swing={sl:>3}: 0 trades")
