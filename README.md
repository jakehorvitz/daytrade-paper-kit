# Daytrade starter kit — paper only

An educational, offline Python simulation. It is **paper only**, is not investment advice, and makes no profitability claim. Sample prices are synthetic, not market data. The Alpaca class is an offline stub: it cannot connect to Alpaca or submit orders. There is no live-trading mode or network broker implementation.

## Setup and run

Python 3.11 or newer is required. From this directory:

```sh
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -e . pytest
python -m pytest -q
python -m daytrade.backtest examples/sample.csv
```

Installing dependencies requires package access; after installation the simulation itself runs offline. Each run prints the disclaimer and writes `reports/summary.json` and `reports/equity_curve.csv`. To regenerate the synthetic sample exactly, run `python examples/generate_sample.py`. Prices are unadjusted. Input is CSV with `timestamp,open,high,low,close,volume`; timestamps need explicit offsets and are normalized to UTC. Invalid bars fail with row and field/rule.

## How the simulation works

The default strategy calculates SMA crossovers using completed closes. An actionable signal can fill only on the next bar's open, with 5 basis points slippage per fill and zero commission by default. Final-bar signals cannot fill; open positions are marked to the final close. The final `ceil(20% of bars)` is a chronological holdout, using a fresh paper account and earlier closes only to warm indicators. The benchmark buys on the next open and holds within the same position cap, so it is a **risk-capped** buy-and-hold comparison. These synthetic results say nothing about real-market performance.

The position cap includes pending buys, and fills are rechecked at actual prices. Daily loss uses account equity (realized and unrealized P&L) against the first observed equity of the New York trading day. A tripped switch persists in `.daytrade/kill_switch.json` and blocks all orders. Each comparison starts from the switch state at the beginning of the run, so a pre-existing trip blocks every scenario, while a trip in one simulated account does not contaminate the others. The full replay's trip persists for future runs; hypothetical comparison trips are local to their scenarios. Inspect the reason and intentionally clear a persisted switch using `RiskManager(...).clear_manually()` only after reviewing the situation. A malformed switch fails closed. The sample config documents defaults; the CLI currently uses those defaults rather than reading the config.

The optional `LLMAdapter` accepts an injected callable; no provider or network integration is supplied. It is disabled by default, schema-checks output, logs responses, and returns hold on timeout or invalid output. A timed-out provider thread may continue in the background; use only a trusted provider that supports its own cancellation. LLM results are unvalidated and are not recommended. A future recommendation would require a strict win over baseline on comparable, non-synthetic holdout data; the example cannot establish that.

See [WORKFLOW](docs/WORKFLOW.md) for how to use this repository and its optional review workflow.
