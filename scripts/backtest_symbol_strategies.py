from __future__ import annotations

import argparse
from pathlib import Path

import pandas as pd

from regime_alpha.backtest import ExecutionConfig
from regime_alpha.data_quality import normalize_ohlcv_schema
from regime_alpha.research import run_strategy_suite, summarize_strategy_suite


def load_prices(path: Path) -> pd.DataFrame:
    frame = normalize_ohlcv_schema(pd.read_csv(path))
    if "date" not in frame.columns:
        raise ValueError(f"{path} must contain a date column")
    return frame.sort_values("date").set_index("date")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--symbol", required=True)
    parser.add_argument("--input-dir", default="data/raw/ohlcv")
    parser.add_argument("--output", default="")
    parser.add_argument("--initial-capital", type=float, default=100_000)
    parser.add_argument("--commission-pct", type=float, default=0.001)
    parser.add_argument("--slippage-pct", type=float, default=0.0005)
    args = parser.parse_args()

    symbol = args.symbol.upper()
    prices = load_prices(Path(args.input_dir) / f"{symbol}.csv")
    config = ExecutionConfig(
        initial_capital=args.initial_capital,
        commission_pct=args.commission_pct,
        slippage_pct=args.slippage_pct,
    )
    results = run_strategy_suite(prices, execution_config=config)
    summary = summarize_strategy_suite(results)

    if args.output:
        output = Path(args.output)
        output.parent.mkdir(parents=True, exist_ok=True)
        summary.to_csv(output, index=False)
    print(summary.to_string(index=False))


if __name__ == "__main__":
    main()
