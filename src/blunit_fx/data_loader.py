"""Historical FX market data loader for EUR/CZK."""

import csv
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import List, Optional, Union


@dataclass(frozen=True)
class MarketCandle:
    """Historical market price candle (e.g. H4 timeframe)."""
    timestamp: datetime
    open: float
    high: float
    low: float
    close: float

    @property
    def mid_price(self) -> float:
        """Reference mid rate for the candle (close price)."""
        return self.close

    @property
    def typical_price(self) -> float:
        """Typical price (High + Low + Close) / 3."""
        return (self.high + self.low + self.close) / 3.0


def parse_timestamp(val: str) -> datetime:
    """Parse various timestamp formats from FX data files."""
    val = val.strip()
    # Check for unix epoch milliseconds
    try:
        numeric_val = float(val)
        # If timestamp is in milliseconds (e.g. 1483315200000)
        if numeric_val > 1e11:
            return datetime.fromtimestamp(numeric_val / 1000.0, tz=timezone.utc)
        # If timestamp is in seconds
        elif numeric_val > 1e8:
            return datetime.fromtimestamp(numeric_val, tz=timezone.utc)
    except ValueError:
        pass

    # Try common ISO and datetime string formats
    clean_val = val.replace("Z", "+00:00")
    for fmt in (
        "%Y-%m-%d %H:%M:%S.%f",
        "%Y-%m-%d %H:%M:%S",
        "%Y-%m-%d %H:%M",
        "%Y-%m-%d",
        "%Y.%m.%d %H:%M:%S",
        "%Y.%m.%d %H:%M",
        "%d.%m.%Y %H:%M:%S",
        "%d.%m.%Y %H:%M:%S.%f",
        "%d.%m.%Y %H:%M",
    ):
        try:
            return datetime.strptime(clean_val, fmt).replace(tzinfo=timezone.utc)
        except ValueError:
            continue

    try:
        return datetime.fromisoformat(clean_val)
    except Exception as exc:
        raise ValueError(f"Unable to parse timestamp string: '{val}'") from exc


def load_market_data(
    filepath: Union[str, Path],
    start_date: Optional[datetime] = None,
    end_date: Optional[datetime] = None,
) -> List[MarketCandle]:
    """
    Load and parse historical market candles from CSV file with date filtering.

    Args:
        filepath: Path to the CSV file.
        start_date: Optional start datetime filter (inclusive).
        end_date: Optional end datetime filter (inclusive).

    Returns:
        Chronologically sorted list of MarketCandle objects.
    """
    path = Path(filepath)
    if not path.exists():
        raise FileNotFoundError(f"FX data file not found: {path}")

    candles: List[MarketCandle] = []

    with open(path, "r", encoding="utf-8") as f:
        # Detect delimiter and format
        sample = f.read(2048)
        f.seek(0)
        if not sample.strip():
            raise ValueError(f"FX data file is empty: {path}")

        try:
            dialect = csv.Sniffer().sniff(sample, delimiters=",;\t")
        except Exception:
            dialect = csv.excel

        reader = csv.DictReader(f, dialect=dialect)
        if not reader.fieldnames:
            raise ValueError(f"No valid header found in CSV: {path}")

        # Normalize fieldnames to lowercase trimmed
        norm_map = {name: name.strip().lower() for name in reader.fieldnames if name}

        # Identify required columns
        ts_col = None
        open_col = None
        high_col = None
        low_col = None
        close_col = None

        for orig_name, norm in norm_map.items():
            if norm in ("timestamp", "time", "date", "gmt time", "local time"):
                ts_col = orig_name
            elif norm in ("open", "bid_open", "bidopen"):
                open_col = orig_name
            elif norm in ("high", "bid_high", "bidhigh"):
                high_col = orig_name
            elif norm in ("low", "bid_low", "bidlow"):
                low_col = orig_name
            elif norm in ("close", "bid_close", "bidclose", "price", "bid"):
                close_col = orig_name

        if not ts_col:
            # Fallback to first column as timestamp
            ts_col = reader.fieldnames[0]

        for row in reader:
            raw_ts = row.get(ts_col)
            if not raw_ts:
                continue

            ts = parse_timestamp(raw_ts)

            # Apply timezone-aware or naive comparison
            if start_date:
                cmp_start = start_date if start_date.tzinfo else start_date.replace(tzinfo=timezone.utc)
                if ts < cmp_start:
                    continue
            if end_date:
                cmp_end = end_date if end_date.tzinfo else end_date.replace(tzinfo=timezone.utc)
                if ts > cmp_end:
                    continue

            close_val = float(row[close_col]) if close_col and row.get(close_col) else 0.0
            open_val = float(row[open_col]) if open_col and row.get(open_col) else close_val
            high_val = float(row[high_col]) if high_col and row.get(high_col) else max(open_val, close_val)
            low_val = float(row[low_col]) if low_col and row.get(low_col) else min(open_val, close_val)

            candles.append(
                MarketCandle(
                    timestamp=ts,
                    open=open_val,
                    high=high_val,
                    low=low_val,
                    close=close_val,
                )
            )

    candles.sort(key=lambda c: c.timestamp)
    return candles
