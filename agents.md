# Agents Guide

This project is a systematic trading research scaffold for a regime-based
Nasdaq-100 alpha framework. Treat it as research infrastructure, not as a
broker, alerting system, or trade-execution tool.

## Mission

Help build a robust, reproducible workflow for testing strategy families across
market regimes:

- trend following: Supertrend, EMA cross, Donchian-style breakouts,
- pullback and mean reversion: RSI and Bollinger variants,
- intermediate momentum: MACD and volatility expansion,
- portfolio controls: volatility sizing, heat limits, correlation limits,
- validation: walk-forward testing, out-of-sample metrics, and benchmark
  comparisons.

## Research Principles

- Prefer out-of-sample robustness over in-sample headline return.
- Always compare strategy returns against buy-and-hold and a simple baseline
  such as QQQ above/below its 200-day moving average.
- Avoid treating the current Nasdaq-100 list as a historical universe.
  Survivorship bias is a first-order risk in this project.
- Keep assumptions explicit: data vendor, adjustment method, execution price,
  transaction costs, slippage, rebalance timing, and delisted-name handling.
- Do not over-optimize on NVDA, AI leaders, or any recent two-year bull period.
- When using TradingView MCP results, treat them as directional screens unless
  the exact strategy implementation is visible and reproducible.

## Coding Conventions

- Python source lives under `src/regime_alpha`.
- Scripts live under `scripts`.
- Tests live under `tests`.
- Use lower-case OHLCV columns: `open`, `high`, `low`, `close`, `volume`.
- Standard signal frames should use:
  - `signal_direction`: `1` for long entry, `-1` for exit, `0` for no action,
  - `initial_stop_loss`: optional fixed stop price at entry.
- Keep modules small and composable. The portfolio engine should call strategy
  signal functions rather than embedding indicator logic directly.
- Use ASCII in project files unless there is a clear reason not to.

## Current Capabilities

- Fetch a current Nasdaq-100 snapshot.
- Download adjusted daily OHLCV from Yahoo Finance for prototyping.
- Compute KER, Hurst, ATR, RSI, Bollinger Bands, and MACD.
- Classify broad regimes into trend, mean-reversion, momentum, and neutral
  buckets.
- Generate standardized signals for several basic strategy families.
- Run a simple close-based long-only backtest for a single symbol.
- Query point-in-time universe membership from a historical constituent table.

## Known Gaps

- Historical Nasdaq-100 membership is currently a placeholder and must be
  replaced with point-in-time constituent intervals before serious results are
  trusted.
- Yahoo Finance data is convenient but not a production-grade institutional
  research source.
- The current simulator is intentionally simple. It does not yet implement full
  portfolio construction, rebalance queues, borrow constraints, tax lots,
  partial fills, or intraday stop simulation beyond coarse daily OHLC checks.
- Walk-forward optimization and Deflated Sharpe Ratio diagnostics still need to
  be implemented.

## Safe Next Moves

1. Add tests around indicators, regime classification, universe membership, and
   backtest accounting.
2. Build a portfolio simulator that combines per-symbol signals, volatility
   sizing, heat limits, and correlation gates.
3. Add walk-forward orchestration with train/test windows.
4. Add reporting tables that rank strategies by total return, CAGR, drawdown,
   Sharpe, profit factor, win rate, and benchmark-relative return.
5. Only then run broader parameter sweeps.

