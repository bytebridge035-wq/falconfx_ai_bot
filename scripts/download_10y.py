#!/usr/bin/env python3
"""
FalconFX — Download 10 years of 1H data from Yahoo Finance
Converts to MT5 .hst format for backtesting
"""

import yfinance as yf
import os
import struct
import sys
from datetime import datetime

# Target pairs (Yahoo Finance tickers)
PAIRS = {
    "EURUSD=X": "EURUSD",
    "GBPUSD=X": "GBPUSD",
    "USDJPY=X": "USDJPY",
    "EURJPY=X": "EURJPY",
    "XAUUSD=X": "XAUUSD",
}

OUTPUT_DIR = os.path.expanduser("~/falconfx-bot/data")
START_DATE = "2015-01-01"
END_DATE = "2025-06-01"

def download_pair(ticker, name):
    """Download 1H data from Yahoo Finance"""
    print(f"  Downloading {name} ({ticker})...")
    try:
        df = yf.download(ticker, start=START_DATE, end=END_DATE, interval="1h", progress=False)
        if df is None or len(df) == 0:
            print(f"    ⚠ No data for {name}")
            return None
        # Flatten multi-level columns if present
        if isinstance(df.columns, type(df.columns).__class__):
            df.columns = [c[0] if isinstance(c, tuple) else c for c in df.columns]
        print(f"    ✓ {len(df)} bars from {df.index[0]} to {df.index[-1]}")
        return df
    except Exception as e:
        print(f"    ✗ Error: {e}")
        return None

def write_hst(filename, df):
    """Write MT5 .hst file (format: =IddddIIII)"""
    # MT5 .hst header: version(4) + header_size(4) + ...
    # Simplified format compatible with MT5
    with open(filename, 'wb') as f:
        # Header: 6 int32 values
        version = 401
        bars_count = len(df)
        header = struct.pack('<6i', version, 0, 0, 0, bars_count, 0)
        f.write(header)
        
        # Each bar: time(8) + open(8) + high(8) + low(8) + close(8) + tick_volume(8) + spread(4) + real_volume(8)
        # Total: 60 bytes per bar (MT5 format)
        for idx, row in df.iterrows():
            ts = int(idx.timestamp())
            o = float(row['Open'])
            h = float(row['High'])
            l = float(row['Low'])
            c = float(row['Close'])
            v = int(row.get('Volume', 0))
            bar = struct.pack('<qddddqqId', ts, o, h, l, c, v, 0, 0, 0)
            f.write(bar)
    
    size_mb = os.path.getsize(filename) / (1024 * 1024)
    print(f"    ✓ Written {filename} ({bars_count} bars, {size_mb:.1f} MB)")

def main():
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    
    print("=" * 60)
    print("FalconFX — 1H Historical Data Downloader")
    print(f"Period: {START_DATE} → {END_DATE}")
    print(f"Pairs: {', '.join(PAIRS.values())}")
    print("=" * 60)
    
    results = {}
    for ticker, name in PAIRS.items():
        df = download_pair(ticker, name)
        if df is not None and len(df) > 0:
            filename = os.path.join(OUTPUT_DIR, f"{name}60.hst")
            write_hst(filename, df)
            results[name] = len(df)
        else:
            # Try alternative ticker format
            alt_ticker = ticker.replace("=X", "=X")
            print(f"  Trying alternative...")
            df = download_pair(alt_ticker, name)
            if df is not None and len(df) > 0:
                filename = os.path.join(OUTPUT_DIR, f"{name}60.hst")
                write_hst(filename, df)
                results[name] = len(df)
    
    print("\n" + "=" * 60)
    print("SUMMARY")
    print("=" * 60)
    for name, count in results.items():
        print(f"  {name}: {count} bars")
    print(f"\nData saved to: {OUTPUT_DIR}")
    return results

if __name__ == "__main__":
    main()
