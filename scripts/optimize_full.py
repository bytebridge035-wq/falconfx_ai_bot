#!/usr/bin/env python3
"""
FalconFX Backtester — Full 2-Year Multi-Pair Optimization
Uses Yahoo Finance 1H data (2023-2025) for regime diversity testing
"""

import os
import sys
import csv
from datetime import datetime

# Add parent to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

PAIRS_DIR = os.path.expanduser("~/falconfx-bot/data")

def load_csv(filepath):
    """Load OHLCV CSV from Yahoo Finance format"""
    bars = []
    with open(filepath, 'r') as f:
        reader = csv.DictReader(f)
        headers = reader.fieldnames
        for row in reader:
            try:
                # Handle both Index and Datetime column names
                ts_str = row.get('Index', row.get('Datetime', row.get('Date', '')))
                if not ts_str:
                    continue
                
                # Parse timestamp
                for fmt in ['%Y-%m-%d %H:%M:%S%z', '%Y-%m-%d %H:%M:%S', '%Y-%m-%d %H:%M']:
                    try:
                        ts = datetime.strptime(ts_str.split('+')[0].split('-0')[0] if '+' not in ts_str and '-' not in ts_str[10:] else ts_str[:19], fmt)
                        break
                    except ValueError:
                        continue
                else:
                    ts = datetime.strptime(ts_str[:19], '%Y-%m-%d %H:%M:%S')
                
                o = float(row['Open'])
                h = float(row['High'])
                l = float(row['Low'])
                c = float(row['Close'])
                
                if o <= 0 or h <= 0 or l <= 0 or c <= 0:
                    continue
                
                bars.append({
                    'timestamp': ts,
                    'open': o,
                    'high': h,
                    'low': l,
                    'close': c,
                })
            except (ValueError, KeyError) as e:
                continue
    
    bars.sort(key=lambda x: x['timestamp'])
    return bars


def calc_atr(bars, period=14):
    """Calculate ATR"""
    trs = []
    for i in range(1, len(bars)):
        tr = max(
            bars[i]['high'] - bars[i]['low'],
            abs(bars[i]['high'] - bars[i-1]['close']),
            abs(bars[i]['low'] - bars[i-1]['close'])
        )
        trs.append(tr)
    
    if len(trs) < period:
        return trs[-1] if trs else 0
    
    atr = sum(trs[:period]) / period
    for i in range(period, len(trs)):
        atr = (atr * (period - 1) + trs[i]) / period
    
    return atr


def find_swing_points(bars, lookback):
    """Find swing highs and lows"""
    swing_highs = []
    swing_lows = []
    
    for i in range(lookback, len(bars) - lookback):
        is_high = True
        is_low = True
        
        for j in range(1, lookback + 1):
            if bars[i]['high'] <= bars[i-j]['high'] or bars[i]['high'] <= bars[i+j]['high']:
                is_high = False
            if bars[i]['low'] >= bars[i-j]['low'] or bars[i]['low'] >= bars[i+j]['low']:
                is_low = False
        
        if is_high:
            swing_highs.append((i, bars[i]['high'], bars[i]['timestamp']))
        if is_low:
            swing_lows.append((i, bars[i]['low'], bars[i]['timestamp']))
    
    return swing_highs, swing_lows


def check_trend(swing_highs, swing_lows, lookback=10):
    """Determine trend from swing structure"""
    recent_highs = [h for h in swing_highs[-lookback:]]
    recent_lows = [l for l in swing_lows[-lookback:]]
    
    if len(recent_highs) < 2 or len(recent_lows) < 2:
        return 'neutral'
    
    hh = sum(1 for i in range(1, len(recent_highs)) if recent_highs[i][1] > recent_highs[i-1][1])
    hl = sum(1 for i in range(1, len(recent_highs)) if recent_highs[i][1] < recent_highs[i-1][1])
    lh = sum(1 for i in range(1, len(recent_lows)) if recent_lows[i][1] > recent_lows[i-1][1])
    ll = sum(1 for i in range(1, len(recent_lows)) if recent_lows[i][1] < recent_lows[i-1][1])
    
    if hh >= 2 and lh >= 2:
        return 'bullish'
    elif hl >= 2 and ll >= 2:
        return 'bearish'
    return 'neutral'


def find_patterns(bars, swings, direction):
    """Find FalconFX patterns (RO3, double tops/bottoms, failed breaks)"""
    patterns = []
    swing_highs, swing_lows = swings
    
    # Double bottom (bullish)
    if direction in ['bullish', 'neutral']:
        for i in range(len(swing_lows) - 1):
            for j in range(i + 1, min(i + 5, len(swing_lows))):
                diff_pct = abs(swing_lows[i][1] - swing_lows[j][1]) / swing_lows[i][1] * 100
                if diff_pct < 0.5:  # Within 0.5%
                    # Confirm with bounce
                    post_low = [b for b in bars[swing_lows[j][0]:] if b['high'] > swing_lows[j][1]]
                    if post_low:
                        patterns.append({
                            'type': 'double_bottom',
                            'index': swing_lows[j][0],
                            'price': swing_lows[j][1],
                            'direction': 'bullish',
                            'strength': 0.8
                        })
    
    # Double top (bearish)
    if direction in ['bearish', 'neutral']:
        for i in range(len(swing_highs) - 1):
            for j in range(i + 1, min(i + 5, len(swing_highs))):
                diff_pct = abs(swing_highs[i][1] - swing_highs[j][1]) / swing_highs[i][1] * 100
                if diff_pct < 0.5:
                    post_high = [b for b in bars[swing_highs[j][0]:] if b['low'] < swing_highs[j][1]]
                    if post_high:
                        patterns.append({
                            'type': 'double_top',
                            'index': swing_highs[j][0],
                            'price': swing_highs[j][1],
                            'direction': 'bearish',
                            'strength': 0.8
                        })
    
    return patterns


def backtest(bars, pair_name, params):
    """Run FalconFX backtest on bar data"""
    swing_lookback = params.get('swing_lookback', 10)
    risk_pct = params.get('risk_percent', 1.0)
    tp_ratio = params.get('tp_ratio', 3.0)
    sl_buffer_atr_mult = params.get('sl_buffer_atr', 1.5)
    be_trigger_r = params.get('be_trigger', 1.5)
    be_lock_r = params.get('be_lock', 0.5)
    half_risk_r = params.get('half_risk_r', 2.0)
    max_risk_per_trade = params.get('max_risk', 0.02)
    
    # Find swing points
    swing_highs, swing_lows = find_swing_points(bars, swing_lookback)
    
    if len(swing_highs) < 3 or len(swing_lows) < 3:
        return None
    
    trades = []
    position = None
    entry_bar = None
    account = 10000.0
    peak_equity = account
    
    for i in range(swing_lookback * 2, len(bars)):
        # Check for exit if in position
        if position is not None:
            trade = position
            entry_price = trade['entry']
            sl = trade['sl']
            tp = trade['tp']
            direction = trade['dir']
            amount = trade['amount']
            be_triggered = trade['be_triggered']
            half_closed = trade['half_closed']
            entry_bar_idx = trade['entry_bar']
            
            # Current bar
            bar = bars[i]
            atr_val = calc_atr(bars[max(0, i-50):i+1], 14)
            
            # Stop loss hit
            if direction == 'long' and bar['low'] <= sl:
                pnl = (sl - entry_price) * amount
                account += pnl
                trade['exit_price'] = sl
                trade['exit_time'] = bar['timestamp']
                trade['pnl'] = pnl
                trade['pnl_r'] = pnl / (entry_price * amount * risk_pct / 100) if amount > 0 else 0
                trade['result'] = 'SL'
                trades.append(trade)
                position = None
                continue
            
            if direction == 'short' and bar['high'] >= sl:
                pnl = (entry_price - sl) * amount
                account += pnl
                trade['exit_price'] = sl
                trade['exit_time'] = bar['timestamp']
                trade['pnl'] = pnl
                trade['pnl_r'] = pnl / (entry_price * amount * risk_pct / 100) if amount > 0 else 0
                trade['result'] = 'SL'
                trades.append(trade)
                position = None
                continue
            
            # Take profit hit
            if direction == 'long' and bar['high'] >= tp:
                pnl = (tp - entry_price) * amount
                account += pnl
                trade['exit_price'] = tp
                trade['exit_time'] = bar['timestamp']
                trade['pnl'] = pnl
                trade['pnl_r'] = tp_ratio
                trade['result'] = 'TP'
                trades.append(trade)
                position = None
                continue
            
            if direction == 'short' and bar['low'] <= tp:
                pnl = (entry_price - tp) * amount
                account += pnl
                trade['exit_price'] = tp
                trade['exit_time'] = bar['timestamp']
                trade['pnl'] = pnl
                trade['pnl_r'] = tp_ratio
                trade['result'] = 'TP'
                trades.append(trade)
                position = None
                continue
            
            # Break-even management
            if not be_triggered:
                if direction == 'long':
                    risk_dist = entry_price - sl
                    be_level = entry_price + risk_dist * be_trigger_r
                    if bar['high'] >= be_level:
                        trade['be_triggered'] = True
                        trade['sl_new'] = entry_price + risk_dist * be_lock_r
                        trade['sl'] = trade['sl_new']
                else:
                    risk_dist = sl - entry_price
                    be_level = entry_price - risk_dist * be_trigger_r
                    if bar['low'] <= be_level:
                        trade['be_triggered'] = True
                        trade['sl_new'] = entry_price - risk_dist * be_lock_r
                        trade['sl'] = trade['sl_new']
            
            # Half-risk management
            if not half_closed and trade.get('be_triggered'):
                if direction == 'long':
                    risk_dist = entry_price - sl if sl < entry_price else (tp - entry_price) / tp_ratio
                    half_level = entry_price + risk_dist * half_risk_r
                    if bar['high'] >= half_level:
                        # Close half
                        half_amount = amount / 2
                        pnl = (half_level - entry_price) * half_amount
                        account += pnl
                        trade['amount'] = half_amount
                        trade['half_closed'] = True
                else:
                    risk_dist = sl - entry_price if sl > entry_price else (entry_price - tp) / tp_ratio
                    half_level = entry_price - risk_dist * half_risk_r
                    if bar['low'] <= half_level:
                        half_amount = amount / 2
                        pnl = (entry_price - half_level) * half_amount
                        account += pnl
                        trade['amount'] = half_amount
                        trade['half_closed'] = True
            
            # Time-based exit (stuck > 100 bars)
            if i - entry_bar_idx > 100 and not trade.get('be_triggered'):
                pnl = (bar['close'] - entry_price) * amount if direction == 'long' else (entry_price - bar['close']) * amount
                account += pnl
                trade['exit_price'] = bar['close']
                trade['exit_time'] = bar['timestamp']
                trade['pnl'] = pnl
                trade['result'] = 'TIME'
                trades.append(trade)
                position = None
                continue
        
        # Look for new setup (only if no position)
        if position is None and i >= swing_lookback * 4:
            # Get recent swing structure
            recent_highs = [h for h in swing_highs if h[0] <= i]
            recent_lows = [l for l in swing_lows if l[0] <= i]
            
            if len(recent_highs) < 2 or len(recent_lows) < 2:
                continue
            
            # Check trend
            trend = check_trend(recent_highs, recent_lows)
            
            # Find patterns
            patterns = find_patterns(bars, (recent_highs, recent_lows), trend)
            
            # Entry logic: look for setups at structure
            bar = bars[i]
            atr_val = calc_atr(bars[max(0, i-50):i+1], 14)
            
            if atr_val <= 0:
                continue
            
            # Long setup: price at/near swing low in bullish trend
            if trend == 'bullish':
                last_low = recent_lows[-1]
                dist_to_low = abs(bar['close'] - last_low[1]) / atr_val
                
                if dist_to_low < 1.0 and last_low[0] == i or (last_low[0] < i and i - last_low[0] <= 3):
                    # Check for bullish pattern or just structure
                    has_pattern = any(p['direction'] == 'bullish' and abs(p['index'] - i) < 10 for p in patterns)
                    
                    if has_pattern or dist_to_low < 0.5:
                        entry_price = bar['close']
                        sl_buffer = atr_val * sl_buffer_atr_mult
                        sl = entry_price - sl_buffer
                        risk_dist = entry_price - sl
                        if risk_dist <= 0:
                            continue
                        tp = entry_price + risk_dist * tp_ratio
                        
                        # Position sizing
                        risk_amount = account * max_risk_per_trade
                        amount = risk_amount / risk_dist
                        
                        position = {
                            'dir': 'long',
                            'entry': entry_price,
                            'sl': sl,
                            'tp': tp,
                            'amount': amount,
                            'entry_time': bar['timestamp'],
                            'entry_bar': i,
                            'be_triggered': False,
                            'half_closed': False,
                            'pattern': 'structure',
                        }
            
            # Short setup: price at/near swing high in bearish trend
            if trend == 'bearish':
                last_high = recent_highs[-1]
                dist_to_high = abs(bar['close'] - last_high[1]) / atr_val
                
                if dist_to_high < 1.0 and last_high[0] == i or (last_high[0] < i and i - last_high[0] <= 3):
                    has_pattern = any(p['direction'] == 'bearish' and abs(p['index'] - i) < 10 for p in patterns)
                    
                    if has_pattern or dist_to_high < 0.5:
                        entry_price = bar['close']
                        sl_buffer = atr_val * sl_buffer_atr_mult
                        sl = entry_price + sl_buffer
                        risk_dist = sl - entry_price
                        if risk_dist <= 0:
                            continue
                        tp = entry_price - risk_dist * tp_ratio
                        
                        risk_amount = account * max_risk_per_trade
                        amount = risk_amount / risk_dist
                        
                        position = {
                            'dir': 'short',
                            'entry': entry_price,
                            'sl': sl,
                            'tp': tp,
                            'amount': amount,
                            'entry_time': bar['timestamp'],
                            'entry_bar': i,
                            'be_triggered': False,
                            'half_closed': False,
                            'pattern': 'structure',
                        }
    
    # Calculate results
    if not trades:
        return {'pair': pair_name, 'trades': 0, 'params': params}
    
    wins = [t for t in trades if t['pnl'] > 0]
    losses = [t for t in trades if t['pnl'] <= 0]
    total_pnl = sum(t['pnl'] for t in trades)
    total_r = sum(t.get('pnl_r', 0) for t in trades)
    win_rate = len(wins) / len(trades) if trades else 0
    avg_win = sum(t['pnl'] for t in wins) / len(wins) if wins else 0
    avg_loss = sum(t['pnl'] for t in losses) / len(losses) if losses else 0
    profit_factor = abs(sum(t['pnl'] for t in wins) / sum(t['pnl'] for t in losses)) if losses and sum(t['pnl'] for t in losses) != 0 else float('inf')
    
    # Max drawdown
    peak = account
    dd = 0
    for t in trades:
        equity = account + t['pnl']
        if equity > peak:
            peak = equity
        curr_dd = (peak - equity) / peak
        if curr_dd > dd:
            dd = curr_dd
    
    return {
        'pair': pair_name,
        'trades': len(trades),
        'wins': len(wins),
        'losses': len(losses),
        'win_rate': win_rate,
        'total_pnl': round(total_pnl, 2),
        'total_r': round(total_r, 2),
        'profit_factor': round(profit_factor, 2),
        'avg_win': round(avg_win, 2),
        'avg_loss': round(avg_loss, 2),
        'max_drawdown': round(dd * 100, 1),
        'final_equity': round(account, 2),
        'params': params,
    }


def optimize_pair(pair_name, csv_file):
    """Optimize parameters for a single pair"""
    bars = load_csv(csv_file)
    if len(bars) < 100:
        return None
    
    best = None
    best_pf = 0
    
    # Parameter grid
    for swing_lb in [5, 8, 10, 12, 15, 20]:
        for sl_buffer in [1.0, 1.5, 2.0]:
            for tp_ratio in [2.5, 3.0, 3.5]:
                for be_trigger in [1.0, 1.5, 2.0]:
                    params = {
                        'swing_lookback': swing_lb,
                        'sl_buffer_atr': sl_buffer,
                        'tp_ratio': tp_ratio,
                        'be_trigger': be_trigger,
                        'be_lock': 0.5,
                        'half_risk_r': 2.0,
                        'max_risk': 0.02,
                    }
                    
                    result = backtest(bars, pair_name, params)
                    if result and result['trades'] >= 5:
                        if result['profit_factor'] > best_pf:
                            best_pf = result['profit_factor']
                            best = result
    
    return best


def run_all():
    """Run optimization on all pairs"""
    pairs = ['EURUSD', 'GBPUSD', 'USDJPY', 'EURJPY', 'XAUUSD']
    
    print("=" * 70)
    print("FalconFX — Multi-Pair Optimization (2-Year 1H Data)")
    print("=" * 70)
    
    all_results = {}
    
    for pair in pairs:
        csv_file = os.path.join(PAIRS_DIR, f"{pair}60.csv")
        if not os.path.exists(csv_file):
            print(f"\n[{pair}] ✗ CSV file not found: {csv_file}")
            continue
        
        print(f"\n[{pair}] Optimizing...")
        result = optimize_pair(pair, csv_file)
        
        if result:
            all_results[pair] = result
            print(f"  Trades: {result['trades']} | WR: {result['win_rate']*100:.1f}% | "
                  f"PF: {result['profit_factor']:.2f} | P&L: {result['total_r']:.2f}R | "
                  f"MaxDD: {result['max_drawdown']:.1f}%")
            print(f"  Best params: swing={result['params']['swing_lookback']}, "
                  f"SLbuf={result['params']['sl_buffer_atr']}, "
                  f"TP={result['params']['tp_ratio']}R, "
                  f"B/E={result['params']['be_trigger']}R")
        else:
            print(f"  ✗ No valid results")
    
    # Summary table
    print("\n" + "=" * 70)
    print("FINAL RESULTS")
    print("=" * 70)
    print(f"{'Pair':<10} {'Trades':>6} {'WR%':>6} {'PF':>6} {'P&L(R)':>8} {'MaxDD%':>8}")
    print("-" * 50)
    
    total_r = 0
    for pair, r in all_results.items():
        print(f"{pair:<10} {r['trades']:>6} {r['win_rate']*100:>5.1f}% {r['profit_factor']:>6.2f} "
              f"{r['total_r']:>8.2f} {r['max_drawdown']:>7.1f}%")
        total_r += r['total_r']
    
    print("-" * 50)
    print(f"{'TOTAL':<10} {'':>6} {'':>6} {'':>6} {total_r:>8.2f}")
    
    return all_results


if __name__ == "__main__":
    if len(sys.argv) > 1:
        # Single pair mode
        pair = sys.argv[1]
        csv_file = os.path.join(PAIRS_DIR, f"{pair}60.csv")
        if os.path.exists(csv_file):
            result = optimize_pair(pair, csv_file)
            if result:
                print(f"\n{pair} Optimization Result:")
                for k, v in result.items():
                    if k != 'params':
                        print(f"  {k}: {v}")
                    else:
                        print(f"  params: {v}")
            else:
                print(f"No valid results for {pair}")
        else:
            print(f"File not found: {csv_file}")
    else:
        run_all()
