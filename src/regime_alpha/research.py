from __future__ import annotations

from collections.abc import Callable

import pandas as pd

from regime_alpha.backtest import BacktestResult, ExecutionConfig, run_long_only_backtest
from regime_alpha.strategies import (
    bollinger_mean_reversion_signals,
    donchian_breakout_signals,
    ema_cross_signals,
    macd_momentum_signals,
    pullback_continuation_signals,
    rsi_pullback_signals,
    supertrend_signals,
    volume_breakout_signals,
)


StrategyFunction = Callable[[pd.DataFrame], pd.DataFrame]


STRATEGY_FUNCTIONS: dict[str, StrategyFunction] = {
    "rsi_pullback": rsi_pullback_signals,
    "bollinger_mean_reversion": bollinger_mean_reversion_signals,
    "macd_momentum": macd_momentum_signals,
    "ema_cross": ema_cross_signals,
    "supertrend": supertrend_signals,
    "donchian_breakout": donchian_breakout_signals,
    "volume_breakout": volume_breakout_signals,
    "pullback_continuation": pullback_continuation_signals,
}


def run_strategy_suite(
    prices: pd.DataFrame,
    strategy_names: list[str] | None = None,
    execution_config: ExecutionConfig | None = None,
) -> dict[str, BacktestResult]:
    names = strategy_names or list(STRATEGY_FUNCTIONS)
    unknown = sorted(set(names) - set(STRATEGY_FUNCTIONS))
    if unknown:
        raise ValueError(f"Unknown strategies: {unknown}")

    results = {}
    for name in names:
        signals = STRATEGY_FUNCTIONS[name](prices)
        results[name] = run_long_only_backtest(prices, signals, config=execution_config)
    return results


def summarize_strategy_suite(results: dict[str, BacktestResult]) -> pd.DataFrame:
    rows = []
    for name, result in results.items():
        rows.append({"strategy": name, **result.metrics})
    if not rows:
        return pd.DataFrame()
    return pd.DataFrame(rows).sort_values(["total_return", "sharpe"], ascending=False)

