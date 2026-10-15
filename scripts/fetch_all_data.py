"""Download and merge Dukascopy EUR/CZK H4 data year-by-year."""

import csv
import subprocess
import time
from pathlib import Path

DATA_DIR = Path("fxdata")
FINAL_FILE = DATA_DIR / "eurczk-h4-bid-2017-01-02-2026-10-15.csv"

YEARS = [
    ("2017-01-02", "2017-12-31", "chunk_2017.csv"),
    ("2018-01-01", "2018-12-31", "chunk_2018.csv"),
    ("2019-01-01", "2019-12-31", "chunk_2019.csv"),
    ("2020-01-01", "2020-12-31", "chunk_2020.csv"),
    ("2021-01-01", "2021-12-31", "chunk_2021.csv"),
    ("2022-01-01", "2022-12-31", "chunk_2022.csv"),
    ("2023-01-01", "2023-12-31", "chunk_2023.csv"),
    ("2024-01-01", "2024-12-31", "chunk_2024.csv"),
    ("2025-01-01", "2025-12-31", "chunk_2025.csv"),
    ("2026-01-01", "2026-10-15", "chunk_2026.csv"),
]

def download_chunk(from_date: str, to_date: str, chunk_name: str) -> Path:
    chunk_path = DATA_DIR / chunk_name
    if chunk_path.exists() and chunk_path.stat().st_size > 1000:
        print(f"Chunk already exists: {chunk_path} ({chunk_path.stat().st_size} bytes)")
        return chunk_path

    stem = chunk_name.replace(".csv", "")
    cmd = [
        "npx", "-y", "dukascopy-node",
        "-i", "eurczk",
        "-from", from_date,
        "-to", to_date,
        "-t", "h4",
        "-p", "bid",
        "-f", "csv",
        "-dir", str(DATA_DIR),
        "-fn", stem,
        "-r", "5",
        "-rp", "1500",
        "-bp", "500",
        "-s",
    ]
    print(f"Downloading {from_date} to {to_date} -> {chunk_path}...")
    for attempt in range(1, 4):
        res = subprocess.run(cmd, capture_output=True, text=True)
        if chunk_path.exists() and chunk_path.stat().st_size > 500:
            print(f"  Successfully downloaded {chunk_path}")
            time.sleep(1.0)
            return chunk_path
        print(f"  Attempt {attempt} failed, retrying in 3s...")
        time.sleep(3.0)

    return chunk_path

def merge_chunks():
    all_rows = []
    seen_ts = set()
    header = None

    for _, _, chunk_name in YEARS:
        chunk_path = DATA_DIR / chunk_name
        if not chunk_path.exists():
            continue
        with open(chunk_path, "r", encoding="utf-8") as f:
            reader = csv.reader(f)
            h = next(reader, None)
            if not header and h:
                header = h
            for row in reader:
                if not row:
                    continue
                ts = row[0]
                if ts not in seen_ts:
                    seen_ts.add(ts)
                    all_rows.append(row)

    all_rows.sort(key=lambda r: float(r[0]) if r[0].isdigit() else r[0])
    print(f"Total merged candles: {len(all_rows)}")
    with open(FINAL_FILE, "w", encoding="utf-8", newline="") as f:
        writer = csv.writer(f)
        if header:
            writer.writerow(header)
        writer.writerows(all_rows)

    print(f"Merged output saved to {FINAL_FILE} ({FINAL_FILE.stat().st_size} bytes)")

def main():
    DATA_DIR.mkdir(exist_ok=True)
    for from_date, to_date, chunk_name in YEARS:
        download_chunk(from_date, to_date, chunk_name)
    merge_chunks()

if __name__ == "__main__":
    main()
