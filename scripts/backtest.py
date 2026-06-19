#!/usr/bin/env python3
"""
FalconFX Python Backtester
Replicates the MT5/Pine Script FalconFX logic in Python for rapid backtesting.
Uses the same Kaggle data (EURJPY, EURUSD, GBPUSD 1H).

This is a validation tool — the MT5 EA is the production target.
Once validated, deploy the same logic on MT5.

Usage:
   python backtest.py --symbol EURJPY --data data/TIMEFRAME_1H.csv
"""

import argparse
import sys
from dataclasses import dataclass
from datetime import datetime
from typing import List, Optional

import pandas as pd


# ═══════════════════════════════════════════════════════════════════════════
# DATA STRUCTURES
# ═══════════════════════════════════════════════════════════════════════════

@dataclass
class Trade:
    entry_time: datetime
    entry_price: float
    sl: float
    tp: float
    direction: str  # 'long' or 'short'
    exit_time: Optional[datetime] = None
    exit_price: Optional[float] = None
    exit_reason: Optional[str] = None
    pnl_r: float = 0.0  # P&L in R units
    scale_ins: int = 0


@dataclass
class SwingPoint:
    bar_index: int
    price: float
    is_high: bool


# ═══════════════════════════════════════════════════════════════════════════
# FALCONFX BACKTEST ENGINE
# ═══════════════════════════════════════════════════════════════════════════

class FalconFXBacktester:
    """
    Python implementation of FalconFX strategy.
    Matches the Pine Script and MQL5 logic exactly.
    """
    
    def __init__(self, swing_lookback=8, impulse_min_bars=3, atr_period=14,
                 risk_pct=1.0, max_trades_per_day=2, tp_ratio=3.0,
                 be_trigger_pct=1.0, use_half_risk=True, half_risk_hours=4,
                 use_scaling=False, max_scale_ins=2, session_filter=True):
        
        self.swing_lookback = swing_lookback
        self.impulse_min_bars = impulse_min_bars
        self.atr_period = atr_period
        self.risk_pct = risk_pct
        self.max_trades_per_day = max_trades_per_day
        self.tp_ratio = tp_ratio
        self.be_trigger_pct = be_trigger_pct
        self.use_half_risk = use_half_risk
        self.half_risk_hours = half_risk_hours
        self.use_scaling = use_scaling
        self.max_scale_ins = max_scale_ins
        self.session_filter = session_filter
        
        # State
        self.trades: List[Trade] = []
        self.current_trade: Optional[Trade] = None
        self.trades_today = 0
        self.last_trade_day = None
        self.day = None
        
        # Market structure state
        self.swing_highs: List[SwingPoint] = []
        self.swing_lows: List[SwingPoint] = []
        self.bullish_structure = False
        self.bearish_structure = False
        self.resistance_level = 0.0
        self.support_level = 0.0
        
        # Nature state
        self.in_impulsive = False
        self.in_corrective = False
        self.consecutive_up = 0
        self.consecutive_down = 0
        self.correction_start = 0.0
        
        # Tracking
        self.consecutive_up_seq = 0
        self.consecutive_down_seq = 0
    
    def calculate_atr(self, df: pd.DataFrame, period: int = 14) -> float:
        """Calculate ATR."""
        if len(df) < period + 1:
            return 0.0
        high = df['high'].iloc[-period-1:]
        low = df['low'].iloc[-period-1:]
        tr = high.values - low.values
        return float(tr[-period:].mean()) if len(tr) >= period else 0.0
    
    def detect_swing_points(self, df: pd.DataFrame, bar_idx: int) -> tuple:
        """Detect swing highs and lows (optimized)."""
        lb = self.swing_lookback
        if bar_idx < lb or bar_idx >= len(df) - lb:
            return False, False
        
        high = df['high'].iloc[bar_idx]
        low = df['low'].iloc[bar_idx]
        
        # Vectorized check
        slice_high = df['high'].iloc[bar_idx-lb:bar_idx+lb+1]
        slice_low = df['low'].iloc[bar_idx-lb:bar_idx+lb+1]
        
        is_high = high == slice_high.max()
        is_low = low == slice_low.min()
        
        return is_high, is_low
    
    def update_structure(self, df: pd.DataFrame, bar_idx: int):
        """Update market structure (swing points + HH/HL/LH/LL)."""
        is_high, is_low = self.detect_swing_points(df, bar_idx)
        
        if is_high:
            self.swing_highs.append(SwingPoint(bar_idx, df['high'].iloc[bar_idx], True))
            if len(self.swing_highs) > 10:
                self.swing_highs = self.swing_highs[-10:]
        
        if is_low:
            self.swing_lows.append(SwingPoint(bar_idx, df['low'].iloc[bar_idx], False))
            if len(self.swing_lows) > 10:
                self.swing_lows = self.swing_lows[-10:]
        
        # Determine structure
        if len(self.swing_highs) >= 2 and len(self.swing_lows) >= 2:
            sh = sorted(self.swing_highs, key=lambda x: x.bar_index)[-2:]
            sl = sorted(self.swing_lows, key=lambda x: x.bar_index)[-2:]
            
            self.bullish_structure = sh[-1].price > sh[-2].price and sl[-1].price > sl[-2].price
            self.bearish_structure = sh[-1].price < sh[-2].price and sl[-1].price < sl[-2].price
            
            # S/R levels
            self.resistance_level = sh[-1].price
            self.support_level = sl[-1].price
    
    def update_nature(self, df: pd.DataFrame, bar_idx: int):
        """Update Nature Theory state (impulsive vs corrective)."""
        if bar_idx == 0:
            return
        
        close = df['close'].iloc[bar_idx]
        open_ = df['open'].iloc[bar_idx]
        high = df['high'].iloc[bar_idx]
        low = df['low'].iloc[bar_idx]
        
        body_size = abs(close - open_)
        range_ = high - low
        
        # Average body and range
        start = max(0, bar_idx - 19)
        avg_body = abs(df['close'].iloc[start:bar_idx+1] - df['open'].iloc[start:bar_idx+1]).mean()
        avg_range = (df['high'].iloc[start:bar_idx+1] - df['low'].iloc[start:bar_idx+1]).mean()
        
        # Consecutive directional bars
        if close > open_:
            self.consecutive_up_seq += 1
            self.consecutive_down_seq = 0
        elif close < open_:
            self.consecutive_down_seq += 1
            self.consecutive_up_seq = 0
        else:
            self.consecutive_up_seq = 0
            self.consecutive_down_seq = 0
        
        # Impulse detection
        impulse_up = self.consecutive_up_seq >= self.impulse_min_bars and body_size > avg_body * 1.3
        impulse_down = self.consecutive_down_seq >= self.impulse_min_bars and body_size > avg_body * 1.3
        
        # Corrective detection
        is_corrective = (body_size < avg_body * 0.6 and range_ < avg_range * 0.7 and
                         abs(close - open_) < abs(high - low) * 0.4)
        
        # Phase transitions
        if impulse_up or impulse_down:
            self.in_impulsive = True
            self.in_corrective = False
            self.correction_start = close
        elif self.in_impulsive and is_corrective:
            self.in_impulsive = False
            self.in_corrective = True
    
    def near_resistance(self, price: float, atr: float) -> bool:
        return abs(price - self.resistance_level) < atr * 0.5
    
    def near_support(self, price: float, atr: float) -> bool:
        return abs(price - self.support_level) < atr * 0.5
    
    def bullish_engulfing(self, df: pd.DataFrame, bar_idx: int) -> bool:
        if bar_idx < 1:
            return False
        c = df['close'].iloc[bar_idx]
        o = df['open'].iloc[bar_idx]
        pc = df['close'].iloc[bar_idx - 1]
        po = df['open'].iloc[bar_idx - 1]
        body_now = abs(c - o)
        body_prev = abs(pc - po)
        return (c > o and pc < po and o <= pc and c >= po and body_now > body_prev * 1.2)
    
    def bearish_engulfing(self, df: pd.DataFrame, bar_idx: int) -> bool:
        if bar_idx < 1:
            return False
        c = df['close'].iloc[bar_idx]
        o = df['open'].iloc[bar_idx]
        pc = df['close'].iloc[bar_idx - 1]
        po = df['open'].iloc[bar_idx - 1]
        body_now = abs(c - o)
        body_prev = abs(pc - po)
        return (c < o and pc > po and o >= pc and c <= po and body_now > body_prev * 1.2)
    
    def bullish_pin_bar(self, df: pd.DataFrame, bar_idx: int) -> bool:
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
    
    def bearish_pin_bar(self, df: pd.DataFrame, bar_idx: int) -> bool:
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
    
    def in_session(self, dt: datetime) -> bool:
        """Check if time is in London or NY session."""
        if not self.session_filter:
            return True
        hour = dt.hour
        in_london = 7 <= hour < 16
        in_ny = 12 <= hour < 21
        return in_london or in_ny
    
    def can_trade(self, dt: datetime) -> bool:
        """Check daily trade limit."""
        if self.last_trade_day != dt.day:
            self.trades_today = 0
            self.last_trade_day = dt.day
        return self.trades_today < self.max_trades_per_day
    
    def check_entry(self, df: pd.DataFrame, bar_idx: int) -> Optional[str]:
        """Check for entry signal. Returns 'long', 'short', or None."""
        if bar_idx < 20:
            return None
        
        close = df['close'].iloc[bar_idx]
        atr = self.calculate_atr(df.iloc[:bar_idx+1])
        
        if atr == 0:
            return None
        
        # LONG signals
        near_sup = self.near_support(close, atr)
        near_res = self.near_resistance(close, atr)
        
        # Risk Entry: corrective at structure edge with confirmation
        risk_entry_long = (near_sup and self.bullish_structure and
                          self.in_corrective and not self.in_impulsive and
                          (self.bullish_engulfing(df, bar_idx) or self.bullish_pin_bar(df, bar_idx)))
        
        # Reduced Risk Entry: break above swing high
        if len(self.swing_highs) >= 2:
            prev_sh = sorted(self.swing_highs, key=lambda x: x.bar_index)[-2].price
            reduced_risk_long = (close > prev_sh and df['close'].iloc[bar_idx-1] <= prev_sh and
                                self.in_corrective)
        else:
            reduced_risk_long = False
        
        # SHORT signals
        risk_entry_short = (near_res and self.bearish_structure and
                           self.in_corrective and not self.in_impulsive and
                           (self.bearish_engulfing(df, bar_idx) or self.bearish_pin_bar(df, bar_idx)))
        
        if len(self.swing_lows) >= 2:
            prev_sl = sorted(self.swing_lows, key=lambda x: x.bar_index)[-2].price
            reduced_risk_short = (close < prev_sl and df['close'].iloc[bar_idx-1] >= prev_sl and
                                 self.in_corrective)
        else:
            reduced_risk_short = False
        
        if risk_entry_long or reduced_risk_long:
            return 'long'
        elif risk_entry_short or reduced_risk_short:
            return 'short'
        
        return None
    
    def manage_trade(self, df: pd.DataFrame, bar_idx: int):
        """Manage open trade (B/E, Half-Risk, TP)."""
        if self.current_trade is None:
            return
        
        trade = self.current_trade
        high = df['high'].iloc[bar_idx]
        low = df['low'].iloc[bar_idx]
        close = df['close'].iloc[bar_idx]
        
        # Check TP/SL hit
        if trade.direction == 'long':
            if low <= trade.sl:
                trade.exit_price = trade.sl
                trade.exit_time = df['time'].iloc[bar_idx]
                trade.exit_reason = 'SL'
                trade.pnl_r = -1.0
                self.trades.append(trade)
                self.current_trade = None
                return
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
        
        # Break-Even method
        risk = abs(trade.entry_price - trade.sl)
        if risk > 0:
            if trade.direction == 'long':
                move = close - trade.entry_price
            else:
                move = trade.entry_price - close
            
            be_trigger = trade.entry_price * (self.be_trigger_pct / 100)
            if move >= risk * 1.5:  # Move to BE only after 1.5R profit
                # Move SL to entry + buffer
                buffer = risk * 0.05
                if trade.direction == 'long':
                    trade.sl = trade.entry_price + buffer
                else:
                    trade.sl = trade.entry_price - buffer
    
    def run(self, df: pd.DataFrame) -> dict:
        """Run backtest on full dataframe."""
        
        # Reset state
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
        
        # Main loop
        for i in range(len(df)):
            # Update analysis
            self.update_nature(df, i)
            self.update_structure(df, i)
            
            # Manage existing trade
            if self.current_trade:
                self.manage_trade(df, i)
            
            # Check for new entry
            if self.current_trade is None:
                dt = df['time'].iloc[i] if 'time' in df.columns else datetime.now()
                if isinstance(dt, str):
                    dt = datetime.fromisoformat(dt)
                
                if self.in_session(dt) and self.can_trade(dt):
                    signal = self.check_entry(df, i)
                    
                    if signal:
                        close = df['close'].iloc[i]
                        atr = self.calculate_atr(df.iloc[:i+1])
                        
                        if signal == 'long':
                            # SL below structure with wider ATR buffer (1.5x ATR)
                            sl = self.support_level - atr * 1.5 if self.support_level > 0 else close - atr * 2.0
                            risk = close - sl
                            tp = close + risk * self.tp_ratio
                        else:
                            sl = self.resistance_level + atr * 1.5 if self.resistance_level > 0 else close + atr * 2.0
                            risk = sl - close
                            tp = close - risk * self.tp_ratio
                        
                        self.current_trade = Trade(
                            entry_time=dt,
                            entry_price=close,
                            sl=sl,
                            tp=tp,
                            direction=signal
                        )
                        self.trades_today += 1
        
        # Close any remaining trade
        if self.current_trade:
            last_close = df['close'].iloc[-1]
            self.current_trade.exit_price = last_close
            self.current_trade.exit_time = df['time'].iloc[-1] if 'time' in df.columns else datetime.now()
            self.current_trade.exit_reason = 'END_OF_DATA'
            if self.current_trade.direction == 'long':
                risk = self.current_trade.entry_price - self.current_trade.sl
                self.current_trade.pnl_r = (last_close - self.current_trade.entry_price) / risk if risk > 0 else 0
            else:
                risk = self.current_trade.sl - self.current_trade.entry_price
                self.current_trade.pnl_r = (self.current_trade.entry_price - last_close) / risk if risk > 0 else 0
            self.trades.append(self.current_trade)
            self.current_trade = None
        
        return self.get_results()
    
    def get_results(self) -> dict:
        """Calculate backtest statistics."""
        if not self.trades:
            return {"error": "No trades executed"}
        
        total_trades = len(self.trades)
        wins = [t for t in self.trades if t.pnl_r > 0]
        losses = [t for t in self.trades if t.pnl_r <= 0]
        
        win_rate = len(wins) / total_trades * 100 if total_trades > 0 else 0
        avg_win = sum(t.pnl_r for t in wins) / len(wins) if wins else 0
        avg_loss = sum(t.pnl_r for t in losses) / len(losses) if losses else 0
        profit_factor = sum(t.pnl_r for t in wins) / abs(sum(t.pnl_r for t in losses)) if losses and sum(t.pnl_r for t in losses) != 0 else float('inf')
        
        total_pnl_r = sum(t.pnl_r for t in self.trades)
        
        return {
            "total_trades": total_trades,
            "wins": len(wins),
            "losses": len(losses),
            "win_rate": round(win_rate, 1),
            "avg_win_r": round(avg_win, 2),
            "avg_loss_r": round(avg_loss, 2),
            "profit_factor": round(profit_factor, 2),
            "total_pnl_r": round(total_pnl_r, 2),
            "trades": self.trades
        }


# ═══════════════════════════════════════════════════════════════════════════
# DATA LOADER
# ═══════════════════════════════════════════════════════════════════════════

def load_kaggle_data(csv_path: str, symbol: str) -> pd.DataFrame:
    """Load Kaggle forex CSV and normalize columns."""
    df = pd.read_csv(csv_path)
    
    # Select columns for the symbol
    cols = {
        'time': 'time',
        symbol: 'open',
        f'H-{symbol}': 'high',
        f'L-{symbol}': 'low',
    }
    df = df[list(cols.keys())].rename(columns=cols).copy()
    
    # Close = next bar's open (current bar's symbol column = open price)
    df['close'] = df['open'].shift(-1)
    df.loc[df.index[-1], 'close'] = df['open'].iloc[-1]
    
    # Parse time
    df['time'] = pd.to_datetime(df['time'])
    
    return df


# ═══════════════════════════════════════════════════════════════════════════
# MAIN
# ═══════════════════════════════════════════════════════════════════════════

def main():
    parser = argparse.ArgumentParser(description='FalconFX Python Backtester')
    parser.add_argument('--symbol', type=str, default='EURJPY')
    parser.add_argument('--data', type=str, default='data/TIMEFRAME_1H.csv')
    parser.add_argument('--swing-lookback', type=int, default=8)
    parser.add_argument('--tp-ratio', type=float, default=3.0)
    args = parser.parse_args()
    
    print("══════════════════════════════════════════")
    print("  FalconFX Python Backtester")
    print("══════════════════════════════════════════")
    print(f"  Symbol: {args.symbol}")
    print(f"  Data: {args.data}")
    print(f"  Swing Lookback: {args.swing_lookback}")
    print(f"  TP Ratio: {args.tp_ratio}")
    print("══════════════════════════════════════════")
    print()
    
    # Load data
    df = load_kaggle_data(args.data, args.symbol)
    print(f"Loaded {len(df)} bars")
    print(f"Date range: {df['time'].iloc[0]} to {df['time'].iloc[-1]}")
    print()
    
    # Run backtest
    bt = FalconFXBacktester(
        swing_lookback=args.swing_lookback,
        tp_ratio=args.tp_ratio
    )
    
    results = bt.run(df)
    
    # Print results
    print("══════════════════════════════════════════")
    print("  BACKTEST RESULTS")
    print("══════════════════════════════════════════")
    print(f"  Total Trades:    {results['total_trades']}")
    print(f"  Wins:            {results['wins']}")
    print(f"  Losses:          {results['losses']}")
    print(f"  Win Rate:        {results['win_rate']}%")
    print(f"  Avg Win (R):     {results['avg_win_r']}")
    print(f"  Avg Loss (R):    {results['avg_loss_r']}")
    print(f"  Profit Factor:   {results['profit_factor']}")
    print(f"  Total P&L (R):   {results['total_pnl_r']}")
    print("══════════════════════════════════════════")
    
    # Handbook benchmark comparison
    print()
    print("  Handbook Benchmark (P28-30):")
    print("    Expected Strike Rate: ~81% (EUR/JPY)")
    print("    Expected Avg RR: ~3:1")
    print("    Continuation/Reversal: 73%/27%")
    
    # Print trade log
    if results['trades']:
        print()
        print("  Trade Log (last 10):")
        print(f"  {'#':>3} {'Dir':>5} {'Entry':>12} {'Exit':>12} {'P&L(R)':>8} {'Reason':>6}")
        print("  " + "-" * 50)
        for i, t in enumerate(results['trades'][-10:]):
            entry_str = f"{t.entry_price:.5f}"
            exit_str = f"{t.exit_price:.5f}" if t.exit_price else "N/A"
            print(f"  {i+1:>3} {t.direction:>5} {entry_str:>12} {exit_str:>12} {t.pnl_r:>8.2f} {t.exit_reason or 'N/A':>6}")


if __name__ == '__main__':
    main()
