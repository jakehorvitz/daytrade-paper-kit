"""Strict CSV data ingestion. Prices are unadjusted."""
import csv
import math
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Protocol


@dataclass(frozen=True)
class Bar:
    timestamp: datetime
    open: float
    high: float
    low: float
    close: float
    volume: float


class DataProvider(Protocol):
    def load(self) -> list[Bar]: ...


class CSVProvider:
    def __init__(self, path: str | Path):
        self.path = path

    def load(self) -> list[Bar]:
        return load_csv(self.path)


def load_csv(path: str | Path) -> list[Bar]:
    bars = []
    with open(path, newline='', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        fields = ('timestamp', 'open', 'high', 'low', 'close', 'volume')
        missing = set(fields) - set(reader.fieldnames or [])
        if missing:
            raise ValueError(f"row 1: missing columns: {', '.join(sorted(missing))}")
        for rownum, row in enumerate(reader, 2):
            try:
                stamp = datetime.fromisoformat(row['timestamp'].replace('Z', '+00:00'))
                if stamp.tzinfo is None or stamp.utcoffset() is None:
                    raise ValueError('timezone required')
                stamp = stamp.astimezone(timezone.utc)
            except (ValueError, TypeError, AttributeError) as exc:
                raise ValueError(f'row {rownum}: timestamp must be ISO 8601 with timezone') from exc
            if bars and stamp <= bars[-1].timestamp:
                raise ValueError(f'row {rownum}: timestamp duplicate or non-monotonic after UTC normalization')
            values = {}
            for field in fields[1:]:
                try:
                    value = float(row[field])
                except (ValueError, TypeError):
                    raise ValueError(f'row {rownum}: {field} must be numeric') from None
                if not math.isfinite(value) or (value < 0 if field == 'volume' else value <= 0):
                    raise ValueError(f'row {rownum}: {field} must be finite and {"nonnegative" if field == "volume" else "positive"}')
                values[field] = value
            if values['high'] < values['low']:
                raise ValueError(f'row {rownum}: high below low')
            for field in ('open', 'close'):
                if not values['low'] <= values[field] <= values['high']:
                    raise ValueError(f'row {rownum}: {field} outside low/high')
            bars.append(Bar(stamp, **values))
    return bars
