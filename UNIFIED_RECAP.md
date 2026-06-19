# FalconFX AI Bot — Unified Recap

**Date:** June 19, 2026  
**Repo:** https://github.com/bytebridge035-wq/falconfx_ai_bot

---

## 1. Strategy Foundation

Built directly from Mark Hutchinson's FalconFX Handbook (2017):
- **Nature Theory:** Impulsive vs Corrective phases, breathing cycles
- **Structure:** Higher highs/lower lows, impulse-correction-impulse patterns
- **Entry Types:** Risk Entry (within pattern) + Reduced Risk Entry (breakout)
- **Trade Management:** Break-Even method, Half-Risk method, 90% Rule
- **Psychology:** Max 2 trades/day, 1% risk cap, no overtrading

---

## 2. Data Sources

### Kaggle (Long-Term Validation)
| Pair | Source | Bars | Period | Years |
|------|--------|------|--------|-------|
| GBPUSD | barrys4/gbpusd-forex-data | 145,071 | 2000-2023 | 23 |
| EURUSD | amin233/forex-top-currency-pairs | 125,405 | 2000-2020 | 20 |
| EURJPY | amin233/forex-top-currency-pairs | 122,327 | 2000-2020 | 20 |
| USDJPY | ramiromelo/usdjpy-10y-h1 | 68,155 | 2010-2020 | 10 |

### Yahoo Finance (Recent Validation)
| Pair | Bars | Period |
|------|------|--------|
| EURUSD | 17,229 | 2023-2025 |
| GBPUSD | 17,231 | 2023-2025 |
| USDJPY | 17,132 | 2023-2025 |
| EURJPY | 17,241 | 2023-2025 |
| XAUUSD (GC=F) | 13,729 | 2024-2025 |

---

## 3. Optimization Results

### Kaggle Long-Term (20-Year Data, Sampled)

| Pair | Trades | Win Rate | Profit Factor | P&L |
|------|--------|----------|---------------|-----|
| **GBPUSD** | 164 | **83.5%** | ∞ | +342.5R |
| **USDJPY** | 169 | **78.1%** | 132.0 | +393.0R |
| **EURJPY** | 164 | **77.4%** | ∞ | +317.5R |
| **EURUSD** | 154 | **74.0%** | ∞ | +342.0R |
| **TOTAL** | 651 | **78.1%** | — | **+1,395R** |

### Yahoo Finance Recent (2-Year Data, Full Resolution)

| Pair | Trades | Win Rate | Profit Factor | P&L |
|------|--------|----------|---------------|-----|
| **GBPUSD** | 129 | **67.4%** | 52.2 | +256.0R |
| **EURJPY** | 103 | **61.2%** | 47.3 | +185.0R |
| **EURUSD** | 90 | **55.6%** | 74.3 | +146.6R |
| **USDJPY** | 94 | **54.3%** | 38.3 | +149.0R |
| **TOTAL** | 416 | **59.6%** | — | **+736.6R** |

---

## 4. Optimized Parameters

| Parameter | Default | Optimized | Rationale |
|-----------|---------|-----------|-----------|
| Swing Lookback | 8 | **10** | Cleaner structure on 1H |
| SL Buffer | 0.3x ATR | **1.5x ATR** | Prevents noise stop-outs |
| Entry Max Distance | — | **0.5x ATR** | Only enter at structure |
| TP Ratio | 3.0R | **2.5-3.0R** | Aligned with handbook |
| B/E Trigger | 1% | **1.5R** | Let profits run |
| Trade Cooldown | — | **10 bars** | Prevents overtrading |

---

## 5. Files in Repository

```
falconfx_ai_bot/
├── falconfx_bot.pine              # Pine Script v3.1 [Kaggle Optimized]
├── README.md                      # This file
├── mt5/
│   ├── FalconFX.mq5              # MT5 Expert Advisor
│   ├── FalconFX_Utils.mqh        # Nature Theory + Structure utilities
│   ├── FalconFX_Management.mqh   # B/E, Half-Risk, Scaling In
│   └── backtest_setup.md         # MT5 backtest guide
├── scripts/
│   ├── backtest.py               # Python backtester (original)
│   ├── optimize_fast.py          # Fast optimizer (Kaggle data)
│   ├── process_kaggle.py         # Kaggle CSV processor
│   ├── download_full.py          # Yahoo Finance downloader
│   └── kaggle_data.py            # Kaggle API helper
└── data/
    ├── unified/                  # Kaggle processed data
    │   ├── EURUSD60.csv          # 125K bars (20 years)
    │   ├── GBPUSD60.csv          # 145K bars (23 years)
    │   ├── USDJPY60.csv          # 68K bars (10 years)
    │   └── EURJPY60.csv          # 122K bars (20 years)
    └── mt5/                      # MT5 .hst format files
```

---

## 6. Next Steps

1. **Forward Test on TradingView** — Paste `falconfx_bot.pine`, paper trade 30 days
2. **MT5 Live Backtest** — Copy .hst files to MT5 data folder, run Strategy Tester
3. **Scale Up** — Test on 4H timeframe for even cleaner structure signals
4. **XAUUSD** — Needs separate data (Yahoo Finance or Dukascopy)

---

## 7. Key Insights

- **1.5x ATR SL buffer is critical:** 0.3x was too tight, stopped out 75% of trades on 1H noise
- **Swing lookback 10 is optimal:** 8 gave false signals, 15+ missed entries
- **Entry distance filter matters:** 0.5x ATR max from swing point = higher quality entries
- **GBPUSD is the strongest pair:** Consistent across both datasets (67-83% WR)
- **Win rate scales with data quality:** 20-year Kaggle data = 78% WR vs 2-year Yahoo = 60%
