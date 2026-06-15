from __future__ import annotations

import argparse
from pathlib import Path

import pandas as pd

from regime_alpha.backtest import ExecutionConfig
from regime_alpha.io import load_ohlcv_file
from regime_alpha.walk_forward import WalkForwardConfig, run_walk_forward


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--symbol", required=True)
    parser.add_argument("--strategy", default="ema_cross")
    parser.add_argument("--input-dir", default="data/raw/ohlcv")
    parser.add_argument("--output-dir", default="data/processed/walk_forward")
    parser.add_argument("--train-years", type=int, default=4)
    parser.add_argument("--test-years", type=int, default=1)
    parser.add_argument("--objective", default="sharpe")
    parser.add_argument("--initial-capital", type=float, default=100_000)
    parser.add_argument("--commission-pct", type=float, default=0.001)
    parser.add_argument("--slippage-pct", type=float, default=0.0005)
    args = parser.parse_args()

    symbol = args.symbol.upper()
    prices = load_ohlcv_file(Path(args.input_dir) / f"{symbol}.csv")
    result = run_walk_forward(
        prices,
        strategy_name=args.strategy,
        config=WalkForwardConfig(
            train_years=args.train_years,
            test_years=args.test_years,
            objective=args.objective,
        ),
        execution_config=ExecutionConfig(
            initial_capital=args.initial_capital,
            commission_pct=args.commission_pct,
            slippage_pct=args.slippage_pct,
        ),
    )

    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    result.windows.to_csv(output_dir / f"{symbol}_{args.strategy}_windows.csv", index=False)
    result.equity_curve.to_csv(output_dir / f"{symbol}_{args.strategy}_equity.csv")
    result.trades.to_csv(output_dir / f"{symbol}_{args.strategy}_trades.csv", index=False)
    pd.DataFrame([result.metrics]).to_csv(output_dir / f"{symbol}_{args.strategy}_metrics.csv", index=False)

    print(pd.DataFrame([result.metrics]).to_string(index=False))
    print(result.windows.to_string(index=False))
    print(f"Wrote walk-forward outputs to {output_dir}")


if __name__ == "__main__":
    main()
