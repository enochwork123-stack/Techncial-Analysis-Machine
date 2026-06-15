from __future__ import annotations

import pandas as pd

from regime_alpha.robustness import (
    adjusted_sharpe_haircut,
    bootstrap_return_ci,
    generate_group_memos,
    group_strategy_summary,
    stock_group,
)


def test_bootstrap_return_ci_and_sharpe_haircut() -> None:
    returns = pd.Series([0.01, -0.005, 0.002, 0.004])
    report = bootstrap_return_ci(returns)

    assert "bootstrap_low" in report
    assert adjusted_sharpe_haircut(1.0, trials=10) < 1.0


def test_group_summary_and_memos() -> None:
    screen = pd.DataFrame(
        {
            "symbol": ["GOOG", "MSFT", "NVDA"],
            "group": ["mega_cap_platform", "mega_cap_platform", "semiconductor_ai"],
            "strategy": ["ema_cross", "ema_cross", "supertrend"],
            "total_return": [1.0, 0.5, 2.0],
            "max_drawdown": [-0.2, -0.1, -0.3],
            "sharpe": [1.0, 0.8, 1.2],
        }
    )

    grouped = group_strategy_summary(screen)
    memos = generate_group_memos(grouped)

    assert stock_group("GOOG") == "mega_cap_platform"
    assert not grouped.empty
    assert not memos.empty
