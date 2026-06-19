# FalconFX MT5 Bot — Documentation

## Overview

MT5 Expert Advisor implementing the complete FalconFX methodology by Mark Hutchinson. Built from the FalconFX Strategy Handbook (2017).

## Files

| File | Purpose |
|------|---------|
| `FalconFX.mq5` | Main Expert Advisor — entry logic, signal generation |
| `FalconFX_Utils.mqh` | Utility functions — Nature Theory, structure, patterns |
| `FalconFX_Management.mqh` | Trade management — B/E, Half-Risk, Scaling In |
| `backtest_setup.md` | Step-by-step backtest guide |
| `../scripts/download_data.py` | Download historical data for MT5 |

## Handbook Alignment

| Component | Handbook | Implementation |
|-----------|----------|----------------|
| Nature Theory (P7-9) | Impulsive vs Corrective | `FalconFX_UpdateNature()` |
| Structure (P10-12) | Breathing cycle, HH/HL | `FalconFX_UpdateStructure()` |
| Risk Entry (P14) | Within pattern before break | `FalconFX_IsRiskEntryLong/Short()` |
| Reduced Risk Entry (P15) | On break confirmation | `FalconFX_IsReducedRiskEntryLong/Short()` |
| B/E Method (P16-20) | Move SL to entry after impulse | `FalconFX_ApplyBreakEven()` |
| Half-Risk (P21) | Move SL to -0.5% on corrective | `FalconFX_ApplyHalfRisk()` |
| 90% Rule (P22) | Watch correction start | `FalconFX_Apply90PercentRule()` |
| Scaling In (P24-27) | Add on continuation | `FalconFX_TryScaleIn()` |
| Risk Cap (P4-5) | 1% max per trade | `FalconFX_CalculateLotSize()` |
| Daily Limit (P3-5) | Max 2 trades/day | `FalconFX_CanTrade()` |

## Installation

See `backtest_setup.md` for complete instructions.

## Recommended Pairs (from handbook backtests)

1. **EUR/JPY** — 81% strike rate, 3:1 RR (Mark's best)
2. **EUR/USD** — High liquidity, clean structure
3. **GBP/USD** — Good volatility for impulse detection
4. **EUR/GBP** — Tighter ranges, good for pattern detection

## Parameters

| Parameter | Default | Description |
|-----------|---------|-------------|
| InpSwingLookback | 8 | Bars for swing detection |
| InpStructureLookback | 50 | Bars for outer structure |
| InpImpulseMinBars | 3 | Min consecutive bars for impulse |
| InpRiskPercent | 1.0 | Risk per trade (Falcon mandate) |
| InpMaxTradesPerDay | 2 | Daily trade limit |
| InpTPRatio | 3.0 | Take profit R:R |
| InpBETrigger | 1.0 | Break-even trigger % |
| InpEnableScalingIn | false | Enable scaling (advanced) |

## Disclaimer

Based on publicly documented FalconFX methodology. Past performance does not guarantee future results. Always backtest and demo trade before live deployment.
