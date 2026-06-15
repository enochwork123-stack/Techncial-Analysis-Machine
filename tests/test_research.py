from __future__ import annotations

import pandas as pd

from regime_alpha.research import run_strategy_suite, summarize_strategy_suite


def test_run_strategy_suite_returns_metrics_for_selected_strategy() -> None:
    index = pd.date_range("2024-01-01", periods=260, freq="B")
    close = pd.Series(range(100, 360), index=index, dtype="float64")
    prices = pd.DataFrame(
        {
            "open": close - 0.5,
            "high": close + 1,
            "low": close - 1,
            "close": close,
            "volume": 1000,
        },
        index=index,
    )

    results = run_strategy_suite(prices, strategy_names=["ema_cross"])
    summary = summarize_strategy_suite(results)

    assert list(summary["strategy"]) == ["ema_cross"]
    assert "total_return" in summary.columns

