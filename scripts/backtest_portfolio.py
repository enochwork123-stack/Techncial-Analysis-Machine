from __future__ import annotations

import argparse
from pathlib import Path

import pandas as pd

from regime_alpha.io import load_ohlcv_directory
from regime_alpha.portfolio import PortfolioConfig, run_portfolio_backtest


def parse_symbols(value: str) -> list[str] | None:
    symbols = [item.strip().upper() for item in value.split(",") if item.strip()]
    return symbols or None


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--symbols", default="", help="Comma-separated symbols. Empty means all cached.")
    parser.add_argument("--strategy", default="ema_cross")
    parser.add_argument("--input-dir", default="data/raw/ohlcv")
    parser.add_argument("--output-dir", default="data/processed/portfolio")
    parser.add_argument("--initial-capital", type=float, default=100_000)
    parser.add_argument("--risk-per-trade", type=float, default=0.01)
    parser.add_argument("--max-portfolio-heat", type=float, default=0.20)
    parser.add_argument("--max-positions", type=int, default=20)
    parser.add_argument("--max-position-pct", type=float, default=0.20)
    parser.add_argument("--commission-pct", type=float, default=0.001)
    parser.add_argument("--slippage-pct", type=float, default=0.0005)
    parser.add_argument("--disable-correlation-filter", action="store_true")
    parser.add_argument("--execution-timing", choices=["close", "next_open"], default="close")
    parser.add_argument("--benchmark-symbol", default="")
    args = parser.parse_args()

    price_data = load_ohlcv_directory(parse_symbols(args.symbols), input_dir=args.input_dir)
    if not price_data:
        raise SystemExit(f"No OHLCV files found in {args.input_dir}")

    config = PortfolioConfig(
        initial_capital=args.initial_capital,
        risk_per_trade=args.risk_per_trade,
        max_portfolio_heat=args.max_portfolio_heat,
        max_positions=args.max_positions,
        max_position_pct=args.max_position_pct,
        commission_pct=args.commission_pct,
        slippage_pct=args.slippage_pct,
        use_correlation_filter=not args.disable_correlation_filter,
        execution_timing=args.execution_timing,
    )
    benchmark = None
    if args.benchmark_symbol:
        benchmark_data = load_ohlcv_directory([args.benchmark_symbol.upper()], input_dir=args.input_dir)
        benchmark = benchmark_data.get(args.benchmark_symbol.upper())
    result = run_portfolio_backtest(
        price_data, strategy_name=args.strategy, config=config, benchmark=benchmark
    )

    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    result.equity_curve.to_csv(output_dir / "equity_curve.csv")
    result.trades.to_csv(output_dir / "trades.csv", index=False)
    result.positions.to_csv(output_dir / "positions.csv", index=False)
    result.benchmark_curve.to_csv(output_dir / "benchmark_curve.csv")
    pd.DataFrame([result.metrics]).to_csv(output_dir / "metrics.csv", index=False)

    print(pd.DataFrame([result.metrics]).to_string(index=False))
    print(f"Wrote portfolio outputs to {output_dir}")


if __name__ == "__main__":
    main()
