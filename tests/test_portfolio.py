from __future__ import annotations

import pandas as pd

from regime_alpha.portfolio import PortfolioConfig, run_portfolio_backtest


def _trending_prices(start: float, length: int = 260) -> pd.DataFrame:
    index = pd.date_range("2024-01-01", periods=length, freq="B")
    close = pd.Series([start + i * 0.5 for i in range(length)], index=index)
    return pd.DataFrame(
        {
            "open": close - 0.2,
            "high": close + 0.5,
            "low": close - 0.5,
            "close": close,
            "volume": 100_000,
        },
        index=index,
    )


def test_portfolio_backtest_returns_equity_and_metrics() -> None:
    price_data = {
        "AAA": _trending_prices(100),
        "BBB": _trending_prices(50),
    }
    result = run_portfolio_backtest(
        price_data,
        strategy_name="ema_cross",
        config=PortfolioConfig(
            initial_capital=100_000,
            max_positions=2,
            use_correlation_filter=False,
            commission_pct=0,
            slippage_pct=0,
        ),
    )

    assert not result.equity_curve.empty
    assert "total_return" in result.metrics
    assert result.equity_curve["open_positions"].max() <= 2


def test_portfolio_supports_next_open_and_benchmark_metrics() -> None:
    price_data = {"AAA": _trending_prices(100)}
    benchmark = _trending_prices(80)
    result = run_portfolio_backtest(
        price_data,
        strategy_name="ema_cross",
        benchmark=benchmark,
        config=PortfolioConfig(
            initial_capital=100_000,
            execution_timing="next_open",
            use_correlation_filter=False,
            commission_pct=0,
            slippage_pct=0,
        ),
    )

    assert "benchmark_return" in result.metrics
    assert "annual_turnover" in result.metrics
    assert not result.benchmark_curve.empty


def test_portfolio_rejects_unknown_strategy() -> None:
    try:
        run_portfolio_backtest({"AAA": _trending_prices(100)}, strategy_name="unknown")
    except ValueError as exc:
        assert "Unknown strategy" in str(exc)
    else:
        raise AssertionError("Expected unknown strategy to raise ValueError")


def test_portfolio_rejects_bad_execution_timing() -> None:
    try:
        run_portfolio_backtest(
            {"AAA": _trending_prices(100)},
            strategy_name="ema_cross",
            config=PortfolioConfig(execution_timing="bad"),
        )
    except ValueError as exc:
        assert "execution_timing" in str(exc)
    else:
        raise AssertionError("Expected bad execution timing to raise ValueError")
