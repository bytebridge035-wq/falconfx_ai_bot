#!/usr/bin/env python3
"""
FalconFX — Kaggle Data Processor
- Resamples 15m → 1H for EURUSD, EURJPY, USDJPY (2000-2020)
- Uses GBPUSD H1 directly (1993-2025)
- Uses USDJPY H1 directly (2010-2020)
- Outputs unified CSVs for backtesting
"""

import os
import csv
from datetime import datetime
from collections import defaultdict

KAGGLE_DIR = os.path.expanduser("~/falconfx-bot/data/kaggle")
OUTPUT_DIR = os.path.expanduser("~/falconfx-bot/data/unified")

def parse_15m_datetime(s):
    """Parse '2000.01.03 00:00:00' format"""
    try:
        return datetime.strptime(s.strip(), '%Y.%m.%d %H:%M:%S')
    except ValueError:
        return None

def parse_gbpusd_datetime(date_str, time_str):
    """Parse '1993.05.12' + '00:00' format"""
    try:
        d = date_str.strip().replace('.', '-')
        t = time_str.strip()
        return datetime.strptime(f"{d} {t}", '%Y-%m-%d %H:%M')
    except ValueError:
        return None

def resample_15m_to_1h(csv_path, pair_name):
    """Resample 15-minute OHLCV to 1-hour"""
    hourly_bars = {}
    
    with open(csv_path, 'r') as f:
        reader = csv.DictReader(f)
        for row in reader:
            dt = parse_15m_datetime(row['DATE_TIME'])
            if dt is None:
                continue
            
            # Round to hour
            hour_key = dt.replace(minute=0, second=0)
            
            o = float(row['OPEN'])
            h = float(row['HIGH'])
            l = float(row['LOW'])
            c = float(row['CLOSE'])
            
            if o <= 0 or h <= 0 or l <= 0 or c <= 0:
                continue
            
            if hour_key not in hourly_bars:
                hourly_bars[hour_key] = {
                    'open': o, 'high': h, 'low': l, 
                    'close': c, 'count': 1
                }
            else:
                bar = hourly_bars[hour_key]
                bar['high'] = max(bar['high'], h)
                bar['low'] = min(bar['low'], l)
                bar['close'] = c
                bar['count'] += 1
    
    # Sort by time
    sorted_keys = sorted(hourly_bars.keys())
    bars = []
    for k in sorted_keys:
        b = hourly_bars[k]
        bars.append({
            'timestamp': k,
            'open': b['open'],
            'high': b['high'],
            'low': b['low'],
            'close': b['close'],
        })
    
    print(f"  {pair_name}: {len(bars)} 1H bars from {bars[0]['timestamp']} to {bars[-1]['timestamp']}")
    return bars

def load_gbpusd_h1(csv_path):
    """Load GBPUSD H1 data (1993+)"""
    bars = []
    with open(csv_path, 'r') as f:
        reader = csv.DictReader(f)
        for row in reader:
            dt = parse_gbpusd_datetime(row['Date'], row['Time'])
            if dt is None:
                continue
            
            o = float(row['Open'])
            h = float(row['High'])
            l = float(row['Low'])
            c = float(row['Close'])
            
            if o <= 0 or h <= 0 or l <= 0 or c <= 0:
                continue
            
            bars.append({
                'timestamp': dt,
                'open': o,
                'high': h,
                'low': l,
                'close': c,
            })
    
    bars.sort(key=lambda x: x['timestamp'])
    print(f"  GBPUSD: {len(bars)} 1H bars from {bars[0]['timestamp']} to {bars[-1]['timestamp']}")
    return bars

def load_usdjpy_h1(csv_path):
    """Load USDJPY H1 data (tab-separated, MT4/5 format)"""
    bars = []
    with open(csv_path, 'r', encoding='utf-8-sig') as f:
        reader = csv.DictReader(f, delimiter='\t')
        for row in reader:
            date_str = row.get('<DATE>', '').strip()
            time_str = row.get('<TIME>', '').strip()
            
            try:
                dt = datetime.strptime(f"{date_str} {time_str}", '%Y.%m.%d %H:%M:%S')
            except ValueError:
                continue
            
            o = float(row.get('<OPEN>', '0'))
            h = float(row.get('<HIGH>', '0'))
            l = float(row.get('<LOW>', '0'))
            c = float(row.get('<CLOSE>', '0'))
            
            if o <= 0 or h <= 0 or l <= 0 or c <= 0:
                continue
            
            bars.append({
                'timestamp': dt,
                'open': o,
                'high': h,
                'low': l,
                'close': c,
            })
    
    bars.sort(key=lambda x: x['timestamp'])
    if bars:
        print(f"  USDJPY: {len(bars)} 1H bars from {bars[0]['timestamp']} to {bars[-1]['timestamp']}")
    else:
        print(f"  USDJPY: No bars parsed!")
    return bars

def save_csv(bars, filepath):
    """Save bars to CSV"""
    with open(filepath, 'w', newline='') as f:
        writer = csv.writer(f)
        writer.writerow(['timestamp', 'open', 'high', 'low', 'close'])
        for b in bars:
            writer.writerow([
                b['timestamp'].strftime('%Y-%m-%d %H:%M:%S'),
                b['open'], b['high'], b['low'], b['close']
            ])
    size_kb = os.path.getsize(filepath) / 1024
    print(f"    → {filepath} ({size_kb:.0f} KB)")

def main():
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    
    print("=" * 60)
    print("FalconFX — Kaggle Data Processor")
    print("=" * 60)
    
    # 1. EURUSD: resample 15m → 1H (2000-2020)
    print("\n[EURUSD] Resampling 15m → 1H...")
    eurusd_bars = resample_15m_to_1h(
        os.path.join(KAGGLE_DIR, 'top_pairs', 'EURUSD-2000-2020-15m.csv'),
        'EURUSD'
    )
    save_csv(eurusd_bars, os.path.join(OUTPUT_DIR, 'EURUSD60.csv'))
    
    # 2. EURJPY: resample 15m → 1H (2000-2020)
    print("\n[EURJPY] Resampling 15m → 1H...")
    eurjpy_bars = resample_15m_to_1h(
        os.path.join(KAGGLE_DIR, 'top_pairs', 'EURJPY-2000-2020-15m.csv'),
        'EURJPY'
    )
    save_csv(eurjpy_bars, os.path.join(OUTPUT_DIR, 'EURJPY60.csv'))
    
    # 3. USDJPY: use H1 data (2010-2020)
    print("\n[USDJPY] Loading H1 data...")
    usdjpy_bars = load_usdjpy_h1(
        os.path.join(KAGGLE_DIR, 'usdjpy', 'USDJPY_H1_201001040000_202012311800.csv')
    )
    save_csv(usdjpy_bars, os.path.join(OUTPUT_DIR, 'USDJPY60.csv'))
    
    # 4. GBPUSD: use H1 data (1993+) — filter to 2000+ for consistency
    print("\n[GBPUSD] Loading H1 data...")
    gbpusd_bars = load_gbpusd_h1(
        os.path.join(KAGGLE_DIR, 'gbpusd', 'GBPUSD', 'GBPUSD_PERIOD_H1.csv')
    )
    # Filter to 2000-01-01 onwards
    gbpusd_filtered = [b for b in gbpusd_bars if b['timestamp'] >= datetime(2000, 1, 1)]
    print(f"  Filtered to 2000+: {len(gbpusd_filtered)} bars")
    save_csv(gbpusd_filtered, os.path.join(OUTPUT_DIR, 'GBPUSD60.csv'))
    
    # 5. XAUUSD: no Kaggle data available, use Yahoo Finance (2 years)
    # Will handle separately
    
    # Summary
    print("\n" + "=" * 60)
    print("SUMMARY")
    print("=" * 60)
    for f in os.listdir(OUTPUT_DIR):
        if f.endswith('.csv'):
            path = os.path.join(OUTPUT_DIR, f)
            with open(path) as csvf:
                lines = sum(1 for _ in csvf) - 1  # minus header
            print(f"  {f}: {lines} bars")
    
    print(f"\nOutput dir: {OUTPUT_DIR}")

if __name__ == "__main__":
    main()
