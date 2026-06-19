# FalconFX Trading Bot v3.0 — [Handbook Edition]

Built directly from **The FalconFX Strategy Handbook (2017)** by Mark Hutchinson.
Every component maps to a specific chapter/page in the handbook.

---

## 📖 Handbook Alignment Index

| Pine Script Section | Handbook Reference | What It Implements |
|---|---|---|
| Section 4: Nature Theory | P7-9 | Impulsive vs Corrective phase detection |
| Section 5: Structure | P10-12 | Breathing cycle (1-2-3 Impulse-Correction-Impulse), Top-Down framework |
| Section 6: S/R Zones | P12 | Structure edges where price approaches |
| Section 7: Candlesticks | P8, Falcon Quick Tips | Engulfing, Pin Bars, Inside Bars, Multi-Touch |
| Section 8: 90% Rule | P22 | "90% of impulsive moves reach correction start" |
| Section 9: Patterns Within Patterns | Falcon Quick Tips Ep2 | Flag continuation, corrective at structure edge |
| Section 10: Entry Types | P13-15 | **Risk Entry** + **Reduced Risk Entry** |
| Section 13: B/E Method | P16-20 | Move SL to entry when price impulses away |
| Section 13: Half-Risk Method | P21 | Move SL to -0.5% when price corrects instead of impulses |
| Section 13: Scaling In | P24-27 | Add positions on continuation patterns |
| Section 3: Daily Limit | P3-5 | Max 2 trades/day (prevents FOMO, revenge trading) |
| Section 15: Info Table | P31-33 | Daily goals tracking |

---

## 🎯 Strategy Logic (Handbook-Accurate)

### Entry Conditions

**Long (Bullish Setup):**
1. Price at/near support (swing low / structure edge)
2. Bullish structure confirmed (Higher Highs + Higher Lows)
3. Corrective nature detected (not impulsive — P8: "nature of approach matters")
4. Confirmation candle: bullish engulfing OR bullish pin bar
5. Session filter (London or NY)
6. Daily trade limit not exceeded

**Short (Bearish Setup):**
1. Price at/near resistance (swing high / structure edge)
2. Bearish structure confirmed (Lower Highs + Lower Lows)
3. Corrective nature detected
4. Confirmation candle: bearish engulfing OR bearish pin bar
5. Session filter + daily limit

### Entry Types (P13-15)

| Type | When | Risk | R:R | Strike Rate |
|---|---|---|---|---|
| Risk Entry | Within corrective pattern before break | Higher | Higher (smaller stop) | Lower |
| Reduced Risk Entry | On close outside pattern (confirmed) | Lower | Slightly less | Higher |

### Trade Management (P16-21)

1. **Break-Even Method**: Move SL to entry+spread when price moves 1% into profit or reaches recent H/L
2. **Half-Risk Method**: Move SL to -0.5% when price shows corrective behavior (no impulse)
3. **90% Rule**: Watch for reversal at correction start point; lock in profit if reversal forms
4. **Scaling In** (advanced): Add on next continuation correction after initial position at BE

---

## ⚙️ Recommended Settings

From handbook backtesting (P28-30):
- **Strike Rate**: ~81% average across pairs
- **Best RR**: 3:1 average on winners
- **Continuation vs Reversal**: 73% continuations, 27% reversals
- **Risk Entry vs Reduced Risk**: 16% risk entries, 84% reduced risk entries
- **Best pairs**: EUR/JPY, EUR/USD, GBP/USD (backtest your own pairs!)

### Timeframe
- **Structure analysis**: 1H-4H (swing detection)
- **Entry execution**: 1H
- **Recommended swing lookback**: 8 bars

---

## 🚀 Installation

1. Open TradingView → Pine Editor
2. Paste `falconfx_bot.pine`
3. Set timeframe to 1H
4. Add to chart
5. Set up alerts for automated notifications

---

## ⚠️ Risk Notes from Handbook

- **1% max risk per trade** — non-negotiable (P4-5)
- **Max 2 trades per day** — prevents overtrading (P3-5)
- **Losses are "expenses"** — the price of doing business (P5)
- **No revenge trading** — stick to the plan (P4)
- **Backtest first** — create a profile for each pair (P28-30)

---

## 📁 Files

- `falconfx_bot.pine` — The complete Pine Script v5 strategy
- `README.md` — This file
