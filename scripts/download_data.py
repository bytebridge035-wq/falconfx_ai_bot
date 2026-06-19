#!/usr/bin/env python3
"""
FalconFX MT5 — Historical Data Downloader
Downloads OHLCV data from Yahoo Finance and converts to MT5 .hst format
for backtesting in the MT5 Strategy Tester.

Usage:
   python download_data.py --symbol EURUSD --years 5 --timeframe 1H
   python download_data.py --symbol EURJPY --years 3 --timeframe D1

Requirements: pip install yfinance pandas
"""

import argparse
import struct
import sys
from datetime import datetime, timedelta
from pathlib import Path

try:
    import yfinance as yf
    import pandas as pd
except ImportError:
    print("ERROR: Required packages not found.")
    print("Install with: pip install yfinance pandas")
    sys.exit(1)


def yfinance_to_mt5_hst(df: pd.DataFrame, output_path: str, symbol: str, timeframe: int):
    """
    Convert yfinance OHLCV DataFrame to MT5 .hst binary format.
    
    MT5 .hst format:
    - Header: 148 bytes
      - version: int32 (4 bytes)
      - copyright: char[64]
      - symbol: char[12]
      - period: int32 (timeframe in minutes)
      - digits: int32
      - timesign: int32 (datetime of first bar)
      - last_sync: int32
      - unused: 52 bytes
    - Bars: 44 bytes each
      - time: int32 (Unix timestamp)
      - open: float64
      - high: float64
      - low: float64
      - close: float64
      - tick_volume: int32
      - spread: int32
      - real_volume: int32
    """
    
    # Determine digits based on symbol
    if 'JPY' in symbol.upper():
        digits = 3
    else:
        digits = 5
    
    # Map timeframe string to MT5 period in minutes
    tf_map = {
        '1H': 60, '60': 60,
        '4H': 240, '240': 240,
        'D1': 1440, '1440': 1440, '1D': 1440,
        'W1': 10080, '1W': 10080,
        'M1': 43200, '1M': 43200,
        '15': 15, '15M': 15,
        '30': 30, '30M': 30,
        '5': 5, '5M': 5,
        '1': 1, '1m': 1,
    }
    
    period = tf_map.get(str(timeframe), 60)
    
    # Write header
    header_format = '<I64s12sIIIII52s'
    header_size = struct.calcsize(header_format)
    
    with open(output_path, 'wb') as f:
        # Write header
        header = struct.pack(
            header_format,
            400,                          # version
            b'FalconFX Bot',              # copyright
            symbol.encode('ascii')[:12],  # symbol
            period,                       # timeframe
            digits,                       # digits
            int(df.index[0].timestamp()),    # timesign
            int(df.index[-1].timestamp()),# last_sync
            *([0] * 13)                   # unused
        )
        f.write(header)
        
        # Write bars
        bar_format = '<IffffIIII'
        for idx, row in df.iterrows():
            timestamp = int(idx.timestamp())
            bar = struct.pack(
                bar_format,
                timestamp,
                float(row['Open']),
                float(row['High']),
                float(row['Low']),
                float(row['Close']),
                int(row['Volume']),
                0,     # spread
                0      # real_volume
            )
            f.write(bar)
    
    print(f"Written {len(df)} bars to {output_path}")
    print(f"  Symbol: {symbol}, Period: {period}min, Digits: {digits}")


def download_and_convert(symbol: str, years: int, timeframe: str, output_dir: str = None):
    """Download data from Yahoo Finance and convert to MT5 format."""
    
    # Map common forex symbols to yfinance format
    yf_symbol_map = {
        'EURUSD': 'EURUSD=X',
        'GBPUSD': 'GBPUSD=X',
        'USDJPY': 'USDJPY=X',
        'AUDUSD': 'AUDUSD=X',
        'USDCAD': 'USDCAD=X',
        'USDCHF': 'USDCHF=X',
        'NZDUSD': 'NZDUSD=X',
        'EURJPY': 'EURJPY=X',
        'GBPJPY': 'GBPJPY=X',
        'EURGBP': 'EURGBP=X',
        'XAUUSD': 'GC=F',      # Gold
        'XAGUSD': 'SI=F',      # Silver
    }
    
    yf_symbol = yf_symbol_map.get(symbol.upper(), f"{symbol}=X")
    
    # Calculate date range
    end_date = datetime.now()
    start_date = end_date - timedelta(days=years * 365)
    
    print(f"Downloading {symbol} ({yf_symbol})...")
    print(f"  Timeframe: {timeframe}")
    print(f"  Period: {start_date.strftime('%Y-%m-%d')} to {end_date.strftime('%Y-%m-%d')}")
    
    # Download from Yahoo Finance
    df = yf.download(yf_symbol, start=start_date, end=end_date, interval=timeframe.lower(), progress=True)
    
    if df.empty:
        print(f"ERROR: No data downloaded for {symbol}")
        return None
    
    # Flatten multi-level columns if present
    if isinstance(df.columns, pd.MultiIndex):
        df.columns = df.columns.get_level_values(0)
    
    # Ensure correct column names
    df = df[['Open', 'High', 'Low', 'Close', 'Volume']].copy()
    df.dropna(inplace=True)
    
    print(f"  Downloaded {len(df)} bars")
    
    # Determine output path
    if output_dir is None:
        output_dir = Path.home() / '.hermes' / 'metatrader5' / 'Tester' / 'history'
    
    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)
    
    mt5_filename = f"{symbol}{timeframe}.hst"
    output_file = output_path / mt5_filename
    
    # Convert to MT5 format
    yfinance_to_mt5_hst(df, str(output_file), symbol, timeframe)
    
    print(f"  Output: {output_file}")
    print(f"  ✓ Ready for MT5 backtesting!")
    
    return str(output_file)


def main():
    parser = argparse.ArgumentParser(description='Download historical data for MT5 backtesting')
    parser.add_argument('--symbol', type=str, default='EURUSD', help='Symbol (e.g., EURUSD, GBPJPY)')
    parser.add_argument('--years', type=int, default=5, help='Years of data to download')
    parser.add_argument('--timeframe', type=str, default='1H', help='Timeframe (15M, 30M, 1H, 4H, D1)')
    parser.add_argument('--output-dir', type=str, default=None, help='Output directory for .hst file')
    
    args = parser.parse_args()
    
    print("══════════════════════════════════════════")
    print("  FalconFX MT5 — Data Downloader")
    print("══════════════════════════════════════════")
    print()
    
    result = download_and_convert(args.symbol, args.years, args.timeframe, args.output_dir)
    
    if result:
        print(f"\nDone! File: {result}")
    else:
        print("\nFailed to download data.")
        sys.exit(1)


if __name__ == '__main__':
    main()
