"""Recreate sample.csv: synthetic bars, seed 7, not market data."""
import csv
import math
import random
from datetime import datetime, timedelta, timezone
from pathlib import Path
rng = random.Random(7)
start = datetime(2025, 1, 2, 14, 30, tzinfo=timezone.utc)
path = Path(__file__).with_name('sample.csv')
with path.open('w', newline='') as f:
    writer = csv.writer(f)
    writer.writerow(['timestamp', 'open', 'high', 'low', 'close', 'volume'])
    previous = 100.0
    for i in range(120):
        opening = previous
        closing = opening * (1 + 0.002 * math.sin(i / 4) + rng.uniform(-.001, .001))
        writer.writerow([(start + timedelta(minutes=i)).isoformat(), f'{opening:.4f}', f'{max(opening, closing)+.1:.4f}', f'{min(opening, closing)-.1:.4f}', f'{closing:.4f}', rng.randrange(100, 1000)])
        previous = closing
