#!/usr/bin/env python3
"""
FalconFX v6 — NumPy-accelerated backtest
Aligned with Pine Script v6 and MQL5 v6 logic.

Sections:
  1. Config + Constants
  2. Data Loading
  3. Indicator Calculation (ATR, Swings)
  4. Pattern Detection (Engulfing, Pin Bar, Inside Bar, Flag)
  5. Entry Signal Generation
  6. Trade Simulation (Entry, Exit, BE, Scale-In)
  7. FTMO Risk Management
  8. Results Calculation + Output
"""

import os, sys, csv, math
import numpy as np
from collections import defaultdict

# === SECTION 1: CONFIG + CONSTANTS ==========================================
# All parameters match Pine Script v6 and MQL5 v6 exactly.

KAGGLE_DIR = os.path.expanduser("~/falconfx-bot/data/kaggle/top_pairs")
UNIFIED_DIR = os.path.expanduser("~/falconfx-bot/data/unified")

# Strategy parameters (match Pine Script inputs)
SWING_LB = 10          # Swing Lookback: bars each side for pivot detection
SL_BUFFER = 1.5        # SL Buffer: ATR multiplier below/above structure
BE_TRIGGER = 1.5       # Break-Even Trigger: R-multiples before moving SL
TP_RATIO = 3.0         # Take-Profit Ratio: 3R target
ENTRY_MAX_DIST = 1.5   # Entry Max Distance: ATR multiplier from structure
ATR_LEN = 14           # ATR Length: Wilder's smoothing period

# FTMO risk parameters
RISK_PCT = 1.0         # Risk % per trade (1% of equity)
MAX_DAILY_LOSS = 5.0   # Max daily loss % (FTMO rule)
MAX_TOTAL_DD = 8.0     # Max total drawdown % (FTMO rule with safety margin)
MAX_TRADES_DAY = 4     # Max trades per day
CONSEC_LOSS_MAX = 3    # Max consecutive losses before stopping

# Backtest settings
INITIAL_CAPITAL = 10000.0
COMMISSION_PCT = 0.02  # 0.02% per trade (matches Pine Script commission_value)


# === SECTION 2: DATA LOADING ================================================
# Loads OHLCV CSV data, normalizes column names, filters invalid bars.
# Supports multiple timestamp column names for different data sources.

def load_csv(filepath, max_bars=80000):
    bars = []
    with open(filepath, 'r', encoding='utf-8-sig') as f:
        reader = csv.DictReader(f)
        for row in reader:
            r = {k.strip().lower(): v.strip() for k, v in row.items() if k}
            try:
                ts_str = (r.get('timestamp') or r.get('date_time') or
                          r.get('datetime') or r.get('date') or '')
                if not ts_str:
                    continue
                o, h, l, c = float(r['open']), float(r['high']), float(r['low']), float(r['close'])
                if o <= 0 or h <= 0 or l <= 0 or c <= 0:
                    continue
                bars.append((ts_str[:19], o, h, l, c))
            except Exception:
                continue
    # Subsample if too many bars (keeps memory manageable)
    if len(bars) > max_bars:
        step = len(bars) // max_bars
        bars = bars[::step]
    return bars


# === SECTION 3: INDICATOR CALCULATION =======================================
# ATR: Average True Range using Wilder's smoothing (matches ta.atr in Pine).
# Swings: Pivot highs/lows using strict > (matches ta.pivothigh in Pine).

def calculate_atr(h_arr, l_arr, c_arr, n):
    """Calculate ATR using Wilder's smoothing method."""
    tr = np.zeros(len(c_arr))
    tr[1:] = np.maximum(h_arr[1:] - l_arr[1:],
                         np.maximum(np.abs(h_arr[1:] - c_arr[:-1]),
                                    np.abs(l_arr[1:] - c_arr[:-1])))
    atr = np.zeros(len(c_arr))
    if len(c_arr) > n:
        atr[n] = np.mean(tr[1:n + 1])
        for i in range(n + 1, len(c_arr)):
            atr[i] = (atr[i - 1] * (n - 1) + tr[i]) / n
    return atr


def detect_swings(h_arr, l_arr, lb):
    """
    Detect swing highs and lows.
    Swing high at bar i: h[i] is strictly greater than all h[i-lb..i+lb].
    Swing low at bar i: l[i] is strictly less than all l[i-lb..i+lb].
    Uses strict > to match Pine Script ta.pivothigh/ta.pivotlow.
    """
    n = len(h_arr)
    is_sh = np.zeros(n, dtype=bool)
    is_sl = np.zeros(n, dtype=bool)
    for i in range(lb, n - lb):
        is_sh[i] = (np.all(h_arr[i - lb:i] < h_arr[i]) and
                     np.all(h_arr[i + 1:i + lb + 1] < h_arr[i]))
        is_sl[i] = (np.all(l_arr[i - lb:i] > l_arr[i]) and
                     np.all(l_arr[i + 1:i + lb + 1] > l_arr[i]))
    return is_sh, is_sl


# === SECTION 4: PATTERN DETECTION ===========================================
# All patterns match Pine Script v6 logic exactly.

def detect_engulfing(o_arr, h_arr, l_arr, c_arr, i):
    """
    Engulfing pattern detection.
    Bullish: current green candle fully engulfs previous red candle.
    Bearish: current red candle fully engulfs previous green candle.
    Uses strict < and > to match Pine Script (not >=, no 1.2x filter).
    """
    if i < 1:
        return False, False
    po, ph, pl, pc = o_arr[i - 1], h_arr[i - 1], l_arr[i - 1], c_arr[i - 1]
    co, ch, cl, cc = o_arr[i], h_arr[i], l_arr[i], c_arr[i]

    bull = cc > co and pc < ph and cc > ph and co < pc
    bear = cc < co and pc > ph and cc < ph and co > pc
    return bull, bear


def detect_pin_bar(h_arr, l_arr, c_arr, o_arr, atr_val, i):
    """
    Pin bar pattern detection.
    Bull pin: lowerWick > bodySize * 2.0, upperWick < bodySize * 0.5.
    Bear pin: upperWick > bodySize * 2.0, lowerWick < bodySize * 0.5.
    Ratios match Pine Script v6 and MQL5 v6.
    """
    if i < 1 or atr_val <= 0:
        return False, False
    c, o, h, l = c_arr[i], o_arr[i], h_arr[i], l_arr[i]
    body = abs(c - o)
    if body <= 0:
        return False, False
    uw = h - max(c, o)
    lw = min(c, o) - l

    bull = lw > body * 2.0 and uw < body * 0.5
    bear = uw > body * 2.0 and lw < body * 0.5
    return bull, bear


def detect_inside_bar(h_arr, l_arr, i):
    """Inside bar: current range fully inside previous range."""
    if i < 1:
        return False
    return h_arr[i] < h_arr[i - 1] and l_arr[i] > l_arr[i - 1]


def detect_flag(h_arr, l_arr, c_arr, o_arr, atr_val, i):
    """
    Flag/breakout bar detection.
    Bull: current high ~= prev high (within ATR * 0.01), low > prev low, body > ATR * 0.3.
    Bear: current low ~= prev low (within ATR * 0.01), high < prev high, body > ATR * 0.3.
    Uses tolerance instead of exact floating point equality (matches Pine fix).
    """
    if i < 1 or atr_val <= 0:
        return False, False
    c, o, h, l = c_arr[i], o_arr[i], h_arr[i], l_arr[i]
    body = abs(c - o)
    tol = atr_val * 0.01

    bull = (c > o and abs(h - h_arr[i - 1]) < tol and
            l > l_arr[i - 1] and body > atr_val * 0.3)
    bear = (c < o and abs(l - l_arr[i - 1]) < tol and
            h < h_arr[i - 1] and body > atr_val * 0.3)
    return bull, bear


# === SECTION 5-7: TRADE SIMULATION + RISK MANAGEMENT =========================
# Simulates trades bar-by-bar, matching Pine Script strategy() behavior.
# Key differences from old backtest:
#   - Position sizing uses DYNAMIC equity (not fixed $10k)
#   - No time-based exit (removed — not in Pine Script)
#   - No entry cooldown (removed — not in Pine Script)
#   - Calendar day detection for FTMO daily limits

def backtest(bars, pair_name=""):
    n = len(bars)
    if n < 200:
        return None

    ts_arr = [b[0] for b in bars]
    o_arr = np.array([b[1] for b in bars], dtype=np.float64)
    h_arr = np.array([b[2] for b in bars], dtype=np.float64)
    l_arr = np.array([b[3] for b in bars], dtype=np.float64)
    c_arr = np.array([b[4] for b in bars], dtype=np.float64)

    # Calculate indicators
    atr = calculate_atr(h_arr, l_arr, c_arr, ATR_LEN)
    is_sh, is_sl = detect_swings(h_arr, l_arr, SWING_LB)

    # Get swing indices for trend detection
    sh_idx = np.where(is_sh)[0]
    sl_idx = np.where(is_sl)[0]

    # === State Variables ===
    position = None          # [entryPrice, sl, tp, direction, qty, beDone, entryBar, slDist]
    trades = []              # List of (pnl, exitReason)
    peak_eq = INITIAL_CAPITAL
    daily_start_eq = INITIAL_CAPITAL
    trades_today = 0
    consec_losses = 0
    last_exit_bar = -50
    current_day = None
    last_high_val = 0.0
    last_low_val = 0.0
    equity = INITIAL_CAPITAL  # Dynamic equity tracking

    for i in range(SWING_LB * 2, n):
        ts = ts_arr[i]
        o, h, l, c = o_arr[i], h_arr[i], l_arr[i], c_arr[i]

        # --- Calendar Day Detection (matches Pine Script ta.change(time("D"))) ---
        day_key = ts[:10]
        if day_key != current_day:
            current_day = day_key
            trades_today = 0
            daily_start_eq = equity

        # --- Update Swing Values ---
        if is_sh[i]:
            last_high_val = h
        if is_sl[i]:
            last_low_val = l

        # --- Trend Detection ---
        sh_before = sh_idx[sh_idx <= i]
        sl_before = sl_idx[sl_idx <= i]
        trend = 0
        if len(sh_before) >= 2 and len(sl_before) >= 2:
            if h_arr[sh_before[-1]] > h_arr[sh_before[-2]] and l_arr[sl_before[-1]] > l_arr[sl_before[-2]]:
                trend = 1
            elif h_arr[sh_before[-1]] < h_arr[sh_before[-2]] and l_arr[sl_before[-1]] < l_arr[sl_before[-2]]:
                trend = -1

        atr_val = atr[i]
        if atr_val <= 0:
            continue

        # --- Update Equity and Peak ---
        peak_eq = max(peak_eq, equity)
        daily_pnl = equity - daily_start_eq

        # --- FTMO Compliance Checks ---
        can_trade = (daily_pnl > -(equity * MAX_DAILY_LOSS / 100) and
                     equity > peak_eq * (1 - MAX_TOTAL_DD / 100) and
                     trades_today < MAX_TRADES_DAY and
                     consec_losses < CONSEC_LOSS_MAX)

        # --- Exit Logic ---
        if position:
            ep, sl, tp, d, amt, be_done, entry_bar, sl_dist = position
            exited = False
            pnl = 0.0

            if d == 'long':
                if l <= sl:
                    pnl = (sl - ep) * amt * (1 - COMMISSION_PCT / 100)
                    trades.append((pnl, 'SL'))
                    consec_losses = consec_losses + 1 if pnl < 0 else 0
                    exited = True
                elif h >= tp:
                    pnl = (tp - ep) * amt * (1 - COMMISSION_PCT / 100)
                    trades.append((pnl, 'TP'))
                    consec_losses = 0
                    exited = True
            else:  # short
                if h >= sl:
                    pnl = (ep - sl) * amt * (1 - COMMISSION_PCT / 100)
                    trades.append((pnl, 'SL'))
                    consec_losses = consec_losses + 1 if pnl < 0 else 0
                    exited = True
                elif l <= tp:
                    pnl = (ep - tp) * amt * (1 - COMMISSION_PCT / 100)
                    trades.append((pnl, 'TP'))
                    consec_losses = 0
                    exited = True

            # --- Break-Even Method ---
            if not exited and not be_done:
                if d == 'long' and (c - ep) >= sl_dist * BE_TRIGGER:
                    position[1] = ep + atr_val * 0.1
                    position[5] = True
                elif d == 'short' and (ep - c) >= sl_dist * BE_TRIGGER:
                    position[1] = ep - atr_val * 0.1
                    position[5] = True

            if exited:
                equity += pnl  # Update equity with realized PnL
                position = None
                last_exit_bar = i
                continue

        # --- Entry Logic ---
        # No cooldown (matches Pine Script — can re-enter immediately)
        if position is None and can_trade and trend != 0:
            ref = last_low_val if trend == 1 else last_high_val
            if abs(c - ref) > atr_val * ENTRY_MAX_DIST:
                continue

            all_sw = np.concatenate([sh_idx, sl_idx])
            all_sw = all_sw[all_sw <= i]
            if len(all_sw) == 0 or (i - all_sw[-1]) > SWING_LB * 3:
                continue

            # Pattern detection
            bull_e, bear_e = detect_engulfing(o_arr, h_arr, l_arr, c_arr, i)
            bull_p, bear_p = detect_pin_bar(h_arr, l_arr, c_arr, o_arr, atr_val, i)
            ib = detect_inside_bar(h_arr, l_arr, i)
            bull_f, bear_f = detect_flag(h_arr, l_arr, c_arr, o_arr, atr_val, i)

            if trend == 1 and (bull_e or bull_p or ib or bull_f):
                sl_d = (h - last_low_val) + atr_val * SL_BUFFER
                # FIX: Use DYNAMIC equity for position sizing (matches Pine strategy.equity)
                risk_amt = equity * RISK_PCT / 100
                qty = risk_amt / sl_d if sl_d > 0 else 0
                if qty > 0:
                    position = [c, c - sl_d, c + sl_d * TP_RATIO, 'long', qty, False, i, sl_d]
                    trades_today += 1
                    last_exit_bar = i

            elif trend == -1 and (bear_e or bear_p or ib or bear_f):
                sl_d = (last_high_val - l) + atr_val * SL_BUFFER
                risk_amt = equity * RISK_PCT / 100
                qty = risk_amt / sl_d if sl_d > 0 else 0
                if qty > 0:
                    position = [c, c + sl_d, c - sl_d * TP_RATIO, 'short', qty, False, i, sl_d]
                    trades_today += 1
                    last_exit_bar = i

    # === SECTION 8: RESULTS CALCULATION ======================================
    if len(trades) < 3:
        return None

    wins = [t for t in trades if t[0] > 0]
    losses = [t for t in trades if t[0] <= 0]
    total_pnl = sum(t[0] for t in trades)
    wr = len(wins) / len(trades) * 100
    risk_per = INITIAL_CAPITAL * RISK_PCT / 100
    total_r = sum(t[0] / risk_per for t in trades)
    gross_r = sum(t[0] / risk_per for t in wins)
    gross_lr = abs(sum(t[0] / risk_per for t in losses))
    pf = gross_r / gross_lr if gross_lr > 0 else float('inf')

    # Max drawdown calculation
    eq_curve = [INITIAL_CAPITAL]
    for t in trades:
        eq_curve.append(eq_curve[-1] + t[0])
    pk = eq_curve[0]
    max_dd = 0
    for e in eq_curve:
        pk = max(pk, e)
        max_dd = max(max_dd, (pk - e) / pk * 100)

    reasons = defaultdict(int)
    for t in trades:
        reasons[t[1]] += 1

    return {
        'pair': pair_name, 'trades': len(trades), 'wr': round(wr, 1),
        'pf': round(pf, 2), 'total_pnl': round(total_pnl, 2),
        'total_r': round(total_r, 2), 'max_dd': round(max_dd, 2),
        'reasons': dict(reasons), 'wins': len(wins), 'losses': len(losses)
    }


# === MAIN: Run backtest on all configured pairs =============================

focus = {
    'EURUSD_15m': os.path.join(KAGGLE_DIR, 'EURUSD-2000-2020-15m.csv'),
    'EURJPY_15m': os.path.join(KAGGLE_DIR, 'EURJPY-2000-2020-15m.csv'),
    'GBPUSD_1h': os.path.join(UNIFIED_DIR, 'GBPUSD60.csv'),
    'USDJPY_15m': os.path.join(KAGGLE_DIR, 'USDJPY-2000-2020-15m.csv'),
    'EURUSD_1h': os.path.join(UNIFIED_DIR, 'EURUSD60.csv'),
    'EURJPY_1h': os.path.join(UNIFIED_DIR, 'EURJPY60.csv'),
    'USDCHF_15m': os.path.join(KAGGLE_DIR, 'USDCHF-2000-2020-15m.csv'),
    'USDCAD_15m': os.path.join(KAGGLE_DIR, 'USDCAD-2000-2020-15m.csv'),
}

print("=" * 75)
print("FALCONFX v6.0 — NUMPY BACKTEST (aligned with Pine Script v6 + MQL5 v6)")
print(f"  Swing={SWING_LB} SLbuf={SL_BUFFER} BE={BE_TRIGGER}R TP={TP_RATIO}:1 Risk={RISK_PCT}%")
print(f"  FTMO: MaxDailyLoss={MAX_DAILY_LOSS}% MaxDD={MAX_TOTAL_DD}% MaxTrades={MAX_TRADES_DAY} MaxConsec={CONSEC_LOSS_MAX}")
print(f"  Position sizing: DYNAMIC equity (not fixed)")
print(f"  No time exit, no cooldown (matches Pine Script)")
print("=" * 75)

results = []
for name, path in sorted(focus.items()):
    if not os.path.exists(path):
        print(f"  [{name}] NOT FOUND")
        continue
    bars = load_csv(path)
    print(f"  [{name}] {len(bars)} bars ... ", end="", flush=True)
    r = backtest(bars, name)
    if r and r['trades'] >= 5:
        results.append(r)
        print(f"OK T={r['trades']} WR={r['wr']}% PF={r['pf']} R={r['total_r']} DD={r['max_dd']}%")
    else:
        print(f"SKIP {'Only ' + str(r['trades']) + ' trades' if r else 'No results'}")

if results:
    print("\n" + "-" * 75)
    print(f"{'Pair':<15} {'Trades':>6} {'W':>4} {'L':>4} {'WR%':>6} {'PF':>6} {'P&L($)':>10} {'R':>8} {'MaxDD':>7}")
    print("-" * 75)
    for r in sorted(results, key=lambda x: x['total_r'], reverse=True):
        print(f"{r['pair']:<15} {r['trades']:>6} {r['wins']:>4} {r['losses']:>4} {r['wr']:>5.1f}% "
              f"{r['pf']:>6.2f} {r['total_pnl']:>9.2f} {r['total_r']:>7.2f} {r['max_dd']:>6.2f}%")
    print("-" * 75)
    total_r = sum(r['total_r'] for r in results)
    total_t = sum(r['trades'] for r in results)
    print(f"{'TOTAL':<15} {total_t:>6} {'':>4} {'':>4} {'':>6} {'':>6} {'':>10} {total_r:>7.2f} {'':>7}")

    print("\n  Exit Reasons:")
    for r in results:
        parts = [f"{k}:{v}" for k, v in sorted(r['reasons'].items())]
        print(f"    {r['pair']:<15} {', '.join(parts)}")

print("\n" + "=" * 75)
