# Regime-Based Alpha Framework Plan

## Objective

Build a survivorship-aware research pipeline that can test whether regime
classification improves strategy selection across Nasdaq-100 stocks.

The main hypothesis is that different stocks and periods favor different
strategy families because their price behavior alternates between trend,
momentum burst, mean-reversion, and neutral regimes.

## Phase 1 - Foundation

Status: complete

- [x] Create project scaffold.
- [x] Add current Nasdaq-100 snapshot fetcher.
- [x] Add OHLCV downloader for prototype data.
- [x] Add core indicators: Hurst, KER, ATR, RSI, Bollinger, MACD.
- [x] Add coarse regime classifier.
- [x] Add basic strategy signal generators.
- [x] Add point-in-time universe membership utilities.
- [x] Add single-symbol long-only backtest primitives.
- [x] Add unit tests for first core modules.

## Phase 2 - Data Integrity

Status: complete for public-source prototype; vendor-grade data still required

- [x] Replace `data/manual/nasdaq100_constituents_history.csv` placeholder with
      approximate public-source historical constituent intervals.
- [x] Add delisted/ticker-change mapping fields if available.
- [x] Add data quality checks for missing bars, split anomalies, duplicate
      dates, zero volume, and extreme returns.
- [x] Build adjusted OHLCV cache metadata with source, download date, and
      adjustment method.
- [x] Add validation script for constituent and OHLCV reports.
- [x] Source/import public Nasdaq-100 membership changes from Wikipedia.
- [ ] Replace Wikipedia reconstruction with a vendor-grade survivorship-bias-free
      historical membership table before final research.

## Phase 3 - Strategy Research

Status: complete for first transparent strategy suite

- [x] Reproduce MCP-style strategy families with transparent Python logic.
- [x] Add Supertrend and Donchian signal modules.
- [x] Add volume-confirmed breakout and pullback continuation variants.
- [x] Add QQQ market regime filters.
- [x] Add stock-level relative-strength filters versus QQQ.
- [x] Create parameter grids with deliberately small, explainable ranges.
- [x] Add strategy-suite runner for symbol-level comparisons.

## Phase 4 - Portfolio Simulation

Status: complete for first simulator and UI

- [x] Combine per-symbol signals into a daily candidate book.
- [x] Add ATR-based position sizing.
- [x] Enforce max positions and max portfolio heat.
- [x] Add correlation filter using trailing returns.
- [x] Add execution assumptions: close-based fills, commission,
      slippage, and skipped trades on missing data.
- [x] Output trade logs, daily equity curves, positions, and exposure.
- [x] Add local HTML UI for inputs and results.
- [x] Add next-open execution mode.
- [x] Add turnover and benchmark-relative portfolio reports.

## Phase 5 - Walk-Forward Validation

Status: complete for first single-symbol walk-forward engine

- [x] Implement rolling train/test windows, defaulting to 4-year train and
      1-year test.
- [x] Select best parameters on each training window from small grids.
- [x] Stitch out-of-sample periods into one equity curve.
- [x] Add robust plateau parameter selection instead of single best points.
- [x] Compare against benchmark buy-and-hold and 200-day moving-average timing.
- [x] Report total return, CAGR, max drawdown, Sharpe, profit factor, win rate,
      turnover, exposure, and benchmark-relative return where supported.

## Phase 6 - Robustness And Reporting

Status: complete for first robustness/reporting pass

- [x] Add bootstrap or permutation tests for strategy stability.
- [x] Add multiple-testing diagnostics as an adjusted Sharpe haircut.
- [x] Segment results by stock group: mega-cap platforms, semis, software,
      defensives, cyclicals, and speculative high-beta names.
- [x] Generate concise research memos explaining why each strategy family works
      or fails for each group.
- [ ] Replace adjusted Sharpe haircut with a formal Deflated Sharpe Ratio.
- [ ] Add block-bootstrap/permutation diagnostics for autocorrelated returns.

## Immediate Next Checklist

- [x] Write tests for `universe.py` and `backtest.py`.
- [x] Write tests for Phase 2 data integrity checks.
- [x] Add Supertrend and Donchian strategy functions.
- [ ] Add an example script that backtests one symbol from downloaded OHLCV.
- [x] Add a strategy-suite comparison script for one downloaded symbol.
- [x] Add a first portfolio simulation pass with equal-risk sizing.
- [x] Download broader OHLCV cache for multi-symbol portfolio testing.
