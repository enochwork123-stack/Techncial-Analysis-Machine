from __future__ import annotations

import argparse
import json
from pathlib import Path

import pandas as pd

from regime_alpha.backtest import ExecutionConfig, run_long_only_backtest
from regime_alpha.io import load_ohlcv_file
from regime_alpha.strategies import (
    bollinger_mean_reversion_signals,
    donchian_breakout_signals,
    ema_cross_signals,
    macd_momentum_signals,
    rsi_pullback_signals,
    supertrend_signals,
)


MCP_STRATEGIES = {
    "ema_cross": ema_cross_signals,
    "supertrend": supertrend_signals,
    "donchian": donchian_breakout_signals,
    "macd": macd_momentum_signals,
    "rsi": rsi_pullback_signals,
    "bollinger": bollinger_mean_reversion_signals,
}


def _load_mcp_results(path: Path) -> list[dict[str, object]]:
    with path.open() as file:
        return json.load(file)


def _local_result(
    symbol: str,
    strategy: str,
    data_dir: Path,
    date_from: str,
    date_to: str,
    initial_capital: float,
    commission_pct: float,
    slippage_pct: float,
) -> dict[str, float]:
    prices = load_ohlcv_file(data_dir / f"{symbol}.csv")
    window = prices.loc[
        (prices.index >= pd.Timestamp(date_from)) & (prices.index <= pd.Timestamp(date_to))
    ]
    signals = MCP_STRATEGIES[strategy](window)
    result = run_long_only_backtest(
        window,
        signals,
        ExecutionConfig(
            initial_capital=initial_capital,
            commission_pct=commission_pct,
            slippage_pct=slippage_pct,
        ),
    )
    buy_hold = window["close"].iloc[-1] / window["close"].iloc[0] - 1
    return {
        "local_total_return_pct": result.metrics["total_return"] * 100,
        "local_max_drawdown_pct": result.metrics["max_drawdown"] * 100,
        "local_sharpe": result.metrics["sharpe"],
        "local_profit_factor": result.metrics["profit_factor"],
        "local_win_rate_pct": result.metrics["win_rate"] * 100,
        "local_trades": result.metrics["number_of_trades"],
        "local_buy_hold_pct": buy_hold * 100,
    }


def build_comparison(
    mcp_results: list[dict[str, object]],
    raw_data_dir: Path,
    adjusted_data_dir: Path,
) -> pd.DataFrame:
    rows = []
    for item in mcp_results:
        symbol = str(item["symbol"])
        strategy = str(item["strategy"])
        if strategy not in MCP_STRATEGIES:
            continue

        args = {
            "symbol": symbol,
            "strategy": strategy,
            "date_from": str(item["date_from"]),
            "date_to": str(item["date_to"]),
            "initial_capital": float(item["initial_capital"]),
            # MCP uses percent units, local config uses decimal units.
            "commission_pct": float(item["commission_pct"]) / 100,
            "slippage_pct": float(item["slippage_pct"]) / 100,
        }
        raw = _local_result(data_dir=raw_data_dir, **args)
        adjusted = _local_result(data_dir=adjusted_data_dir, **args)
        rows.append(
            {
                "symbol": symbol,
                "strategy": strategy,
                "date_from": item["date_from"],
                "date_to": item["date_to"],
                "mcp_total_return_pct": item["total_return_pct"],
                "raw_total_return_pct": raw["local_total_return_pct"],
                "adjusted_total_return_pct": adjusted["local_total_return_pct"],
                "mcp_max_drawdown_pct": item["max_drawdown_pct"],
                "raw_max_drawdown_pct": raw["local_max_drawdown_pct"],
                "adjusted_max_drawdown_pct": adjusted["local_max_drawdown_pct"],
                "mcp_sharpe": item["sharpe_ratio"],
                "raw_sharpe": raw["local_sharpe"],
                "adjusted_sharpe": adjusted["local_sharpe"],
                "mcp_profit_factor": item["profit_factor"],
                "raw_profit_factor": raw["local_profit_factor"],
                "adjusted_profit_factor": adjusted["local_profit_factor"],
                "mcp_win_rate_pct": item["win_rate_pct"],
                "raw_win_rate_pct": raw["local_win_rate_pct"],
                "adjusted_win_rate_pct": adjusted["local_win_rate_pct"],
                "mcp_trades": item["total_trades"],
                "raw_trades": raw["local_trades"],
                "adjusted_trades": adjusted["local_trades"],
                "mcp_buy_hold_pct": item["buy_and_hold_return_pct"],
                "raw_buy_hold_pct": raw["local_buy_hold_pct"],
                "adjusted_buy_hold_pct": adjusted["local_buy_hold_pct"],
                "raw_return_diff_pct": raw["local_total_return_pct"]
                - float(item["total_return_pct"]),
                "adjusted_return_diff_pct": adjusted["local_total_return_pct"]
                - float(item["total_return_pct"]),
            }
        )
    return pd.DataFrame(rows)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--mcp-results",
        default="data/processed/calibration/mcp_backtest_strategy_goog_nvda_2y.json",
    )
    parser.add_argument("--raw-data-dir", default="data/processed/calibration/raw_ohlcv")
    parser.add_argument("--adjusted-data-dir", default="data/raw/ohlcv")
    parser.add_argument("--output", default="data/processed/calibration/mcp_vs_local_comparison.csv")
    args = parser.parse_args()

    comparison = build_comparison(
        _load_mcp_results(Path(args.mcp_results)),
        raw_data_dir=Path(args.raw_data_dir),
        adjusted_data_dir=Path(args.adjusted_data_dir),
    )
    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    comparison.to_csv(output, index=False)
    print(comparison.to_string(index=False))


if __name__ == "__main__":
    main()
