# Regime-Based Alpha Framework

Research scaffold for a Nasdaq-100 regime-switching strategy project.

The goal is to move from an exploratory MCP strategy screen to a robust
walk-forward research process:

- Build a historical Nasdaq-100 universe.
- Download adjusted daily OHLCV data.
- Classify market and stock regimes with Hurst exponent and Kaufman Efficiency
  Ratio.
- Route symbols into strategy families: trend, mean reversion, and momentum.
- Validate out-of-sample with walk-forward tests and portfolio-level risk
  controls.

## Important Data Warning

The current free-data scripts can fetch the current Nasdaq-100 list and Yahoo
Finance adjusted OHLCV. The project can also reconstruct approximate historical
Nasdaq-100 membership intervals from Wikipedia's current component and component
change tables. That is useful for prototyping, but it is not enough for a
production-grade survivorship-bias-free study.

A true 2010-present historical Nasdaq-100 universe must include:

- additions and removals by effective date,
- delisted tickers,
- ticker changes,
- bankrupt or acquired companies,
- split/dividend-adjusted price history.

For rigorous work, use a survivorship-free vendor or maintain
`data/manual/nasdaq100_constituents_history.csv` with historical membership
intervals.

## Project Layout

```text
config/default.toml                  Research defaults
data/manual/                         Manual universe inputs
data/raw/                            Raw downloaded data
data/processed/                      Cleaned research data
notebooks/                           Exploratory notebooks
scripts/import_nasdaq100_wikipedia_history.py
                                      Public-source constituent reconstruction
scripts/fetch_current_nasdaq100.py   Current Nasdaq-100 snapshot
scripts/download_ohlcv.py            Adjusted/raw OHLCV downloader
scripts/validate_data_integrity.py   Constituent/OHLCV validation reports
scripts/backtest_symbol_strategies.py
                                      Compare transparent strategy suite
scripts/backtest_portfolio.py         Multi-symbol portfolio simulator
scripts/walk_forward_symbol.py        Single-symbol walk-forward validation
scripts/serve_ui.py                   Local HTML research UI
scripts/calibrate_against_mcp.py      MCP/local backtest comparison report
src/regime_alpha/indicators.py       Hurst, KER, ATR, RSI, MACD, etc.
src/regime_alpha/regime.py           Regime classification logic
src/regime_alpha/strategies.py       Standardized strategy signal functions
src/regime_alpha/research.py         Strategy-suite runner and summaries
src/regime_alpha/data_quality.py     OHLCV schema and anomaly checks
src/regime_alpha/universe.py         Point-in-time universe utilities
```

## Quick Start

Install dependencies:

```bash
uv sync
```

Fetch a current Nasdaq-100 snapshot:

```bash
uv run python scripts/fetch_current_nasdaq100.py
```

Import approximate historical Nasdaq-100 intervals from Wikipedia:

```bash
uv run python scripts/import_nasdaq100_wikipedia_history.py
```

Download adjusted daily OHLCV for the snapshot:

```bash
uv run python scripts/download_ohlcv.py --universe data/raw/current_nasdaq100.csv
```

For TradingView/MCP calibration, download raw Yahoo OHLCV instead. Raw prices
match the close levels used by the TradingView MCP `backtest_strategy` output,
while the default adjusted cache is better for dividend/split-adjusted research:

```bash
uv run python scripts/download_ohlcv.py --universe data/manual/starter_universe.csv --start 2024-06-13 --end 2026-06-13 --adjustment raw --output-dir data/processed/calibration/raw_ohlcv
```

Compare the transparent strategy suite for one downloaded symbol:

```bash
uv run python scripts/backtest_symbol_strategies.py --symbol MSFT
```

Run a portfolio simulation over cached OHLCV files:

```bash
uv run python scripts/backtest_portfolio.py --symbols GOOG,MSFT,NVDA --strategy ema_cross
```

Run a walk-forward validation for one cached symbol:

```bash
uv run python scripts/walk_forward_symbol.py --symbol GOOG --strategy ema_cross
```

Compare saved MCP `backtest_strategy` results against the local engine:

```bash
uv run python scripts/calibrate_against_mcp.py
```

The local engine marks open positions to market and computes drawdown from daily
equity. The MCP built-in backtester reports closed-trade capital, excludes open
trades at the end of the test, and uses its own fixed strategy definitions, so
Sharpe and drawdown are not directly comparable without this calibration step.

Start the local HTML UI:

```bash
uv run python scripts/serve_ui.py
```

Then open:

```text
http://127.0.0.1:8765
```

The UI supports:

- portfolio backtests,
- single-symbol strategy comparisons,
- walk-forward validation,
- close or next-open execution timing,
- optional benchmark comparison when the benchmark symbol is cached,
- a TradingView-style equity/benchmark chart.

Download the starter universe used for multi-symbol UI testing:

```bash
uv run python scripts/download_ohlcv.py --universe data/manual/starter_universe.csv --start 2010-01-01
```

Yahoo Finance adjusted OHLC can occasionally flag `invalid_ohlc` after
adjustment, especially around corporate actions. Treat those rows as review
items, not automatic proof that the symbol is unusable.

Run data-integrity validation:

```bash
uv run python scripts/validate_data_integrity.py
```

The validation script writes:

- `data/processed/constituent_history_quality_report.csv`
- `data/processed/ohlcv_quality_report.csv`

Downloaded OHLCV files also get JSON metadata sidecars under
`data/raw/ohlcv_metadata/`.

## Next Research Milestones

1. Replace Wikipedia reconstruction and Yahoo OHLCV with vendor-grade
   survivorship-free constituent and price data before trusting final results.
2. Add formal Deflated Sharpe Ratio and block-bootstrap diagnostics.
3. Add portfolio-level walk-forward validation.
4. Add richer benchmark reports and tear sheets.
