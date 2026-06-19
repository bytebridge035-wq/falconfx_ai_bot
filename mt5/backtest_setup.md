# MT5 Backtest Setup Guide

## Prerequisites

1. **MetaTrader 5** installed (download from your broker or metaquotes.com)
2. **MetaEditor** (comes with MT5) for compiling the EA
3. **Python 3.8+** (for data download script)

## Step 1: Install MT5

### On the Onsite VM (Linux/Wine):
```bash
# Download MT5 from official site
wget https://download.metaquotes.com/trade/MetaTrader5-64.exe

# Install via Wine
wine MetaTrader5-64.exe
```

### On Windows:
Just run the installer from your broker.

## Step 2: Install Python Dependencies

```bash
pip install yfinance pandas
```

## Step 3: Download Historical Data

### Option A: Kaggle (Recommended — free, no API key needed)
```bash
# Downloads from anthonygocmen/multi-timeframe-fx-dataset-29-major-pairs
# Covers: EURUSD, GBPUSD, EURJPY, USDJPY, AUDUSD, and 24 more pairs
# Timeframes: 5M, 15M, 1H

python scripts/kaggle_data.py --symbol EURJPY --timeframe 1H
python scripts/kaggle_data.py --symbol EURUSD --timeframe 1H
python scripts/kaggle_data.py --symbol GBPUSD --timeframe 1H
python scripts/kaggle_data.py --symbol USDJPY --timeframe 1H
```

### Option B: Yahoo Finance (more years available)
```bash
python scripts/download_data.py --symbol EURJPY --years 5 --timeframe 1H
python scripts/download_data.py --symbol EURUSD --years 5 --timeframe 1H
python scripts/download_data.py --symbol GBPUSD --years 5 --timeframe 1H
python scripts/download_data.py --symbol XAUUSD --years 5 --timeframe 1H
```

## Step 4: Compile the EA

1. Open MetaEditor (F4 in MT5, or launch separately)
2. Open `mt5/FalconFX.mq5`
3. Click **Compile** (F7) or Build → Compile
4. Ensure 0 errors
5. The compiled `.ex5` file will be in `MQL5/Experts/`

## Step 5: Configure MT5 for Backtesting

1. In MT5: Tools → Options → Expert Advisors
   - ✅ Allow automated trading
   - ✅ Allow DLL imports (if using custom indicators)

2. Open Strategy Tester: View → Strategy Tester (or Ctrl+R)

3. Configure:
   - **Expert Advisor:** FalconFX
   - **Symbol:** EURUSD (or your pair)
   - **Period:** 1H (recommended)
   - **Date Range:** Select at least 1 year
   - **Model:** Every tick (most accurate)
   - **Spread:** Use current spread or custom (check your broker)
   - **Initial Deposit:** 10000 (default)
   - **Leverage:** 1:100 (or your broker's default)

4. Click **Start** to run backtest

## Step 6: Interpret Results

### Key Metrics to Check (Handbook Benchmarks):

| Metric | Handbook Reference | Target |
|--------|-------------------|--------|
| Win Rate | P28-30: 81% on EUR/JPY | > 70% |
| Profit Factor | — | > 1.5 |
| Avg Win/Loss | P28-30: 3:1 RR | > 2.5:1 |
| Max Drawdown | — | < 15% |
| Total Trades | — | > 50 for statistical significance |

### What to Look For:
- **Strike Rate ≥ 70%**: Strategy is working as expected
- **Profit Factor > 1.5**: Edge is present
- **Max DD < 15%**: Risk management is effective
- **Smooth equity curve**: No wild swings

## Step 7: Optimize (Optional)

In Strategy Tester:
1. ✅ Enable "Optimization"
2. Select parameters to optimize:
   - InpSwingLookback: 5-15 (step 1)
   - InpTPRatio: 2.0-4.0 (step 0.5)
   - InpRiskPercent: 0.5-1.5 (step 0.1)
3. Run optimization (takes longer)

## Step 8: Forward Test on TradingView

After successful backtest:
1. Apply the Pine Script bot to TradingView
2. Set same timeframe and pair
3. Run on paper trading for 30 days
4. Compare signals between MT5 and TradingView
5. If aligned → proceed to live demo

## Troubleshooting

| Issue | Solution |
|-------|----------|
| "Zero divide" error | Check symbol digits match your broker |
| No trades generated | Increase date range or reduce swing lookback |
| Too many trades | Check InpMaxTradesPerDay is set to 2 |
| Compilation error in MetaEditor | Ensure all .mqh files are in MQL5/Include/ |
| Data gaps in backtest | Re-download data with download_data.py |

## File Structure

```
mt5/
├── FalconFX.mq5              # Main Expert Advisor
├── FalconFX_Utils.mqh        # Nature Theory, Structure, Patterns
├── FalconFX_Management.mqh   # B/E, Half-Risk, Scaling
├── README.md                 # MT5-specific docs
└── backtest_setup.md         # This file

scripts/
└── download_data.py         # Historical data downloader
```
