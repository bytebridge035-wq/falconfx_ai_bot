# FalconFX Bot — Paper Trading Quick Start Guide

## What You Need
1. **TradingView account** (free tier works for manual testing)
2. **This Pine Script file**: `falconfx_bot.pine`
3. **A forex broker account** (OANDA, FXCM, Pepperstone, etc.) — or use TradingView's paper trading

---

## Step-by-Step Setup (5 minutes)

### Step 1: Open TradingView
Go to https://www.tradingview.com and log in.

### Step 2: Open Pine Editor
- Open any chart (e.g., EURUSD on 1H timeframe)
- Click the **Pine Editor** tab at the bottom of the screen

### Step 3: Paste the Code
- Delete any existing code in the editor
- Copy the entire contents of `falconfx_bot.pine` and paste it
- Click **"Add to Chart"** (or Ctrl+Enter)

### Step 4: Verify Settings
The strategy dialog will open. Confirm these inputs:

| Setting | Value | Why |
|---------|-------|-----|
| Swing Lookback | 10 | Optimized for 1H forex |
| SL Buffer (x ATR) | 1.5 | Prevents noise stop-outs |
| Entry Max Distance | 0.5x ATR | Only enter near structure |
| Risk Per Trade | 1% | Falcon handbook mandate |
| Max Trades/Day | 2 | Psychology discipline |
| TP Ratio | 3:1 | Falcon backtest average |
| Session Filter | ON (London + NY) | Best liquidity |

### Step 5: Add Alerts
- Right-click on the chart → **"Add Alert"**
- Condition: `FalconFX Long Entry` or `FalconFX Short Entry`
- Set notification method (pop-up, email, webhook)
- Expiration: "Open-ended"

---

## Recommended Pairs & Timeframes

| Pair | Timeframe | Why |
|------|-----------|-----|
| **EURUSD** | 1H | Most liquid, cleanest structure |
| **GBPUSD** | 1H | Strong impulses, good for Falcon |
| **EURJPY** | 1H | Volatile, clear swing structure |
| **USDJPY** | 1H | Trend-friendly, good B/E candidates |

Start with **EURUSD 1H** — it's the most forgiving for learning the strategy.

---

## How to Read the Bot's Signals

### Visual Cues on Chart:
- **Green background** = Bullish structure (HH + HL)
- **Red background** = Bearish structure (LH + LL)
- **Blue overlay** = Impulsive phase active
- **Yellow overlay** = Corrective phase active
- **Triangle labels** = Entry signals:
  - 🟢 "RISK LONG" / "REDUCED LONG" = Buy
  - 🔴 "RISK SHORT" / "REDUCED SHORT" = Sell

### Info Table (top-right):
- Structure: HH+HL ▲ or LH+LL ▼
- Nature: IMPULSIVE or CORRECTIVE
- Trades Today: X/2
- Session: ACTIVE or WAIT
- Near Res/Sup: YES/no

---

## Trade Management (Automated by the Bot)

1. **Entry**: Bot enters at structure edge (swing point ± 0.5 ATR)
2. **Stop Loss**: Placed 1.5x ATR beyond structure
3. **Take Profit**: 3:1 risk-reward ratio
4. **Break-Even**: SL moves to entry when price moves 1% into profit
5. **90% Rule**: Bot watches for reversals at correction start level
6. **Half-Risk**: If price doesn't impulse, SL tightens to -0.5%

---

## Paper Trading Routine (Falcon Method)

### Daily Routine (~30 minutes):
1. **Morning (London open ~07:00 UTC)**: Check 1H chart for structure
2. **Wait for signal**: Bot alerts when entry triggers
3. **Confirm**: Check that structure aligns (HH+HL for longs, LH+LL for shorts)
4. **Execute**: Enter in your broker platform (or TradingView paper trade)
5. **Log**: Note entry price, SL, TP, and pattern type
6. **Max 2 trades/day**: If both hit, stop trading that day

### Weekly Review:
- Export trade log from TradingView Strategy Tester
- Compare to Python backtest expectations (78% WR, 3:1 RR average)
- Note any pairs that underperform
- Check if you're following the 2-trade/day discipline

---

## Expected Performance (from 20-year backtest)

| Metric | Python Backtest (Kaggle) | TVMCP (Binance) |
|--------|-------------------------|-----------------|
| Win Rate | 78.1% | 7.9% (crypto) |
| Total Trades | 651 | 38 |
| Profit Factor | 2.87 | 0.32 |
| Net Profit | +1,395R | -16.9% |

**Note**: The Python backtest on forex data is the reliable benchmark. TVMCP uses Binance crypto which behaves differently.

---

## Troubleshooting

| Issue | Fix |
|-------|-----|
| "Compilation error" in Pine | Make sure you're using Pine Script v5 (line 1: `//@version=5`) |
| No signals appearing | Check session filter — bot only trades London/NY hours |
| Too many signals | Reduce `Max Trades Per Day` to 1 |
| Stopped out too often | Increase `SL Buffer` to 2.0 ATR |
| No TP hits | Decrease `TP Ratio` to 2.0 for easier targets |

---

## Next Steps After Paper Trading

1. **30-day paper trade log** → compare actual WR to backtest
2. **Refine parameters** if live results diverge significantly
3. **Scale up** to real capital only after 30+ trades show consistent results
4. **Add more pairs** once you're comfortable with the execution

---

## Files in This Repo

| File | Purpose |
|------|---------|
| `falconfx_bot.pine` | TradingView Pine Script strategy (paste this) |
| `PAPER_TRADING_GUIDE.md` | This file |
| `scripts/backtest.py` | Python backtester (for offline optimization) |
| `mt5/FalconFX.mq5` | MT5 EA (for Windows MT5 users) |
| `UNIFIED_RECAP.md` | Full backtest results report |
