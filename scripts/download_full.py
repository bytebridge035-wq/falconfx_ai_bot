#!/usr/bin/env python3
"""
FalconFX — Download maximum available 1H data from Yahoo Finance
Downloads last 730 days of 1H data for all pairs + XAUUSD via GC=F
Saves as CSV for Python backtester and MT5 .hst format
"""

import yfinance as yf
import os
import struct
import sys
from datetime import datetime

# Yahoo Finance tickers
PAIRS = {
    "EURUSD=X": "EURUSD",
    "GBPUSD=X": "GBPUSD",
    "USDJPY=X": "USDJPY",
    "EURJPY=X": "EURJPY",
    "GC=F": "XAUUSD",  # Gold futures as XAUUSD proxy
}

OUTPUT_DIR = os.path.expanduser("~/falconfx-bot/data")
HST_DIR = os.path.expanduser("~/falconfx-bot/data/mt5")

def download_all():
    """Download 1H data for all pairs (max 730 days)"""
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    os.makedirs(HST_DIR, exist_ok=True)
    
    print("=" * 60)
    print("FalconFX — Historical Data Download")
    print("Source: Yahoo Finance (max 730 days of 1H data)")
    print("=" * 60)
    
    results = {}
    
    for ticker, name in PAIRS.items():
        print(f"\n[{name}] Downloading {ticker}...")
        try:
            df = yf.download(ticker, period='730d', interval='1h', progress=False)
            if df is None or len(df) == 0:
                print(f"  ✗ No data")
                continue
            
            # Flatten multi-level columns
            if hasattr(df.columns, 'levels'):
                df.columns = [c[0] for c in df.columns]
            
            # Drop any NaN rows
            df = df.dropna()
            
            # Save to CSV
            csv_path = os.path.join(OUTPUT_DIR, f"{name}60.csv")
            df.to_csv(csv_path)
            
            # Save to MT5 .hst format
            hst_path = os.path.join(HST_DIR, f"{name}60.hst")
            write_hst(hst_path, df)
            
            days = (df.index[-1] - df.index[0]).days
            print(f"  ✓ {len(df)} bars ({days} days)")
            print(f"    {df.index[0]} → {df.index[-1]}")
            print(f"    CSV: {csv_path}")
            print(f"    HST: {hst_path}")
            
            results[name] = {'bars': len(df), 'days': days, 'file': csv_path}
            
        except Exception as e:
            print(f"  ✗ Error: {e}")
    
    # Summary
    print("\n" + "=" * 60)
    print("SUMMARY")
    print("=" * 60)
    total_bars = 0
    for name, info in results.items():
        print(f"  {name}: {info['bars']} bars ({info['days']} days)")
        total_bars += info['bars']
    print(f"\n  Total: {total_bars} bars across {len(results)} pairs")
    print(f"  CSV dir: {OUTPUT_DIR}")
    print(f"  HST dir: {HST_DIR}")
    
    return results

def write_hst(filename, df):
    """Write MT5 .hst file (format 401)"""
    with open(filename, 'wb') as f:
        # MT5 .hst header
        # signature = 'COPYRIGHT' (ignored by MT5 for backtesting)
        # Format: version(4) + header_size(60) + ...
        header = struct.pack('<4s60s', b'COPYRIGHT', b'\x00' * 60)
        f.write(header)
        
        # Each bar: time(8) + open(8) + high(8) + low(8) + close(8) + 
        #            tick_volume(8) + spread(4) + real_volume(8)
        for idx, row in df.iterrows():
            ts = int(idx.timestamp())
            o = float(row['Open'])
            h = float(row['High'])
            l = float(row['Low'])
            c = float(row['Close'])
            v = int(row.get('Volume', 0))
            bar = struct.pack('<qddddqqId', ts, o, h, l, c, v, 0, 0, 0)
            f.write(bar)

if __name__ == "__main__":
    download_all()
