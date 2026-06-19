#!/usr/bin/env python3
"""
FalconFX Tick-Level Backtester
Runs backtest on .hst data with intrabar simulation for accurate results.
Uses the same logic as the MT5 EA but runs locally for fast iteration.

This simulates what MT5 Strategy Tester would do with "Every tick" mode
by using the OHLCV data to simulate intrabar price movement.

Usage:
   python tick_backtest.py --symbol EURJPY --data data/TIMEFRAME_1H.csv --swing 5
"""

import argparse
import sys
from datetime import datetime
from typing import Optional

import pandas as pd


# ═══════════════════════════════════════════════════════════════════════════
# TRADE STATE
# ═══════════════════════════════════════════════════════════════════════════

class Trade:
    def __init__(self, direction, entry_price, sl, tp, entry_time, risk):
        self.direction = direction
        self.entry_price = entry_price
        self.sl = sl
        self.tp = tp
        self.entry_time = entry_time
        self.risk = risk
        self.exit_price = None
        self.exit_time = None
        self.exit_reason = None
        self.pnl_r = 0.0
        self.be_moved = False


# ═══════════════════════════════════════════════════════════════════════════
# FALCONFX TICK BACKTESTER
# ═══════════════════════════════════════════════════════════════════════════

class FalconFXTickBacktester:
    """
    Simulates MT5 "Every tick" backtest using OHLCV bar data.
    Intrabar simulation: checks if SL/TP was hit within a bar using H/L.
    """
    
    def __init__(self, swing_lookback=8, impulse_min_bars=3, atr_period=14,
                 risk_pct=1.0, max_trades_per_day=2, tp_ratio=3.0,
                 be_trigger_r=1.5, sl_atr_multiplier=1.5,
                 use_half_risk=True, half_risk_hours=4,
                 session_filter=True):
        
        self.swing_lookback = swing_lookback
        self.impulse_min_bars = impulse_min_bars
        self.atr_period = atr_period
        self.risk_pct = risk_pct
        self.max_trades_per_day = max_trades_per_day
        self.tp_ratio = tp_ratio
        self.be_trigger_r = be_trigger_r
        self.sl_atr_multiplier = sl_atr_multiplier
        self.use_half_risk = use_half_risk
        self.half_risk_hours = half_risk_hours
        self.session_filter = session_filter
        
        # State
        self.trades = []
        self.current_trade: Optional[Trade] = None
        self.trades_today = 0
        self.last_trade_day = None
        
        # Structure
        self.swing_highs = []
        self.swing_lows = []
        self.bullish_structure = False
        self.bearish_structure = False
        self.resistance_level = 0.0
        self.support_level = 0.0
        
        # Nature
        self.in_impulsive = False
        self.in_corrective = False
        self.consecutive_up_seq = 0
        self.consecutive_down_seq = 0
        self.correction_start = 0.0
    
    def calculate_atr(self, df, bar_idx):
        if bar_idx < self.atr_period:
            return 0.0
        high = df['high'].iloc[bar_idx-self.atr_period:bar_idx]
        low = df['low'].iloc[bar_idx-self.atr_period:bar_idx]
        tr = high.values - low.values
        return float(tr.mean()) if len(tr) > 0 else 0.0
    
    def detect_swing(self, df, bar_idx):
        lb = self.swing_lookback
        if bar_idx < lb or bar_idx >= len(df) - lb:
            return False, False
        
        high = df['high'].iloc[bar_idx]
        low = df['low'].iloc[bar_idx]
        
        is_high = all(df['high'].iloc[i] < high for i in range(bar_idx-lb, bar_idx+lb+1) if i != bar_idx)
        is_low = all(df['low'].iloc[i] > low for i in range(bar_idx-lb, bar_idx+lb+1) if i != bar_idx)
        
        return is_high, is_low
    
    def update_structure(self, df, bar_idx):
        is_high, is_low = self.detect_swing(df, bar_idx)
        
        if is_high:
            self.swing_highs.append((bar_idx, df['high'].iloc[bar_idx]))
            if len(self.swing_highs) > 10:
                self.swing_highs = self.swing_highs[-10:]
        
        if is_low:
            self.swing_lows.append((bar_idx, df['low'].iloc[bar_idx]))
            if len(self.swing_lows) > 10:
                self.swing_lows = self.swing_lows[-10:]
        
        if len(self.swing_highs) >= 2 and len(self.swing_lows) >= 2:
            sh = sorted(self.swing_highs, key=lambda x: x[0])[-2:]
            sl = sorted(self.swing_lows, key=lambda x: x[0])[-2:]
            
            self.bullish_structure = sh[-1][1] > sh[-2][1] and sl[-1][1] > sl[-2][1]
            self.bearish_structure = sh[-1][1] < sh[-2][1] and sl[-1][1] < sl[-2][1]
            
            self.resistance_level = sh[-1][1]
            self.support_level = sl[-1][1]
    
    def update_nature(self, df, bar_idx):
        if bar_idx == 0:
            return
        
        close = df['close'].iloc[bar_idx]
        open_ = df['open'].iloc[bar_idx]
        high = df['high'].iloc[bar_idx]
        low = df['low'].iloc[bar_idx]
        
        body_size = abs(close - open_)
        range_ = high - low
        
        start = max(0, bar_idx - 19)
        avg_body = abs(df['close'].iloc[start:bar_idx+1] - df['open'].iloc[start:bar_idx+1]).mean()
        avg_range = (df['high'].iloc[start:bar_idx+1] - df['low'].iloc[start:bar_idx+1]).mean()
        
        if close > open_:
            self.consecutive_up_seq += 1
            self.consecutive_down_seq = 0
        elif close < open_:
            self.consecutive_down_seq += 1
            self.consecutive_up_seq = 0
        else:
            self.consecutive_up_seq = 0
            self.consecutive_down_seq = 0
        
        impulse_up = self.consecutive_up_seq >= self.impulse_min_bars and body_size > avg_body * 1.3
        impulse_down = self.consecutive_down_seq >= self.impulse_min_bars and body_size > avg_body * 1.3
        
        is_corrective = (body_size < avg_body * 0.6 and range_ < avg_range * 0.7 and
                         abs(close - open_) < abs(high - low) * 0.4)
        
        if impulse_up or impulse_down:
            self.in_impulsive = True
            self.in_corrective = False
            self.correction_start = close
        elif self.in_impulsive and is_corrective:
            self.in_impulsive = False
            self.in_corrective = True
    
    def near_resistance(self, price, atr):
        return abs(price - self.resistance_level) < atr * 0.5
    
    def near_support(self, price, atr):
        return abs(price - self.support_level) < atr * 0.5
    
    def bullish_engulfing(self, df, bar_idx):
        if bar_idx < 1:
            return False
        c = df['close'].iloc[bar_idx]
        o = df['open'].iloc[bar_idx]
        pc = df['close'].iloc[bar_idx - 1]
        po = df['open'].iloc[bar_idx - 1]
        return (c > o and pc < po and o <= pc and c >= po and
                abs(c - o) > abs(pc - po) * 1.2)
    
    def bearish_engulfing(self, df, bar_idx):
        if bar_idx < 1:
            return False
        c = df['close'].iloc[bar_idx]
        o = df['open'].iloc[bar_idx]
        pc = df['close'].iloc[bar_idx - 1]
        po = df['open'].iloc[bar_idx - 1]
        return (c < o and pc > po and o >= pc and c <= po and
                abs(c - o) > abs(pc - po) * 1.2)
    
    def bullish_pin_bar(self, df, bar_idx):
        if bar_idx < 1:
            return False
        c = df['close'].iloc[bar_idx]
        o = df['open'].iloc[bar_idx]
        h = df['high'].iloc[bar_idx]
        l = df['low'].iloc[bar_idx]
        body = abs(c - o)
        range_ = h - l
        upper_wick = h - max(c, o)
        lower_wick = min(c, o) - l
        start = max(0, bar_idx - 19)
        avg_range = (df['high'].iloc[start:bar_idx+1] - df['low'].iloc[start:bar_idx+1]).mean()
        return (lower_wick > body * 2.5 and upper_wick < body * 0.3 and
                range_ > avg_range * 0.6 and c > o)
    
    def bearish_pin_bar(self, df, bar_idx):
        if bar_idx < 1:
            return False
        c = df['close'].iloc[bar_idx]
        o = df['open'].iloc[bar_idx]
        h = df['high'].iloc[bar_idx]
        l = df['low'].iloc[bar_idx]
        body = abs(c - o)
        range_ = h - l
        upper_wick = h - max(c, o)
        lower_wick = min(c, o) - l
        start = max(0, bar_idx - 19)
        avg_range = (df['high'].iloc[start:bar_idx+1] - df['low'].iloc[start:bar_idx+1]).mean()
        return (upper_wick > body * 2.5 and lower_wick < body * 0.3 and
                range_ > avg_range * 0.6 and c < o)
    
    def in_session(self, dt):
        if not self.session_filter:
            return True
        hour = dt.hour if hasattr(dt, 'hour') else datetime.fromisoformat(str(dt)).hour
        return (7 <= hour < 16) or (12 <= hour < 21)
    
    def can_trade(self, dt):
        day = dt.day if hasattr(dt, 'day') else datetime.fromisoformat(str(dt)).day
        if self.last_trade_day != day:
            self.trades_today = 0
            self.last_trade_day = day
        return self.trades_today < self.max_trades_per_day
    
    def check_entry(self, df, bar_idx):
        if bar_idx < 20:
            return None
        
        close = df['close'].iloc[bar_idx]
        atr = self.calculate_atr(df, bar_idx)
        
        if atr == 0:
            return None
        
        near_sup = self.near_support(close, atr)
        near_res = self.near_resistance(close, atr)
        
        risk_entry_long = (near_sup and self.bullish_structure and
                          self.in_corrective and not self.in_impulsive and
                          (self.bullish_engulfing(df, bar_idx) or self.bullish_pin_bar(df, bar_idx)))
        
        reduced_risk_long = False
        if len(self.swing_highs) >= 2:
            prev_sh = sorted(self.swing_highs, key=lambda x: x[0])[0][1]
            reduced_risk_long = (close > prev_sh and df['close'].iloc[bar_idx-1] <= prev_sh and
                                self.in_corrective)
        
        risk_entry_short = (near_res and self.bearish_structure and
                           self.in_corrective and not self.in_impulsive and
                           (self.bearish_engulfing(df, bar_idx) or self.bearish_pin_bar(df, bar_idx)))
        
        reduced_risk_short = False
        if len(self.swing_lows) >= 2:
            prev_sl = sorted(self.swing_lows, key=lambda x: x[0])[0][1]
            reduced_risk_short = (close < prev_sl and df['close'].iloc[bar_idx-1] >= prev_sl and
                                 self.in_corrective)
        
        if risk_entry_long or reduced_risk_long:
            return 'long'
        elif risk_entry_short or reduced_risk_short:
            return 'short'
        
        return None
    
    def manage_trade_intrabar(self, df, bar_idx):
        """Simulate intrabar SL/TP hit using H/L."""
        if self.current_trade is None:
            return
        
        trade = self.current_trade
        high = df['high'].iloc[bar_idx]
        low = df['low'].iloc[bar_idx]
        
        if trade.direction == 'long':
            # Check SL first (worst case)
            if low <= trade.sl:
                trade.exit_price = trade.sl
                trade.exit_time = df['time'].iloc[bar_idx]
                trade.exit_reason = 'SL'
                trade.pnl_r = -1.0
                self.trades.append(trade)
                self.current_trade = None
                return
            # Check TP
            if high >= trade.tp:
                trade.exit_price = trade.tp
                trade.exit_time = df['time'].iloc[bar_idx]
                trade.exit_reason = 'TP'
                trade.pnl_r = self.tp_ratio
                self.trades.append(trade)
                self.current_trade = None
                return
        else:  # short
            if high >= trade.sl:
                trade.exit_price = trade.sl
                trade.exit_time = df['time'].iloc[bar_idx]
                trade.exit_reason = 'SL'
                trade.pnl_r = -1.0
                self.trades.append(trade)
                self.current_trade = None
                return
            if low <= trade.tp:
                trade.exit_price = trade.tp
                trade.exit_time = df['time'].iloc[bar_idx]
                trade.exit_reason = 'TP'
                trade.pnl_r = self.tp_ratio
                self.trades.append(trade)
                self.current_trade = None
                return
        
        # Break-Even check (at end of bar)
        close = df['close'].iloc[bar_idx]
        risk = abs(trade.entry_price - trade.sl)
        if risk > 0 and not trade.be_moved:
            if trade.direction == 'long':
                move = close - trade.entry_price
            else:
                move = trade.entry_price - close
            
            if move >= risk * self.be_trigger_r:
                # Move SL to entry + small buffer
                buffer = risk * 0.05
                if trade.direction == 'long':
                    trade.sl = trade.entry_price + buffer
                else:
                    trade.sl = trade.entry_price - buffer
                trade.be_moved = True
    
    def run(self, df):
        self.trades = []
        self.current_trade = None
        self.trades_today = 0
        self.last_trade_day = None
        self.swing_highs = []
        self.swing_lows = []
        self.bullish_structure = False
        self.bearish_structure = False
        self.in_impulsive = False
        self.in_corrective = False
        self.consecutive_up_seq = 0
        self.consecutive_down_seq = 0
        self.resistance_level = 0.0
        self.support_level = 0.0
        self.correction_start = 0.0
        
        for i in range(len(df)):
            self.update_nature(df, i)
            self.update_structure(df, i)
            
            if self.current_trade:
                self.manage_trade_intrabar(df, i)
            
            if self.current_trade is None:
                dt = df['time'].iloc[i]
                if self.in_session(dt) and self.can_trade(dt):
                    signal = self.check_entry(df, i)
                    
                    if signal:
                        close = df['close'].iloc[i]
                        atr = self.calculate_atr(df, i)
                        
                        if signal == 'long':
                            sl = self.support_level - atr * self.sl_atr_multiplier if self.support_level > 0 else close - atr * 2.0
                            risk = close - sl
                            tp = close + risk * self.tp_ratio
                        else:
                            sl = self.resistance_level + atr * self.sl_atr_multiplier if self.resistance_level > 0 else close + atr * 2.0
                            risk = sl - close
                            tp = close - risk * self.tp_ratio
                        
                        self.current_trade = Trade(
                            direction=signal,
                            entry_price=close,
                            sl=sl,
                            tp=tp,
                            entry_time=dt,
                            risk=risk
                        )
                        self.trades_today += 1
        
        # Close remaining
        if self.current_trade:
            last_close = df['close'].iloc[-1]
            self.current_trade.exit_price = last_close
            self.current_trade.exit_time = df['time'].iloc[-1]
            self.current_trade.exit_reason = 'END'
            risk = self.current_trade.risk
            if self.current_trade.direction == 'long':
                self.current_trade.pnl_r = (last_close - self.current_trade.entry_price) / risk if risk > 0 else 0
            else:
                self.current_trade.pnl_r = (self.current_trade.entry_price - last_close) / risk if risk > 0 else 0
            self.trades.append(self.current_trade)
            self.current_trade = None
        
        return self.get_results()
    
    def get_results(self):
        if not self.trades:
            return {"error": "No trades"}
        
        total = len(self.trades)
        wins = [t for t in self.trades if t.pnl_r > 0]
        losses = [t for t in self.trades if t.pnl_r <= 0]
        
        win_rate = len(wins) / total * 100 if total > 0 else 0
        avg_win = sum(t.pnl_r for t in wins) / len(wins) if wins else 0
        avg_loss = sum(t.pnl_r for t in losses) / len(losses) if losses else 0
        gross_win = sum(t.pnl_r for t in wins)
        gross_loss = abs(sum(t.pnl_r for t in losses))
        pf = gross_win / gross_loss if gross_loss > 0 else float('inf')
        total_pnl = sum(t.pnl_r for t in self.trades)
        
        return {
            "total_trades": total,
            "wins": len(wins),
            "losses": len(losses),
            "win_rate": round(win_rate, 1),
            "avg_win_r": round(avg_win, 2),
            "avg_loss_r": round(avg_loss, 2),
            "profit_factor": round(pf, 2),
            "total_pnl_r": round(total_pnl, 2),
            "trades": self.trades
        }


def load_data(csv_path, symbol):
    df = pd.read_csv(csv_path)
    cols = {'time': 'time', symbol: 'open', f'H-{symbol}': 'high', f'L-{symbol}': 'low'}
    df = df[list(cols.keys())].rename(columns=cols).copy()
    # Close = next bar's open
    df['close'] = df['open'].shift(-1)
    df.loc[df.index[-1], 'close'] = df['open'].iloc[-1]
    df['time'] = pd.to_datetime(df['time'])
    return df


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--symbol', default='EURJPY')
    parser.add_argument('--data', default='data/TIMEFRAME_1H.csv')
    parser.add_argument('--swing', type=int, default=10)
    parser.add_argument('--tp-ratio', type=float, default=3.0)
    args = parser.parse_args()
    
    df = load_data(args.data, args.symbol)
    
    bt = FalconFXTickBacktester(
        swing_lookback=args.swing,
        tp_ratio=args.tp_ratio,
        sl_atr_multiplier=1.5,
        be_trigger_r=1.5
    )
    
    r = bt.run(df)
    
    print("══════════════════════════════════════════")
    print(f"  FALCONFX TICK BACKTESTER - {args.symbol}")
    print(f"  Swing LB: {args.swing} | TP: {args.tp_ratio}:1 | SL: 1.5x ATR")
    print("══════════════════════════════════════════")
    print(f"  Bars tested:   {len(df)}")
    print(f"  Date range:    {df['time'].iloc[0]} to {df['time'].iloc[-1]}")
    print()
    print(f"  Total Trades:  {r['total_trades']}")
    print(f"  Wins:          {r['wins']}")
    print(f"  Losses:        {r['losses']}")
    print(f"  Win Rate:      {r['win_rate']}%")
    print(f"  Avg Win (R):   {r['avg_win_r']}")
    print(f"  Avg Loss (R):  {r['avg_loss_r']}")
    print(f"  Profit Factor: {r['profit_factor']}")
    print(f"  Total P&L (R): {r['total_pnl_r']}")
    print("══════════════════════════════════════════")
    
    # Trade log
    if r['trades']:
        print()
        print("  Trade Log:")
        print(f"  {'#':>3} {'Dir':>4} {'Entry':>10} {'SL':>10} {'TP':>10} {'Exit':>10} {'P&L':>6} {'Reason':>5}")
        print("  " + "-" * 65)
        for i, t in enumerate(r['trades']):
            print(f"  {i+1:>3} {t.direction:>4} {t.entry_price:>10.5f} {t.sl:>10.5f} {t.tp:>10.5f} "
                  f"{(t.exit_price or 0):>10.5f} {t.pnl_r:>6.2f} {t.exit_reason or 'N/A':>5}")


if __name__ == '__main__':
    main()
