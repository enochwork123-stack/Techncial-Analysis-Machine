from __future__ import annotations

import pandas as pd

from regime_alpha.walk_forward import (
    WalkForwardConfig,
    benchmark_buy_hold_curve,
    benchmark_ma_timing_curve,
    parameter_combinations,
    run_walk_forward,
    walk_forward_windows,
)


def _prices(length: int = 1600) -> pd.DataFrame:
    index = pd.date_range("2015-01-01", periods=length, freq="B")
    close = pd.Series([100 + i * 0.05 for i in range(length)], index=index)
    return pd.DataFrame(
        {
            "open": close - 0.1,
            "high": close + 0.4,
            "low": close - 0.4,
            "close": close,
            "volume": 100_000,
        },
        index=index,
    )


def test_parameter_combinations_expands_grid() -> None:
    combos = parameter_combinations({"fast": [5, 10], "slow": [20, 30]})

    assert len(combos) == 4
    assert {"fast": 5, "slow": 20} in combos


def test_walk_forward_windows_are_generated() -> None:
    prices = _prices()
    windows = walk_forward_windows(prices.index, train_years=2, test_years=1)

    assert windows
    assert windows[0][0] < windows[0][1] < windows[0][2] < windows[0][3]


def test_run_walk_forward_returns_window_summary() -> None:
    result = run_walk_forward(
        _prices(),
        strategy_name="ema_cross",
        config=WalkForwardConfig(
            train_years=2,
            test_years=1,
            min_train_trades=0,
            selection_mode="plateau",
        ),
        parameter_grid={"fast_window": [5], "slow_window": [20]},
    )

    assert not result.windows.empty
    assert "total_return" in result.metrics
    assert "benchmark_return" in result.metrics
    assert "timing_return" in result.metrics
    assert not result.benchmark_curve.empty


def test_benchmark_curves_are_generated() -> None:
    prices = _prices()
    buy_hold = benchmark_buy_hold_curve(prices, 100_000)
    timing = benchmark_ma_timing_curve(prices, 100_000, ma_window=20)

    assert not buy_hold.empty
    assert not timing.empty
    assert buy_hold["equity"].iloc[0] == 100_000
