#!/usr/bin/env python3
"""
FalconFX Optimized Backtester — Fast 2-Year Multi-Pair
Reduced parameter grid, early exit on bad combos
"""

import os
import sys
import csv
from datetime import datetime
from collections import defaultdict

PAIRS_DIR = os.path.expanduser("~/falconfx-bot/data")

def load_csv(filepath):
    """Load OHLCV CSV — fast path"""
    bars = []
    with open(filepath, 'r') as f:
        reader = csv.DictReader(f)
        for row in reader:
            try:
                ts_str = row.get('Index', row.get('Datetime', row.get('Date', '')))
                if not ts_str:
                    continue
                # Fast parse: just use string as timestamp key
                o = float(row['Open'])
                h = float(row['High'])
                l = float(row['Low'])
                c = float(row['Close'])
                if o <= 0 or h <= 0 or l <= 0 or c <= 0:
                    continue
                bars.append({
                    'ts': ts_str[:19],
                    'open': o,
                    'high': h,
                    'low': l,
                    'close': c,
                })
            except (ValueError, KeyError):
                continue
    return bars


def calc_atr_fast(bars, period=14):
    """Fast ATR calculation"""
    if len(bars) < period + 1:
        return 0
    trs = []
    for i in range(1, len(bars)):
        tr = max(
            bars[i]['high'] - bars[i]['low'],
            abs(bars[i]['high'] - bars[i-1]['close']),
            abs(bars[i]['low'] - bars[i-1]['close'])
        )
        trs.append(tr)
    if len(trs) < period:
        return sum(trs) / len(trs) if trs else 0
    atr = sum(trs[:period]) / period
    for i in range(period, len(trs)):
        atr = (atr * (period - 1) + trs[i]) / period
    return atr


def find_swings_fast(bars, lookback):
    """Find swing points — optimized"""
    swing_highs = []
    swing_lows = []
    n = len(bars)
    
    for i in range(lookback, n - lookback):
        h = bars[i]['high']
        l = bars[i]['low']
        is_high = True
        is_low = True
        
        for j in range(1, lookback + 1):
            if h <= bars[i-j]['high'] or h <= bars[i+j]['high']:
                is_high = False
            if l >= bars[i-j]['low'] or l >= bars[i+j]['low']:
                is_low = False
            if not is_high and not is_low:
                break
        
        if is_high:
            swing_highs.append((i, h))
        if is_low:
            swing_lows.append((i, l))
    
    return swing_highs, swing_lows


def backtest_fast(bars, params):
    """Fast FalconFX backtest"""
    swing_lookback = params['swing_lookback']
    sl_buffer_atr = params['sl_buffer_atr']
    tp_ratio = params['tp_ratio']
    be_trigger_r = params['be_trigger']
    
    swing_highs, swing_lows = find_swings_fast(bars, swing_lookback)
    
    if len(swing_highs) < 3 or len(swing_lows) < 3:
        return None
    
    trades = []
    position = None
    account = 10000.0
    initial_account = 10000.0
    last_exit_bar = -50  # Cooldown: min 10 bars between trades
    
    # Pre-build swing lookup for fast access
    swing_high_bars = {idx: price for idx, price in swing_highs}
    swing_low_bars = {idx: price for idx, price in swing_lows}
    swing_high_idxs = sorted(swing_high_bars.keys())
    swing_low_idxs = sorted(swing_low_bars.keys())
    
    for i in range(swing_lookback * 4, len(bars)):
        bar = bars[i]
        
        # Exit logic
        if position is not None:
            ep = position['entry']
            sl = position['sl']
            tp = position['tp']
            d = position['dir']
            amt = position['amount']
            be_done = position['be']
            entry_bar = position['entry_bar']
            
            # SL
            if d == 'long' and bar['low'] <= sl:
                pnl = (sl - ep) * amt
                account += pnl
                trades.append(pnl)
                position = None
                continue
            if d == 'short' and bar['high'] >= sl:
                pnl = (ep - sl) * amt
                account += pnl
                trades.append(pnl)
                position = None
                continue
            
            # TP
            if d == 'long' and bar['high'] >= tp:
                pnl = (tp - ep) * amt
                account += pnl
                trades.append(pnl)
                position = None
                continue
            if d == 'short' and bar['low'] <= tp:
                pnl = (ep - tp) * amt
                account += pnl
                trades.append(pnl)
                position = None
                continue
            
            # B/E
            if not be_done:
                if d == 'long':
                    risk_dist = ep - sl
                    if risk_dist > 0 and bar['high'] >= ep + risk_dist * be_trigger_r:
                        position['sl'] = ep  # Move to breakeven
                        position['be'] = True
                else:
                    risk_dist = sl - ep
                    if risk_dist > 0 and bar['low'] <= ep - risk_dist * be_trigger_r:
                        position['sl'] = ep
                        position['be'] = True
            
            # Time exit
            if i - entry_bar > 80:
                pnl = (bar['close'] - ep) * amt if d == 'long' else (ep - bar['close']) * amt
                account += pnl
                trades.append(pnl)
                position = None
                continue
        
        # Entry logic (only if no position AND cooldown passed)
        if position is None and (i - last_exit_bar) >= 10:
            # Find nearest swing points before current bar
            prev_highs = [idx for idx in swing_high_idxs if idx <= i]
            prev_lows = [idx for idx in swing_low_idxs if idx <= i]
            
            if len(prev_highs) < 2 or len(prev_lows) < 2:
                continue
            
            # Simple trend check: last 2 swing highs and lows
            last_2h = [swing_high_bars[idx] for idx in prev_highs[-2:]]
            last_2l = [swing_low_bars[idx] for idx in prev_lows[-2:]]
            
            atr_val = calc_atr_fast(bars[max(0, i-30):i+1])
            if atr_val <= 0:
                continue
            
            bullish = last_2h[-1] > last_2h[0] and last_2l[-1] > last_2l[0]
            bearish = last_2h[-1] < last_2h[0] and last_2l[-1] < last_2l[0]
            
            # Long at swing low in bullish trend (strict: must be AT the swing, not just near it)
            if bullish:
                last_low_idx = prev_lows[-1]
                last_low_price = swing_low_bars[last_low_idx]
                dist = abs(bar['close'] - last_low_price) / atr_val
                
                # Must be within 0.5 ATR of the swing low AND at the swing bar or 1-2 bars after
                if dist < 0.5 and (i - last_low_idx) <= 2:
                    ep = bar['close']
                    sl_buf = atr_val * sl_buffer_atr
                    sl = ep - sl_buf
                    rd = ep - sl
                    if rd > 0:
                        tp = ep + rd * tp_ratio
                        risk_amt = initial_account * 0.02
                        amt = risk_amt / rd
                        position = {
                            'dir': 'long', 'entry': ep, 'sl': sl, 'tp': tp,
                            'amount': amt, 'be': False, 'entry_bar': i
                        }
                        last_exit_bar = i  # Reset cooldown
            
            # Short at swing high in bearish trend
            if bearish:
                last_high_idx = prev_highs[-1]
                last_high_price = swing_high_bars[last_high_idx]
                dist = abs(bar['close'] - last_high_price) / atr_val
                
                if dist < 0.5 and (i - last_high_idx) <= 2:
                    ep = bar['close']
                    sl_buf = atr_val * sl_buffer_atr
                    sl = ep + sl_buf
                    rd = sl - ep
                    if rd > 0:
                        tp = ep - rd * tp_ratio
                        risk_amt = initial_account * 0.02
                        amt = risk_amt / rd
                        position = {
                            'dir': 'short', 'entry': ep, 'sl': sl, 'tp': tp,
                            'amount': amt, 'be': False, 'entry_bar': i
                        }
                        last_exit_bar = i  # Reset cooldown
    
    if len(trades) < 3:
        return None
    
    # trades are in dollar P&L (fixed position size)
    # Convert to R-multiple for proper comparison
    risk_per_trade = initial_account * 0.02  # $200 on $10k
    
    wins = [p for p in trades if p > 0]
    losses = [p for p in trades if p <= 0]
    total = sum(trades)
    wr = len(wins) / len(trades) if trades else 0
    
    # R-multiple calculation
    total_r = sum(p / risk_per_trade for p in trades)
    gross_r = sum(p / risk_per_trade for p in wins)
    gross_loss_r = abs(sum(p / risk_per_trade for p in losses))
    pf = gross_r / gross_loss_r if gross_loss_r > 0 else float('inf')
    
    return {
        'trades': len(trades),
        'win_rate': wr,
        'profit_factor': pf,
        'total_pnl': round(total, 2),
        'total_r': round(total_r, 2),
        'avg_pnl': round(total / len(trades), 2),
    }


def optimize_pair(pair_name, csv_file):
    """Fast optimization with reduced grid"""
    bars = load_csv(csv_file)
    if len(bars) < 100:
        return None
    
    best = None
    best_score = 0
    
    # Reduced grid — based on known good values
    grid = [
        {'swing_lookback': 5, 'sl_buffer_atr': 1.5, 'tp_ratio': 3.0, 'be_trigger': 1.5},
        {'swing_lookback': 8, 'sl_buffer_atr': 1.5, 'tp_ratio': 3.0, 'be_trigger': 1.5},
        {'swing_lookback': 10, 'sl_buffer_atr': 1.5, 'tp_ratio': 3.0, 'be_trigger': 1.5},
        {'swing_lookback': 10, 'sl_buffer_atr': 2.0, 'tp_ratio': 3.0, 'be_trigger': 1.5},
        {'swing_lookback': 10, 'sl_buffer_atr': 1.5, 'tp_ratio': 2.5, 'be_trigger': 1.0},
        {'swing_lookback': 10, 'sl_buffer_atr': 1.5, 'tp_ratio': 3.5, 'be_trigger': 2.0},
        {'swing_lookback': 12, 'sl_buffer_atr': 1.5, 'tp_ratio': 3.0, 'be_trigger': 1.5},
        {'swing_lookback': 15, 'sl_buffer_atr': 2.0, 'tp_ratio': 3.0, 'be_trigger': 1.5},
        {'swing_lookback': 10, 'sl_buffer_atr': 1.0, 'tp_ratio': 3.0, 'be_trigger': 1.5},
        {'swing_lookback': 10, 'sl_buffer_atr': 1.5, 'tp_ratio': 3.0, 'be_trigger': 1.0},
    ]
    
    for params in grid:
        result = backtest_fast(bars, params)
        if result and result['trades'] >= 5:
            # Score: profit factor * log(trades) for robustness
            import math
            score = result['profit_factor'] * math.log(result['trades'])
            if score > best_score:
                best_score = score
                best = {**result, 'params': params}
    
    return best


def run_all():
    """Run optimization on all pairs"""
    pairs = ['EURUSD', 'GBPUSD', 'USDJPY', 'EURJPY', 'XAUUSD']
    
    print("=" * 70)
    print("FalconFX — Fast 2-Year Multi-Pair Optimization")
    print("=" * 70)
    
    results = {}
    for pair in pairs:
        csv_file = os.path.join(PAIRS_DIR, f"{pair}60.csv")
        if not os.path.exists(csv_file):
            print(f"[{pair}] ✗ Not found")
            continue
        
        print(f"[{pair}] ", end="", flush=True)
        r = optimize_pair(pair, csv_file)
        
        if r:
            results[pair] = r
            print(f"Trades={r['trades']} | WR={r['win_rate']*100:.1f}% | "
                  f"PF={r['profit_factor']:.2f} | R={r['total_r']:.2f} | "
                  f"swing={r['params']['swing_lookback']} SLbuf={r['params']['sl_buffer_atr']}")
        else:
            print("No valid results")
    
    # Summary
    print("\n" + "=" * 70)
    print("FINAL RESULTS (2-Year 1H Data, 2023-2025)")
    print("=" * 70)
    print(f"{'Pair':<10} {'Trades':>6} {'WR%':>6} {'PF':>6} {'P&L(R)':>10} {'Params':>20}")
    print("-" * 60)
    
    total_r = 0
    for pair, r in results.items():
        total_r += r['total_r']
        p = r['params']
        print(f"{pair:<10} {r['trades']:>6} {r['win_rate']*100:>5.1f}% {r['profit_factor']:>6.2f} "
              f"{r['total_r']:>9.2f}R  sw={p['swing_lookback']} sl={p['sl_buffer_atr']} tp={p['tp_ratio']}")
    
    print("-" * 60)
    print(f"{'TOTAL':<10} {'':>6} {'':>6} {'':>6} {total_r:>9.2f}R")
    
    return results


if __name__ == "__main__":
    if len(sys.argv) > 1:
        pair = sys.argv[1]
        csv_file = os.path.join(PAIRS_DIR, f"{pair}60.csv")
        if os.path.exists(csv_file):
            r = optimize_pair(pair, csv_file)
            if r:
                print(f"\n{pair}:")
                for k, v in r.items():
                    print(f"  {k}: {v}")
    else:
        run_all()
