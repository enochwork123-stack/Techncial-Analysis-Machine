from __future__ import annotations

import pandas as pd

from regime_alpha.backtest import ExecutionConfig, run_long_only_backtest


def test_long_only_backtest_enters_and_exits_on_signals() -> None:
    index = pd.date_range("2024-01-01", periods=5, freq="D")
    prices = pd.DataFrame(
        {
            "open": [10, 11, 12, 13, 14],
            "high": [10, 11, 12, 13, 14],
            "low": [10, 11, 12, 13, 14],
            "close": [10, 11, 12, 13, 14],
            "volume": [100, 100, 100, 100, 100],
        },
        index=index,
    )
    signals = pd.DataFrame(
        {
            "signal_direction": [1, 0, 0, -1, 0],
            "initial_stop_loss": [float("nan")] * 5,
        },
        index=index,
    )

    result = run_long_only_backtest(
        prices,
        signals,
        ExecutionConfig(initial_capital=100_000, commission_pct=0, slippage_pct=0),
    )

    assert len(result.trades) == 1
    assert result.trades.iloc[0]["entry_price"] == 10
    assert result.trades.iloc[0]["exit_price"] == 13
    assert round(result.metrics["total_return"], 4) == 0.3


def test_long_only_backtest_respects_initial_stop_loss() -> None:
    index = pd.date_range("2024-01-01", periods=3, freq="D")
    prices = pd.DataFrame(
        {
            "open": [10, 11, 12],
            "high": [10, 11, 12],
            "low": [10, 8, 12],
            "close": [10, 11, 12],
            "volume": [100, 100, 100],
        },
        index=index,
    )
    signals = pd.DataFrame(
        {
            "signal_direction": [1, 0, 0],
            "initial_stop_loss": [9.0, float("nan"), float("nan")],
        },
        index=index,
    )

    result = run_long_only_backtest(
        prices,
        signals,
        ExecutionConfig(initial_capital=100_000, commission_pct=0, slippage_pct=0),
    )

    assert len(result.trades) == 1
    assert result.trades.iloc[0]["exit_reason"] == "stop_loss"
    assert result.trades.iloc[0]["exit_price"] == 9
    assert round(result.trades.iloc[0]["return_pct"], 4) == -0.1

