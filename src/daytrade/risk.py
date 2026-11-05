"""Persistent kill switch and paper account risk limits."""
import json
import math
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

class RiskManager:
    def __init__(self, max_position_pct=0.10, max_daily_loss_pct=0.02, kill_path='.daytrade/kill_switch.json'):
        if not (0 < max_position_pct <= 1 and 0 < max_daily_loss_pct <= 1):
            raise ValueError('risk limits must be in (0, 1]')
        self.max_position_pct = max_position_pct
        self.max_daily_loss_pct = max_daily_loss_pct
        self.kill_path = Path(kill_path)
        self.day = None
        self.start_equity = None

    def killed(self):
        if not self.kill_path.exists():
            return False
        try:
            data = json.loads(self.kill_path.read_text())
            return data.get('tripped') is not False
        except (OSError, ValueError, AttributeError):
            return True

    def trip(self, reason):
        self.kill_path.parent.mkdir(parents=True, exist_ok=True)
        self.kill_path.write_text(json.dumps({'tripped': True, 'reason': reason}) + '\n')

    def clear_manually(self):
        self.kill_path.parent.mkdir(parents=True, exist_ok=True)
        self.kill_path.write_text(json.dumps({'tripped': False}) + '\n')

    def observe(self, when: datetime, equity: float):
        if when.tzinfo is None or not math.isfinite(equity):
            raise ValueError('aware time and finite equity required')
        day = when.astimezone(ZoneInfo('America/New_York')).date()
        if day != self.day:
            self.day, self.start_equity = day, equity
        if self.start_equity <= 0 or equity <= self.start_equity * (1 - self.max_daily_loss_pct):
            self.trip('daily loss limit')
        return not self.killed()

    def allowed(self, action, quantity, price, equity, position, pending_buy_value=0):
        if self.killed() or action not in ('buy', 'sell') or not all(math.isfinite(x) for x in (quantity, price, equity, position, pending_buy_value)):
            return False
        if quantity <= 0 or price <= 0 or equity <= 0 or position < 0 or pending_buy_value < 0:
            return False
        if action == 'sell':
            return quantity <= position
        return (position * price + pending_buy_value + quantity * price <= equity * self.max_position_pct + 1e-9)
