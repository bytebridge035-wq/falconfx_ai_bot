#!/usr/bin/env python3
"""Parameter optimization for FalconFX backtester."""
import sys
sys.path.insert(0, 'scripts')
from backtest import FalconFXBacktester, load_kaggle_data

pairs = ['EURJPY', 'EURUSD', 'GBPUSD', 'USDJPY']

for pair in pairs:
    try:
        df = load_kaggle_data('data/TIMEFRAME_1H.csv', pair)
    except Exception as e:
        print(f"SKIP {pair}: {e}")
        continue
    
    print(f"\n=== {pair} Parameter Optimization (1H, {len(df)} bars) ===")
    print("SwingLB  Trades  WinRate     PF   PnL(R)")
    print("-" * 45)
    
    for sl in [5, 8, 10, 13, 15, 20]:
        bt = FalconFXBacktester(swing_lookback=sl, tp_ratio=3.0)
        r = bt.run(df)
        if r.get('total_trades', 0) > 0:
            print(f"  {sl:>4}   {r['total_trades']:>4}   {r['win_rate']:>5.1f}%  {r['profit_factor']:>5.2f}  {r['total_pnl_r']:>7.2f}")
        else:
            print(f"  {sl:>4}      0     N/A   0.00     0.00")
