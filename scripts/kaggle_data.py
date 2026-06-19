#!/usr/bin/env python3
"""
FalconFX MT5 — Kaggle Data Converter
Downloads forex data from Kaggle (anthonygocmen/multi-timeframe-fx-dataset-29-major-pairs)
and converts to MT5 .hst format for Strategy Tester.

Usage:
   python download_data.py                     # Download from Kaggle + convert
   python kaggle_data.py --symbol EURJPY        # Convert only (if data already downloaded)

Requirements: pip install kaggle pandas (kaggle already set up with token)
"""

import argparse
import struct
import sys
from datetime import datetime
from pathlib import Path

import pandas as pd

# Kaggle dataset info
KAGGLE_DATASET = "anthonygocmen/multi-timeframe-fx-dataset-29-major-pairs"
DATA_DIR = Path(__file__).parent.parent / "data"

# Map our symbol names to CSV column prefixes
SYMBOL_MAP = {
    "EURUSD": {"H": "H-EURUSD", "L": "L-EURUSD"},
    "GBPUSD": {"H": "H-GBPUSD", "L": "L-GBPUSD"},
    "USDJPY": {"H": "H-USDJPY", "L": "L-USDJPY"},
    "EURJPY": {"H": "H-EURJPY", "L": "L-EURJPY"},
    "AUDUSD": {"H": "H-AUDUSD", "L": "L-AUDUSD"},
}


def download_kaggle_data():
    """Download and unzip the Kaggle dataset."""
    from kaggle.api.kaggle_api_extended import KaggleApi

    print("Downloading from Kaggle: ", KAGGLE_DATASET)
    api = KaggleApi()
    api.authenticate()
    api.dataset_download_files(KAGGLE_DATASET, path=str(DATA_DIR), unzip=True)
    print("Download complete!")
    print("Files:", list(DATA_DIR.glob("*.csv")))


def csv_to_mt5_hst(csv_path: str, symbol: str, output_dir: str = None, period_minutes: int = 60):
    """
    Convert CSV OHLCV to MT5 .hst binary format.
    
    Parameters:
        csv_path: Path to CSV file
        symbol: Symbol name (EURUSD, EURJPY, etc.)
        output_dir: Where to write .hst file (default: MT5 Tester history folder)
        period_minutes: Timeframe in minutes (60 = 1H)
    """
    
    if symbol not in SYMBOL_MAP:
        print(f"ERROR: {symbol} not in SYMBOL_MAP. Available: {list(SYMBOL_MAP.keys())}")
        return None
    
    print(f"Converting {symbol} from {csv_path}...")
    
    df = pd.read_csv(csv_path)
    
    cols = SYMBOL_MAP[symbol]
    h_col = cols["H"]
    l_col = cols["L"]
    
    if h_col not in df.columns or l_col not in df.columns:
        print(f"ERROR: Columns {h_col} or {l_col} not found in CSV")
        print(f"Available columns: {list(df.columns)[:10]}...")
        return None
    
    time_col = "time" if "time" in df.columns else df.columns[0]
    
    # Parse times
    df[time_col] = pd.to_datetime(df[time_col])
    df = df.sort_values(time_col).reset_index(drop=True)
    
    # Determine digits
    if "JPY" in symbol:
        digits = 3
    else:
        digits = 5
    
    # Prepare output path
    if output_dir is None:
        # Default MT5 history directory
        home = Path.home()
        # Try common MT5 data locations
        possible_dirs = [
            home / ".metaquote" / "Terminal" / "D0D3C5E3F3F11111112" / "history" / "MQL5",
            home / ".hermes" / "metatrader5" / "history",
            home / "AppData" / "Roaming" / "MetaQuotes" / "Terminal" / "history",
        ]
        output_dir = possible_dirs[0]
        for d in possible_dirs:
            if d.exists():
                output_dir = d
                break
    
    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)
    output_file = output_path / f"{symbol}{period_minutes}.hst"
    
    # Write MT5 .hst format
    # Header: 148 bytes = version(4) + copyright(64) + symbol(12) + period(4) + digits(4) + timesign(4) + last_sync(4) + unused(52)
    header_format = '<I64s12sIIII52s'
    
    with open(output_file, 'wb') as f:
        first_ts = int(df[time_col].iloc[0].timestamp())
        last_ts = int(df[time_col].iloc[-1].timestamp())
        
        header = struct.pack(
            header_format,
            400,                          # version
            b'FalconFX Bot',              # copyright (64 bytes)
            symbol.encode('ascii')[:12],  # symbol (12 bytes)
            period_minutes,               # period
            digits,                       # digits
            first_ts,                     # timesign
            last_ts,                      # last_sync
            b'\x00' * 52                  # unused
        )
        f.write(header)
        
        # Bars: 48 bytes each = time(4) + open(8) + high(8) + low(8) + close(8) + tick_volume(4) + spread(4) + real_volume(4)
        bar_format = '=IddddIII'
        bars_written = 0
        
        for idx, row in df.iterrows():
            timestamp = int(row[time_col].timestamp())
            
            high = float(row[h_col])
            low = float(row[l_col])
            
            # CSV format: column "SYMBOL" = Open price, Close = next bar's Open
            open_col = symbol
            v_col = f"V-{symbol}"
            
            open_price = float(row[open_col])
            volume = int(row.get(v_col, 0)) if v_col in df.columns else 0
            
            # Close = next bar's open (or current open for last bar)
            if idx < len(df) - 1:
                close_price = float(df[open_col].iloc[idx + 1])
            else:
                close_price = open_price
            
            bar = struct.pack(
                bar_format,
                timestamp,
                open_price,
                high,
                low,
                close_price,
                volume,
                0,   # spread
                0    # real_volume
            )
            f.write(bar)
            bars_written += 1
    
    print(f"Written {bars_written} bars to {output_file}")
    print(f"  Symbol: {symbol}, Period: {period_minutes}min, Digits: {digits}")
    print(f"  Date range: {df[time_col].iloc[0]} to {df[time_col].iloc[-1]}")
    print(f"  File size: {output_file.stat().st_size} bytes")
    
    return str(output_file)


def main():
    parser = argparse.ArgumentParser(description='Download forex data from Kaggle and convert to MT5 .hst')
    parser.add_argument('--download', action='store_true', help='Download from Kaggle first')
    parser.add_argument('--symbol', type=str, default='EURJPY', help='Symbol to convert')
    parser.add_argument('--timeframe', type=str, default='1H', help='Timeframe (5M, 15M, 1H)')
    parser.add_argument('--output-dir', type=str, default=None, help='Output directory')
    
    args = parser.parse_args()
    
    print("══════════════════════════════════════════")
    print("  FalconFX MT5 — Kaggle Data Converter")
    print("══════════════════════════════════════════")
    print()
    
    if args.download or not DATA_DIR.exists():
        download_kaggle_data()
    
    # Map timeframe to CSV file and period minutes
    tf_map = {
        '5M': ('TIMEFRAME_5M.csv', 5),
        '15M': ('TIMEFRAME_15M.csv', 15),
        '1H': ('TIMEFRAME_1H.csv', 60),
    }
    
    if args.timeframe not in tf_map:
        print(f"ERROR: Unknown timeframe {args.timeframe}. Use: {list(tf_map.keys())}")
        sys.exit(1)
    
    csv_file, period_minutes = tf_map[args.timeframe]
    csv_path = DATA_DIR / csv_file
    
    if not csv_path.exists():
        print(f"ERROR: {csv_path} not found. Run with --download flag first.")
        sys.exit(1)
    
    result = csv_to_mt5_hst(str(csv_path), args.symbol, args.output_dir, period_minutes)
    
    if result:
        print(f"\nDone! File: {result}")
    else:
        print("\nConversion failed.")
        sys.exit(1)


if __name__ == '__main__':
    main()
