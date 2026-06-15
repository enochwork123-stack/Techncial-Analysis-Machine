from __future__ import annotations

from dataclasses import dataclass
from itertools import product

import numpy as np
import pandas as pd

from regime_alpha.backtest import ExecutionConfig, performance_metrics, run_long_only_backtest
from regime_alpha.research import STRATEGY_FUNCTIONS
from regime_alpha.strategies import strategy_parameter_grids


@dataclass(frozen=True)
class WalkForwardConfig:
    train_years: int = 4
    test_years: int = 1
    objective: str = "sharpe"
    min_train_trades: int = 3
    selection_mode: str = "plateau"
    plateau_top_pct: float = 0.25


@dataclass(frozen=True)
class WalkForwardResult:
    windows: pd.DataFrame
    equity_curve: pd.DataFrame
    trades: pd.DataFrame
    metrics: dict[str, float]
    benchmark_curve: pd.DataFrame
    timing_curve: pd.DataFrame


def parameter_combinations(grid: dict[str, list[int | float]]) -> list[dict[str, int | float]]:
    keys = list(grid)
    return [dict(zip(keys, values, strict=True)) for values in product(*(grid[key] for key in keys))]


def walk_forward_windows(
    index: pd.DatetimeIndex,
    train_years: int = 4,
    test_years: int = 1,
) -> list[tuple[pd.Timestamp, pd.Timestamp, pd.Timestamp, pd.Timestamp]]:
    if index.empty:
        return []
    start = pd.Timestamp(index.min()).normalize()
    end = pd.Timestamp(index.max()).normalize()
    windows = []
    train_start = start
    while True:
        train_end = train_start + pd.DateOffset(years=train_years) - pd.Timedelta(days=1)
        test_start = train_end + pd.Timedelta(days=1)
        test_end = test_start + pd.DateOffset(years=test_years) - pd.Timedelta(days=1)
        if test_start > end:
            break
        windows.append((train_start, min(train_end, end), test_start, min(test_end, end)))
        if test_end >= end:
            break
        train_start = train_start + pd.DateOffset(years=test_years)
    return windows


def _slice(prices: pd.DataFrame, start: pd.Timestamp, end: pd.Timestamp) -> pd.DataFrame:
    return prices.loc[(prices.index >= start) & (prices.index <= end)].copy()


def _run_strategy(
    prices: pd.DataFrame,
    strategy_name: str,
    params: dict[str, int | float],
    execution_config: ExecutionConfig,
):
    signals = STRATEGY_FUNCTIONS[strategy_name](prices, **params)
    return run_long_only_backtest(prices, signals, config=execution_config)


def _param_stability_key(params: dict[str, int | float]) -> float:
    if not params:
        return 0.0
    return float(sum(abs(float(value)) for value in params.values()) / len(params))


def select_parameters(
    train: pd.DataFrame,
    strategy_name: str,
    combinations: list[dict[str, int | float]],
    execution_config: ExecutionConfig,
    config: WalkForwardConfig,
) -> tuple[dict[str, int | float], float, dict[str, float], pd.DataFrame]:
    rows = []
    for params in combinations:
        train_result = _run_strategy(train, strategy_name, params, execution_config)
        metrics = train_result.metrics
        if metrics.get("number_of_trades", 0) < config.min_train_trades:
            continue
        rows.append({"params": params, **metrics})
    scores = pd.DataFrame(rows)
    if scores.empty:
        return combinations[0], float("-inf"), {}, scores
    scores = scores.sort_values(config.objective, ascending=False).reset_index(drop=True)
    if config.selection_mode == "best":
        selected = scores.iloc[0]
    elif config.selection_mode == "plateau":
        keep = max(1, int(np.ceil(len(scores) * config.plateau_top_pct)))
        plateau = scores.head(keep).copy()
        plateau["stability_key"] = plateau["params"].map(_param_stability_key)
        selected = plateau.sort_values(["stability_key", "max_drawdown"], ascending=[True, False]).iloc[0]
    else:
        raise ValueError("selection_mode must be 'best' or 'plateau'")
    params = dict(selected["params"])
    return params, float(selected[config.objective]), selected.drop(labels=["params"]).to_dict(), scores


def benchmark_buy_hold_curve(
    prices: pd.DataFrame,
    initial_capital: float,
    index: pd.DatetimeIndex | None = None,
) -> pd.DataFrame:
    close = prices["close"].copy()
    if index is not None:
        close = close.reindex(index).ffill()
    close = close.dropna()
    if close.empty:
        return pd.DataFrame(columns=["equity"])
    return pd.DataFrame({"equity": initial_capital * (close / close.iloc[0])}, index=close.index)


def benchmark_ma_timing_curve(
    prices: pd.DataFrame,
    initial_capital: float,
    ma_window: int = 200,
    index: pd.DatetimeIndex | None = None,
) -> pd.DataFrame:
    close = prices["close"].copy()
    ma = close.rolling(ma_window).mean()
    invested = (close > ma).shift().fillna(False)
    returns = close.pct_change().fillna(0).where(invested, 0)
    equity = initial_capital * (1 + returns).cumprod()
    if index is not None:
        equity = equity.reindex(index).ffill().dropna()
    return pd.DataFrame({"equity": equity}, index=equity.index)


def run_walk_forward(
    prices: pd.DataFrame,
    strategy_name: str,
    config: WalkForwardConfig | None = None,
    execution_config: ExecutionConfig | None = None,
    parameter_grid: dict[str, list[int | float]] | None = None,
    benchmark: pd.DataFrame | None = None,
) -> WalkForwardResult:
    cfg = config or WalkForwardConfig()
    exec_cfg = execution_config or ExecutionConfig()
    if strategy_name not in STRATEGY_FUNCTIONS:
        raise ValueError(f"Unknown strategy: {strategy_name}")
    if cfg.objective not in {"sharpe", "total_return", "cagr"}:
        raise ValueError("objective must be 'sharpe', 'total_return', or 'cagr'")
    if cfg.selection_mode not in {"best", "plateau"}:
        raise ValueError("selection_mode must be 'best' or 'plateau'")

    grid = parameter_grid or strategy_parameter_grids().get(strategy_name, {})
    combinations = parameter_combinations(grid) if grid else [{}]
    windows = walk_forward_windows(prices.index, cfg.train_years, cfg.test_years)
    window_rows: list[dict[str, object]] = []
    trade_frames = []
    equity_frames = []

    for i, (train_start, train_end, test_start, test_end) in enumerate(windows, start=1):
        train = _slice(prices, train_start, train_end)
        test = _slice(prices, test_start, test_end)
        if train.empty or test.empty:
            continue

        best_params, best_score, best_train_metrics, train_scores = select_parameters(
            train, strategy_name, combinations, exec_cfg, cfg
        )

        test_result = _run_strategy(test, strategy_name, best_params, exec_cfg)
        test_equity = test_result.equity_curve.copy()
        if not test_equity.empty:
            if equity_frames:
                previous = equity_frames[-1]["equity"].iloc[-1]
                test_equity["equity"] = previous * (test_equity["equity"] / test_equity["equity"].iloc[0])
            test_equity["window"] = i
            equity_frames.append(test_equity)
        if not test_result.trades.empty:
            trades = test_result.trades.copy()
            trades["window"] = i
            trades["strategy"] = strategy_name
            trades["params"] = str(best_params)
            trade_frames.append(trades)

        row = {
            "window": i,
            "train_start": train_start.date().isoformat(),
            "train_end": train_end.date().isoformat(),
            "test_start": test_start.date().isoformat(),
            "test_end": test_end.date().isoformat(),
            "params": str(best_params),
            "train_objective": best_score,
            "train_trades": best_train_metrics.get("number_of_trades", 0),
            "selection_mode": cfg.selection_mode,
            "evaluated_params": len(train_scores),
        }
        row.update({f"test_{key}": value for key, value in test_result.metrics.items()})
        window_rows.append(row)

    windows_frame = pd.DataFrame(window_rows)
    equity_curve = pd.concat(equity_frames) if equity_frames else pd.DataFrame()
    trades = pd.concat(trade_frames, ignore_index=True) if trade_frames else pd.DataFrame()
    if equity_curve.empty:
        metrics = {"total_return": 0.0, "cagr": 0.0, "max_drawdown": 0.0, "sharpe": 0.0}
        benchmark_curve = pd.DataFrame()
        timing_curve = pd.DataFrame()
    else:
        metrics = performance_metrics(equity_curve, trades)
        benchmark_source = benchmark if benchmark is not None else prices
        benchmark_curve = benchmark_buy_hold_curve(
            benchmark_source, exec_cfg.initial_capital, equity_curve.index
        )
        timing_curve = benchmark_ma_timing_curve(
            benchmark_source, exec_cfg.initial_capital, index=equity_curve.index
        )
        if not benchmark_curve.empty:
            benchmark_metrics = performance_metrics(benchmark_curve, pd.DataFrame())
            metrics["benchmark_return"] = benchmark_metrics["total_return"]
            metrics["benchmark_cagr"] = benchmark_metrics["cagr"]
            metrics["benchmark_max_drawdown"] = benchmark_metrics["max_drawdown"]
            metrics["excess_return"] = metrics["total_return"] - benchmark_metrics["total_return"]
        if not timing_curve.empty:
            timing_metrics = performance_metrics(timing_curve, pd.DataFrame())
            metrics["timing_return"] = timing_metrics["total_return"]
            metrics["timing_cagr"] = timing_metrics["cagr"]
            metrics["timing_max_drawdown"] = timing_metrics["max_drawdown"]
            metrics["excess_vs_timing"] = metrics["total_return"] - timing_metrics["total_return"]
    return WalkForwardResult(
        windows=windows_frame,
        equity_curve=equity_curve,
        trades=trades,
        metrics=metrics,
        benchmark_curve=benchmark_curve,
        timing_curve=timing_curve,
    )
