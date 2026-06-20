# FalconFX — 30-Day Paper Trading Checklist

## Pre-Trade Setup (Day 0)
- [ ] Paste `falconfx_bot.pine` into TradingView Pine Editor
- [ ] Verify Pine Script v5 compilation (no errors)
- [ ] Add to EURUSD 1H chart
- [ ] Set inputs: Swing=10, SL Buffer=1.5, Risk=1%, Max Trades=2
- [ ] Enable session filter (London + NY)
- [ ] Set up alerts (Long Entry + Short Entry)
- [ ] Open TradingView paper trading panel

## Daily Checklist (Each Trading Day)
- [ ] Check chart at London open (07:00 UTC)
- [ ] Confirm structure: HH+HL (bullish) or LH+LL (bearish)?
- [ ] Wait for bot signal (triangle on chart)
- [ ] Log signal details:
  - Pair: ___________
  - Time: ___________
  - Type: [ ] Risk Entry  [ ] Reduced Risk Entry
  - Direction: [ ] Long  [ ] Short
  - Entry price: ___________
  - SL: ___________
  - TP: ___________
  - Pattern: [ ] Engulfing  [ ] Pin Bar  [ ] Inside Bar  [ ] Flag
- [ ] Enter trade in paper account
- [ ] Set alert for B/E move (+1%)
- [ ] End of day: Did you exceed 2 trades? [ ] Yes [ ] No

## Weekly Review (Every Friday)
- [ ] Export TradingView Strategy Tester results
- [ ] Count total trades this week: ___
- [ ] Win rate this week: ___%
- [ ] Average R:R achieved: ___
- [ ] Best pair this week: ___________
- [ ] Worst pair this week: ___________
- [ ] Did you follow 2-trade/day rule? [ ] Yes [ ] No
- [ ] Notes for next week: _________________________________

## 30-Day Summary (Day 30)
- [ ] Total trades: ___
- [ ] Overall win rate: ___%
- [ ] Total R-multiple: __R
- [ ] Best trade: +___R (pair: ___)
- [ ] Worst trade: -___R (pair: ___)
- [ ] Max drawdown: __%
- [ ] Profit factor: ___
- [ ] Compare to backtest: [ ] Better  [ ] Similar  [ ] Worse
- [ ] Decision: [ ] Go live  [ ] More paper trading  [ ] Adjust parameters

---

## Quick Parameter Tuning Guide

| Problem | Adjustment |
|---------|------------|
| Too many losses | Increase SL Buffer to 2.0 ATR |
| Missed opportunities | Increase Entry Distance to 0.8 ATR |
| TP not hitting | Decrease TP Ratio to 2.0 |
| Overtrading | Set Max Trades = 1 |
| No signals | Disable session filter, check swing lookback (try 8) |
| Choppy/ranging pairs | Add structure filter: only trade if outer range > 2x ATR |

---

## Contact & Resources
- GitHub: https://github.com/bytebridge035-wq/falconfx_ai_bot
- FalconFX Handbook (2017) by Mark Hutchinson
- TVMCP MCP Server: configured in Hermes (for Binance crypto backtests)
