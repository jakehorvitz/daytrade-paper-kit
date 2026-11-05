"""Offline, next-open paper replay. No profitability claim."""
import argparse
import csv
import json
import math
import tempfile
from pathlib import Path
from .broker import SimulatedBroker
from .data import load_csv
from .risk import RiskManager
from .strategy import sma_signal, Signal

DISCLAIMER = 'PAPER ONLY — educational simulation; no profitability claim or investment advice.'


def replay(bars, start=0, *, mode='baseline', adapter=None, starting_equity=100000.0,
           max_position_pct=0.10, max_daily_loss_pct=0.02, slippage_bps=5, commission=0,
           kill_path='.daytrade/kill_switch.json', fast=3, slow=8):
    broker = SimulatedBroker(cash=starting_equity)
    risk = RiskManager(max_position_pct, max_daily_loss_pct, kill_path)
    curve, fills = [], []
    benchmark_attempted = False
    for i in range(start, len(bars)):
        bar = bars[i]
        # Observe open equity before fills, then close equity after price movement.
        risk.observe(bar.timestamp, broker.equity(bar.open))
        for fill in broker.fill_pending(bar.open, risk, slippage_bps, commission):
            fills.append({'timestamp': bar.timestamp.isoformat(), **fill})
        equity = broker.equity(bar.close)
        risk.observe(bar.timestamp, equity)
        curve.append((bar.timestamp.isoformat(), equity))
        if mode == 'baseline':
            signal = sma_signal([b.close for b in bars[:i+1]], fast, slow)
        elif mode == 'llm':
            signal = adapter.signal(bars[:i+1])
        elif mode == 'benchmark':
            signal = Signal('buy' if not benchmark_attempted else 'hold')
            benchmark_attempted = True
        else:
            raise ValueError('unknown mode')
        if i + 1 == len(bars):
            continue
        if signal.action == 'buy':
            # Reserve at current close; fill rechecks at next open.
            desired = max(0, (equity * max_position_pct - broker.position * bar.close) / bar.close)
            if desired > 0:
                broker.submit('buy', desired, bar.close, risk)
        elif signal.action == 'sell' and broker.position > 0:
            broker.submit('sell', broker.position, bar.close, risk)
    ending = curve[-1][1] if curve else starting_equity
    return {'starting_equity': starting_equity, 'ending_equity': ending,
            'net_total_return': ending / starting_equity - 1, 'fills': fills, 'curve': curve}


def run(bars, *, adapter=None, slow=8, fast=3, output_dir='reports', _print_disclaimer=True, **kwargs):
    if _print_disclaimer:
        print(DISCLAIMER)
    if not 0 < fast < slow:
        raise ValueError('require 0 < fast < slow')
    n = len(bars)
    k = math.ceil(.2 * n)
    start = n - k
    if k < 2 or start < slow + 1:
        raise ValueError('insufficient bars: require at least two holdout bars and slow_window + 1 prefix bars')
    # Capture the pre-run switch before the full account can trip it. Each
    # comparison starts with that state and an independent simulated account.
    live_switch = Path(kwargs.get('kill_path', '.daytrade/kill_switch.json'))
    initial_switch = live_switch.read_bytes() if live_switch.exists() else None
    full = replay(bars, fast=fast, slow=slow, **kwargs)
    with tempfile.TemporaryDirectory(prefix='daytrade-comparisons-') as temp:
        def scenario(mode):
            switch = Path(temp) / (mode + '.json')
            if initial_switch is not None:
                switch.write_bytes(initial_switch)
            settings = {**kwargs, 'kill_path': switch}
            return replay(bars, start, mode=mode, adapter=adapter, fast=fast, slow=slow, **settings)
        baseline = scenario('baseline')
        benchmark = scenario('benchmark')
        llm = scenario('llm') if adapter is not None else None
    summary = {'disclaimer': DISCLAIMER, 'bars': n, 'holdout_bars': k,
               'costs': {'slippage_bps': kwargs.get('slippage_bps', 5), 'commission': kwargs.get('commission', 0)},
               'full_return': full['net_total_return'], 'holdout': {'baseline_return': baseline['net_total_return'],
               'benchmark_return': benchmark['net_total_return'], 'benchmark': 'risk-capped buy-and-hold, next-open entry'},
               'llm': {'enabled': adapter is not None, 'validation': 'unvalidated'}}
    if adapter is not None:
        summary['llm'].update({'holdout_return': llm['net_total_return'], 'baseline_holdout_return': baseline['net_total_return'],
                               'beats_baseline': llm['net_total_return'] > baseline['net_total_return']})
    output = Path(output_dir)
    output.mkdir(parents=True, exist_ok=True)
    (output / 'summary.json').write_text(json.dumps(summary, indent=2) + '\n')
    with (output / 'equity_curve.csv').open('w', newline='') as f:
        writer = csv.writer(f)
        writer.writerow(['timestamp', 'equity'])
        writer.writerows(full['curve'])
    return summary


def main():
    print(DISCLAIMER)
    parser = argparse.ArgumentParser(description=DISCLAIMER)
    parser.add_argument('csv')
    args = parser.parse_args()
    try:
        summary = run(load_csv(args.csv), _print_disclaimer=False)
    except (ValueError, OSError) as exc:
        parser.exit(2, f'error: {exc}\n')
    print(json.dumps(summary, indent=2))

if __name__ == '__main__':
    main()
