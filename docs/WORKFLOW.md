# Paper-only workflow

1. Create a Python 3.11+ virtual environment and run the setup and tests in the README. The sample is synthetic; do not infer real-market results from it.
2. Place an unadjusted OHLCV CSV in a local file. Use explicit timezones, positive finite prices, nonnegative finite volume, and increasing unique timestamps. The loader checks every bar.
3. Run `python -m daytrade.backtest path/to/file.csv`. Inspect the full and holdout returns, the risk-capped benchmark, costs, and equity CSV under `reports/`.
4. Keep the kill switch in place and review any trip before clearing it manually. This kit only simulates; its Alpaca class is a non-network stub.
5. Optional experiments can inject an `LLMAdapter` into `daytrade.backtest.run`. It is off by default and unvalidated. Compare on the same chronological holdout; no recommendation follows from the synthetic example.

## Optional Bones workflow

Bones is a separate, locally installed tool and is not included in this repo. If Justin chooses to use it, install and configure his own copy and owner credentials; do not copy Jake's keys or private state. Initialize a new run with a pinned acceptance command, then follow `bones status`: Stage 1 interrogation, Stage 2 owner decision, Stage 3 owner spec sign-off, Stage 4 critique, Stage 5 plan and verified build, Stage 6 review, Stage 7 staging, Stage 8 owner promotion and smoke, Stage 9 presentation, Stage 10 owner operate decision. Use the installed skill's instructions and owner authentication at each gate. This repo's manual implementation is not evidence that any Bones gate passed. No live trade or deployment is part of this kit.
