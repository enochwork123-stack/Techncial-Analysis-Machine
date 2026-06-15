from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd

from regime_alpha.backtest import TRADING_DAYS_PER_YEAR, annualized_sharpe
from regime_alpha.io import load_ohlcv_directory
from regime_alpha.research import run_strategy_suite, summarize_strategy_suite


@dataclass(frozen=True)
class BootstrapConfig:
    samples: int = 1000
    seed: int = 42
    confidence: float = 0.95


STOCK_GROUPS: dict[str, str] = {
    "AAPL": "mega_cap_platform",
    "MSFT": "mega_cap_platform",
    "GOOG": "mega_cap_platform",
    "GOOGL": "mega_cap_platform",
    "AMZN": "mega_cap_platform",
    "META": "mega_cap_platform",
    "NVDA": "semiconductor_ai",
    "AVGO": "semiconductor_ai",
    "AMD": "semiconductor_ai",
    "ASML": "semiconductor_ai",
    "AMAT": "semiconductor_ai",
    "LRCX": "semiconductor_ai",
    "MU": "semiconductor_ai",
    "INTC": "semiconductor_ai",
    "TSLA": "high_beta_growth",
    "ARM": "high_beta_growth",
    "NFLX": "consumer_growth",
    "COST": "defensive_compounder",
    "WMT": "defensive_compounder",
    "CSCO": "mature_tech",
}


def bootstrap_return_ci(
    returns: pd.Series,
    config: BootstrapConfig | None = None,
) -> dict[str, float]:
    cfg = config or BootstrapConfig()
    clean = returns.replace([np.inf, -np.inf], np.nan).dropna()
    if clean.empty:
        return {"bootstrap_mean_return": 0.0, "bootstrap_low": 0.0, "bootstrap_high": 0.0}
    rng = np.random.default_rng(cfg.seed)
    values = clean.to_numpy()
    samples = rng.choice(values, size=(cfg.samples, len(values)), replace=True)
    compounded = np.prod(1 + samples, axis=1) - 1
    alpha = (1 - cfg.confidence) / 2
    return {
        "bootstrap_mean_return": float(np.mean(compounded)),
        "bootstrap_low": float(np.quantile(compounded, alpha)),
        "bootstrap_high": float(np.quantile(compounded, 1 - alpha)),
    }


def adjusted_sharpe_haircut(sharpe: float, trials: int) -> float:
    """Simple multiple-testing haircut, not a formal Deflated Sharpe Ratio."""
    if trials <= 1:
        return float(sharpe)
    return float(sharpe - np.sqrt(2 * np.log(trials) / TRADING_DAYS_PER_YEAR))


def robustness_report(
    equity_curve: pd.DataFrame,
    trials: int = 1,
    bootstrap_config: BootstrapConfig | None = None,
) -> dict[str, float]:
    if equity_curve.empty or "equity" not in equity_curve.columns:
        return {}
    returns = equity_curve["equity"].pct_change()
    sharpe = annualized_sharpe(equity_curve["equity"])
    report = bootstrap_return_ci(returns, bootstrap_config)
    report["adjusted_sharpe_haircut"] = adjusted_sharpe_haircut(sharpe, trials)
    report["multiple_test_trials"] = float(trials)
    return report


def stock_group(symbol: str) -> str:
    return STOCK_GROUPS.get(symbol.upper(), "unclassified")


def screen_cached_strategies(
    symbols: list[str] | None = None,
    input_dir: str = "data/raw/ohlcv",
) -> pd.DataFrame:
    data = load_ohlcv_directory(symbols, input_dir=input_dir)
    rows = []
    for symbol, prices in data.items():
        summary = summarize_strategy_suite(run_strategy_suite(prices))
        if summary.empty:
            continue
        winner = summary.iloc[0].to_dict()
        winner["symbol"] = symbol
        winner["group"] = stock_group(symbol)
        rows.append(winner)
    if not rows:
        return pd.DataFrame()
    columns = ["symbol", "group", *[column for column in rows[0] if column not in {"symbol", "group"}]]
    return pd.DataFrame(rows)[columns].sort_values(["group", "total_return"], ascending=[True, False])


def group_strategy_summary(screen: pd.DataFrame) -> pd.DataFrame:
    if screen.empty:
        return pd.DataFrame()
    grouped = (
        screen.groupby(["group", "strategy"])
        .agg(
            symbols=("symbol", lambda values: ", ".join(sorted(values))),
            count=("symbol", "count"),
            median_return=("total_return", "median"),
            median_drawdown=("max_drawdown", "median"),
            median_sharpe=("sharpe", "median"),
        )
        .reset_index()
        .sort_values(["group", "count", "median_return"], ascending=[True, False, False])
    )
    return grouped


def generate_group_memos(grouped: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for _, row in grouped.iterrows():
        strategy = row["strategy"]
        group = row["group"]
        rationale = {
            "supertrend": "ATR trend following can stay with persistent directional moves while adapting exits to volatility.",
            "ema_cross": "Moving-average timing works best when regime shifts are broad and sustained.",
            "macd_momentum": "MACD favors intermediate acceleration after basing or cyclical turns.",
            "rsi_pullback": "Pullback entries suit quality compounders where dips are often bought.",
            "bollinger_mean_reversion": "Band reversion tends to suit mature names with valuation or positioning mean reversion.",
            "donchian_breakout": "Breakouts need clean expansion and can struggle in choppy leadership rotation.",
            "volume_breakout": "Volume confirmation helps when institutional accumulation accompanies price expansion.",
            "pullback_continuation": "Trend pullbacks aim to enter established trends without chasing highs.",
        }.get(strategy, "Review the trade log and regime context before assigning a causal explanation.")
        rows.append(
            {
                "group": group,
                "strategy": strategy,
                "symbols": row["symbols"],
                "memo": rationale,
            }
        )
    return pd.DataFrame(rows)

