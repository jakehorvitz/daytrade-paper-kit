"""Simulation only: the Alpaca class is an offline stub and sends no orders."""
from dataclasses import dataclass, field

PAPER_URL = 'https://paper-api.alpaca.markets'

class AlpacaPaperStub:
    def __init__(self, base_url=PAPER_URL):
        if base_url != PAPER_URL:
            raise ValueError('only the fixed Alpaca paper endpoint is permitted')
        self.base_url = PAPER_URL

    def submit(self, *args, **kwargs):
        raise NotImplementedError('offline stub: no network or broker integration')

@dataclass
class SimulatedBroker:
    cash: float = 100_000.0
    position: float = 0.0
    pending: list = field(default_factory=list)

    def equity(self, price):
        return self.cash + self.position * price

    def submit(self, action, quantity, price, risk):
        pending = sum(q * p for a, q, p in self.pending if a == 'buy')
        if not risk.allowed(action, quantity, price, self.equity(price), self.position, pending):
            return False
        self.pending.append((action, quantity, price))
        return True

    def fill_pending(self, open_price, risk, slippage_bps=5, commission=0):
        orders, self.pending = self.pending, []
        fills = []
        for action, requested, _ in orders:
            price = open_price * (1 + slippage_bps / 10000 * (1 if action == 'buy' else -1))
            equity = self.equity(open_price)
            # Recheck at actual fill price after gaps, costs and earlier fills.
            if action == 'buy':
                # Post-fill equity includes spread/slippage and commission.
                max_q = max(0.0, (risk.max_position_pct * (equity - commission) - self.position * price) / (price + risk.max_position_pct * (price - open_price)))
                quantity = min(requested, max_q, max(0.0, (self.cash - commission) / price))
            else:
                quantity = min(requested, self.position)
            if quantity <= 1e-12 or not risk.allowed(action, quantity, price, equity, self.position):
                continue
            if action == 'buy':
                self.cash -= quantity * price + commission
                self.position += quantity
            else:
                self.cash += quantity * price - commission
                self.position -= quantity
            fills.append({'action': action, 'quantity': quantity, 'price': price})
        return fills
