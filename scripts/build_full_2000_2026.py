"""
Fetch ČNB historical EUR/CZK daily rates (2000-2016) and merge with existing
high-resolution H4 data (2017-2026) to create a comprehensive 2000-2026 dataset.
"""

import csv
import ssl
import time
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

DATA_DIR = Path("fxdata")
EXISTING_H4_FILE = DATA_DIR / "eurczk-h4-bid-2017-01-02-2026-10-15.csv"
OUTPUT_FILE = DATA_DIR / "eurczk-h4-bid-2000-01-03-2026-10-15.csv"


def fetch_cnb_year(year: int):
    """Fetch daily EUR/CZK rates for a given year from official Czech National Bank archive."""
    url = f"https://www.cnb.cz/cs/financni-trhy/devizovy-trh/kurzy-devizoveho-trhu/kurzy-devizoveho-trhu/rok.txt?rok={year}"
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0 (compatible; BlunitFX/1.0)"})
    ctx = ssl._create_unverified_context()
    
    with urllib.request.urlopen(req, context=ctx) as resp:
        text = resp.read().decode("utf-8").strip()

    lines = [line.strip() for line in text.split("\n") if line.strip()]
    if not lines:
        return []

    eur_idx = None
    records = []

    for line in lines:
        parts = [p.strip() for p in line.split("|")]
        if not parts:
            continue
        # Header line (can appear multiple times per file when currency basket changes)
        if parts[0] == "Datum":
            try:
                eur_idx = next(i for i, col in enumerate(parts) if "EUR" in col)
            except StopIteration:
                eur_idx = None
            continue

        if eur_idx is None or len(parts) <= eur_idx:
            continue

        date_str = parts[0]
        eur_str = parts[eur_idx].replace(",", ".")
        if not eur_str:
            continue
        try:
            rate = float(eur_str)
            # Basic sanity check for EUR/CZK
            if 15.0 <= rate <= 45.0:
                dt = datetime.strptime(date_str, "%d.%m.%Y").replace(tzinfo=timezone.utc)
                records.append((dt, rate))
        except (ValueError, TypeError):
            continue

    # Sort ascending by date
    records.sort(key=lambda x: x[0])
    return records


def build_full_dataset():
    DATA_DIR.mkdir(exist_ok=True)
    all_candles = []
    seen_ts = set()

    # 1. Fetch 2000-2016 from ČNB
    print("Fetching 2000-2016 daily rates from ČNB...")
    cnb_rates = []
    for yr in range(2000, 2017):
        print(f"  Downloading ČNB year {yr}...")
        yr_rates = fetch_cnb_year(yr)
        print(f"    Loaded {len(yr_rates)} trading days.")
        cnb_rates.extend(yr_rates)
        time.sleep(0.2)

    # 2. Expand ČNB daily rates into 6 H4 candles per day
    # Offsets in seconds: 00:00, 04:00, 08:00, 12:00, 16:00, 20:00
    h4_offsets = [0, 14400, 28800, 43200, 57600, 72000]

    for i, (dt, rate) in enumerate(cnb_rates):
        prev_rate = cnb_rates[i - 1][1] if i > 0 else rate
        next_rate = cnb_rates[i + 1][1] if i < len(cnb_rates) - 1 else rate

        day_open = (prev_rate + rate) / 2.0
        day_close = (rate + next_rate) / 2.0
        day_high = max(day_open, day_close, rate * 1.002)
        day_low = min(day_open, day_close, rate * 0.998)

        steps = [
            (day_open, max(day_open, day_low), min(day_open, day_low), round(day_open + (day_high - day_open) * 0.3, 4)),
            (round(day_open + (day_high - day_open) * 0.3, 4), day_high, min(day_open, day_low), round(day_open + (day_high - day_open) * 0.7, 4)),
            (round(day_open + (day_high - day_open) * 0.7, 4), day_high, day_low, round(day_high - (day_high - day_low) * 0.4, 4)),
            (round(day_high - (day_high - day_low) * 0.4, 4), day_high, day_low, round(day_low + (day_close - day_low) * 0.5, 4)),
            (round(day_low + (day_close - day_low) * 0.5, 4), max(day_close, day_low), day_low, round(day_low + (day_close - day_low) * 0.8, 4)),
            (round(day_low + (day_close - day_low) * 0.8, 4), max(day_close, day_high), min(day_close, day_low), day_close),
        ]

        day_base_ts = int(dt.timestamp())
        for offset, (o, h, l, c) in zip(h4_offsets, steps):
            ts_ms = (day_base_ts + offset) * 1000
            ts_str = str(ts_ms)
            if ts_str not in seen_ts:
                seen_ts.add(ts_str)
                all_candles.append([ts_str, f"{o:.4f}", f"{h:.4f}", f"{l:.4f}", f"{c:.4f}"])

    print(f"Generated {len(all_candles)} H4 candles from ČNB (2000-2016).")

    # 3. Load 2017-2026 from existing file
    if EXISTING_H4_FILE.exists():
        print(f"Merging with existing high-res H4 data from {EXISTING_H4_FILE}...")
        with open(EXISTING_H4_FILE, "r", encoding="utf-8") as f:
            reader = csv.reader(f)
            header = next(reader, None)
            for row in reader:
                if row and row[0] not in seen_ts:
                    seen_ts.add(row[0])
                    all_candles.append(row)

    # 4. Sort and write out
    all_candles.sort(key=lambda r: float(r[0]))
    print(f"Total merged candles: {len(all_candles)}")

    for dest in [OUTPUT_FILE]:
        with open(dest, "w", encoding="utf-8", newline="") as f:
            writer = csv.writer(f)
            writer.writerow(["timestamp", "open", "high", "low", "close"])
            writer.writerows(all_candles)
        print(f"Saved dataset to {dest} ({dest.stat().st_size} bytes)")


if __name__ == "__main__":
    build_full_dataset()
