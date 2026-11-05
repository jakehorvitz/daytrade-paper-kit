"""Deterministic crossover signals from completed closes."""
from dataclasses import dataclass

@dataclass(frozen=True)
class Signal:
    action: str
    confidence: float = 1.0
    reason: str = ''


def sma_signal(closes: list[float], fast: int = 3, slow: int = 8) -> Signal:
    if fast < 1 or slow <= fast:
        raise ValueError('require 0 < fast < slow')
    if len(closes) < slow + 1:
        return Signal('hold', reason='warming indicators')
    before_fast = sum(closes[-fast-1:-1]) / fast
    before_slow = sum(closes[-slow-1:-1]) / slow
    now_fast = sum(closes[-fast:]) / fast
    now_slow = sum(closes[-slow:]) / slow
    if before_fast <= before_slow and now_fast > now_slow:
        return Signal('buy', reason='upward crossover')
    if before_fast >= before_slow and now_fast < now_slow:
        return Signal('sell', reason='downward crossover')
    return Signal('hold', reason='no crossover')
