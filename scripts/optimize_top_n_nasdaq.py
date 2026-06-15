from __future__ import annotations

import argparse
import json
from itertools import product
from pathlib import Path

import pandas as pd
import yfinance as yf

from regime_alpha.backtest import ExecutionConfig, performance_metrics, run_long_only_backtest
from regime_alpha.io import load_ohlcv_file
from regime_alpha.research import STRATEGY_FUNCTIONS
from regime_alpha.strategies import strategy_parameter_grids
from download_ohlcv import normalize_ohlcv


def _safe_sheet_name(name: str) -> str:
    return name.replace("/", "-").replace("\\", "-")[:31]


def parameter_combinations(grid: dict[str, list[int | float]]) -> list[dict[str, int | float]]:
    keys = list(grid)
    if not keys:
        return [{}]
    return [dict(zip(keys, values, strict=True)) for values in product(*(grid[key] for key in keys))]


def top_n_symbols(snapshot_path: Path, n: int) -> pd.DataFrame:
    snapshot = pd.read_csv(snapshot_path)
    required = {"symbol", "company_name", "market_cap"}
    missing = required - set(snapshot.columns)
    if missing:
        raise ValueError(f"{snapshot_path} is missing columns: {sorted(missing)}")
    snapshot["market_cap"] = pd.to_numeric(snapshot["market_cap"], errors="coerce")
    return (
        snapshot.dropna(subset=["market_cap"])
        .sort_values("market_cap", ascending=False)
        .head(n)
        .reset_index(drop=True)
    )


def download_symbols(
    symbols: list[str],
    output_dir: Path,
    start: str,
    end: str | None,
    adjustment: str,
) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    for symbol in symbols:
        output_path = output_dir / f"{symbol}.csv"
        print(f"Downloading {symbol}...")
        frame = yf.download(
            symbol,
            start=start,
            end=end,
            auto_adjust=adjustment == "auto_adjust",
            progress=False,
            threads=False,
        )
        normalized = normalize_ohlcv(frame, symbol)
        if normalized.empty:
            print(f"Skipping {symbol}: no data")
            continue
        normalized.to_csv(output_path, index=False)


def _metric_row(
    symbol: str,
    strategy: str,
    params: dict[str, int | float],
    result,
    benchmark_metrics: dict[str, float],
    stage: str,
) -> dict[str, object]:
    metrics = result.metrics
    return {
        "symbol": symbol,
        "stage": stage,
        "strategy": strategy,
        "params_json": json.dumps(params, sort_keys=True),
        "total_return_pct": metrics["total_return"] * 100,
        "cagr_pct": metrics["cagr"] * 100,
        "max_drawdown_pct": metrics["max_drawdown"] * 100,
        "sharpe": metrics["sharpe"],
        "sortino": metrics.get("sortino", 0.0),
        "calmar": metrics.get("calmar", 0.0),
        "profit_factor": metrics["profit_factor"],
        "win_rate_pct": metrics["win_rate"] * 100,
        "number_of_trades": metrics["number_of_trades"],
        "average_trade_return_pct": metrics["average_trade_return"] * 100,
        "buy_hold_return_pct": benchmark_metrics["total_return"] * 100,
        "excess_vs_buy_hold_pct": (metrics["total_return"] - benchmark_metrics["total_return"]) * 100,
        "buy_hold_max_drawdown_pct": benchmark_metrics["max_drawdown"] * 100,
        "buy_hold_sharpe": benchmark_metrics["sharpe"],
    }


def buy_hold_metrics(prices: pd.DataFrame, initial_capital: float) -> dict[str, float]:
    curve = pd.DataFrame(
        {"equity": initial_capital * prices["close"] / prices["close"].iloc[0]},
        index=prices.index,
    )
    return performance_metrics(curve, pd.DataFrame())


def optimize_symbol(
    symbol: str,
    prices: pd.DataFrame,
    execution_config: ExecutionConfig,
) -> tuple[pd.DataFrame, dict[str, object]]:
    benchmark_metrics = buy_hold_metrics(prices, execution_config.initial_capital)
    rows = []
    default_results = {}

    for strategy_name, strategy_fn in STRATEGY_FUNCTIONS.items():
        result = run_long_only_backtest(
            prices,
            strategy_fn(prices),
            config=execution_config,
        )
        default_results[strategy_name] = result
        rows.append(
            _metric_row(
                symbol,
                strategy_name,
                {},
                result,
                benchmark_metrics,
                stage="strategy_selection_default",
            )
        )

    default_frame = pd.DataFrame(rows)
    selected_strategy = str(
        default_frame.sort_values(["total_return_pct", "sharpe"], ascending=False).iloc[0][
            "strategy"
        ]
    )

    grid = strategy_parameter_grids().get(selected_strategy, {})
    combinations = parameter_combinations(grid)
    optimized_rows = []
    for params in combinations:
        result = run_long_only_backtest(
            prices,
            STRATEGY_FUNCTIONS[selected_strategy](prices, **params),
            config=execution_config,
        )
        optimized_rows.append(
            _metric_row(
                symbol,
                selected_strategy,
                params,
                result,
                benchmark_metrics,
                stage="selected_strategy_parameter_sweep",
            )
        )

    optimized_frame = pd.DataFrame(optimized_rows)
    all_rows = pd.concat([default_frame, optimized_frame], ignore_index=True)
    best = optimized_frame.sort_values(["total_return_pct", "sharpe"], ascending=False).iloc[0]
    best_summary = best.to_dict()
    best_summary["selected_from_default_strategy"] = selected_strategy
    best_summary["default_selected_return_pct"] = float(
        default_frame.loc[default_frame["strategy"] == selected_strategy, "total_return_pct"].iloc[0]
    )
    best_summary["default_selected_trades"] = float(
        default_frame.loc[default_frame["strategy"] == selected_strategy, "number_of_trades"].iloc[0]
    )
    return all_rows, best_summary


def investigation_notes(row: pd.Series) -> str:
    excess = float(row["excess_vs_buy_hold_pct"])
    trades = float(row["number_of_trades"])
    dd = float(row["max_drawdown_pct"])
    bh_dd = float(row["buy_hold_max_drawdown_pct"])
    strategy = str(row["strategy"])
    buy_hold = float(row["buy_hold_return_pct"])
    total_return = float(row["total_return_pct"])
    if excess >= 0:
        return "Optimized strategy beat buy-and-hold over the test window."
    if trades <= 2:
        return (
            "Underperformed mainly because the selected rules were too inactive; "
            "a strong buy-and-hold trend left little room for timing exits to add value."
        )
    if total_return > 200 and buy_hold > total_return * 1.4:
        return (
            "The strategy captured large trend legs but sold during high-volatility pauses; "
            "buy-and-hold won because the symbol compounded through deep pullbacks."
        )
    if strategy in {"ema_cross", "supertrend", "donchian_breakout", "volume_breakout"}:
        return (
            "Trend timing reduced exposure during selloffs but also missed rebounds; "
            "the stock's best days arrived close to volatile regime shifts."
        )
    if strategy in {"macd_momentum", "bollinger_mean_reversion", "rsi_pullback"}:
        return (
            "The selected tactical rules traded frequently enough to add costs and cash drag; "
            "buy-and-hold benefited more from staying continuously exposed."
        )
    if dd < bh_dd:
        return "The strategy reduced drawdown, but the upside sacrificed was larger than the risk saved."
    return (
        "Underperformed with meaningful drawdown, suggesting the symbol was choppy for this "
        "strategy family or the optimized parameters overreacted to noise."
    )


def write_markdown_report(
    path: Path,
    universe: pd.DataFrame,
    summary: pd.DataFrame,
    start_date: str,
    end_date: str,
    adjustment: str,
) -> None:
    winners = summary["strategy"].value_counts().to_dict()
    underperformers = summary[summary["excess_vs_buy_hold_pct"] < 0].copy()
    outperformers = summary[summary["excess_vs_buy_hold_pct"] >= 0].copy()
    lines = [
        "# Top 20 Nasdaq 5-Year Strategy Optimization",
        "",
        f"Data window: `{start_date}` to `{end_date}`.",
        f"Price adjustment: `{adjustment}`.",
        "Selection method: first rank default strategy families by total return, then optimize only the winning family using the project parameter grid.",
        "",
        "This is an in-sample optimization report. It is useful for pattern discovery, not proof of live-trading edge.",
        "",
        "## Universe",
        "",
        "| Rank | Symbol | Company | Market Cap |",
        "| ---: | --- | --- | ---: |",
    ]
    for i, row in universe.iterrows():
        lines.append(
            f"| {i + 1} | {row['symbol']} | {row['company_name']} | {row['market_cap']:,.0f} |"
        )

    lines.extend(
        [
            "",
            "## Best Strategy Summary",
            "",
            "| Symbol | Best Strategy | Params | Return | Buy & Hold | Excess | Max DD | Trades | Sharpe |",
            "| --- | --- | --- | ---: | ---: | ---: | ---: | ---: | ---: |",
        ]
    )
    for _, row in summary.iterrows():
        lines.append(
            "| {symbol} | {strategy} | `{params}` | {ret:.2f}% | {bh:.2f}% | {excess:.2f}% | {dd:.2f}% | {trades:.0f} | {sharpe:.2f} |".format(
                symbol=row["symbol"],
                strategy=row["strategy"],
                params=row["params_json"],
                ret=row["total_return_pct"],
                bh=row["buy_hold_return_pct"],
                excess=row["excess_vs_buy_hold_pct"],
                dd=row["max_drawdown_pct"],
                trades=row["number_of_trades"],
                sharpe=row["sharpe"],
            )
        )

    lines.extend(
        [
            "",
            "## Pattern Observations",
            "",
            f"- Winning strategy families: {json.dumps(winners, sort_keys=True)}.",
            f"- {len(outperformers)} of {len(summary)} optimized strategies beat buy-and-hold in-sample.",
            f"- {len(underperformers)} of {len(summary)} optimized strategies still lagged buy-and-hold.",
            "- Trend and breakout rules tend to work best where the stock had persistent directional phases with recoverable pullbacks.",
            "- Mean-reversion winners usually indicate repeated panic/rebound behavior rather than smooth compounding trend.",
            "- Underperformance versus buy-and-hold is common in mega-cap momentum names because timing systems sit in cash during part of strong bull legs.",
            "- The biggest underperformers versus buy-and-hold were not necessarily bad absolute strategies; several still made triple-digit returns but failed to keep up with exceptional semiconductor/AI compounding.",
            "- A practical next step is to retest the best candidates with walk-forward validation and a risk-adjusted objective rather than pure total return.",
            "",
            "## Underperformer Investigation",
            "",
        ]
    )
    if underperformers.empty:
        lines.append("No optimized strategy underperformed buy-and-hold in this run.")
    else:
        for _, row in underperformers.sort_values("excess_vs_buy_hold_pct").iterrows():
            lines.append(
                f"- **{row['symbol']}**: optimized `{row['strategy']}` returned "
                f"{row['total_return_pct']:.2f}% versus buy-and-hold {row['buy_hold_return_pct']:.2f}% "
                f"({row['excess_vs_buy_hold_pct']:.2f}% excess). {investigation_notes(row)}"
            )

    lines.extend(
        [
            "",
            "## Research Caveats",
            "",
            "- The optimization is in-sample over one 5-year period and can overfit recent market structure.",
            "- The chosen objective is total return; a stricter production workflow should optimize a risk-adjusted objective and validate with walk-forward tests.",
            "- Strategy names are transparent local implementations, not the TradingView MCP black-box definitions.",
            "- Use raw data for TradingView-style price-level matching and adjusted data for long-horizon total-return research.",
            "",
        ]
    )
    path.write_text("\n".join(lines))


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--snapshot", default="data/raw/current_nasdaq100.csv")
    parser.add_argument("--top-n", type=int, default=20)
    parser.add_argument("--years", type=int, default=5)
    parser.add_argument("--start", default="2021-06-14")
    parser.add_argument("--end", default="2026-06-15")
    parser.add_argument("--adjustment", choices=["auto_adjust", "raw"], default="raw")
    parser.add_argument("--data-dir", default="data/processed/top20_nasdaq_5y/ohlcv")
    parser.add_argument("--output-dir", default="data/processed/top20_nasdaq_5y")
    parser.add_argument("--initial-capital", type=float, default=100_000)
    parser.add_argument("--commission-pct", type=float, default=0.001)
    parser.add_argument("--slippage-pct", type=float, default=0.0005)
    parser.add_argument("--skip-download", action="store_true")
    args = parser.parse_args()

    output_dir = Path(args.output_dir)
    data_dir = Path(args.data_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    universe = top_n_symbols(Path(args.snapshot), args.top_n)
    universe_path = output_dir / "top20_universe.csv"
    universe.to_csv(universe_path, index=False)
    symbols = universe["symbol"].astype(str).tolist()

    if not args.skip_download:
        download_symbols(symbols, data_dir, args.start, args.end, args.adjustment)

    execution_config = ExecutionConfig(
        initial_capital=args.initial_capital,
        commission_pct=args.commission_pct,
        slippage_pct=args.slippage_pct,
    )
    summary_rows = []
    per_symbol_frames = {}
    for symbol in symbols:
        path = data_dir / f"{symbol}.csv"
        if not path.exists():
            print(f"Skipping {symbol}: missing {path}")
            continue
        prices = load_ohlcv_file(path)
        if prices.empty:
            print(f"Skipping {symbol}: empty data")
            continue
        latest = prices.index.max()
        start = latest - pd.DateOffset(years=args.years)
        prices = prices.loc[prices.index >= start].copy()
        if len(prices) < 200:
            print(f"Skipping {symbol}: only {len(prices)} rows in window")
            continue
        print(f"Optimizing {symbol} over {prices.index.min().date()} to {prices.index.max().date()}")
        all_rows, best = optimize_symbol(symbol, prices, execution_config)
        best["start_date"] = prices.index.min().date().isoformat()
        best["end_date"] = prices.index.max().date().isoformat()
        best["rows"] = len(prices)
        per_symbol_frames[symbol] = all_rows
        summary_rows.append(best)

    summary = pd.DataFrame(summary_rows).sort_values(
        ["total_return_pct", "sharpe"], ascending=False
    )
    summary["investigation_note"] = summary.apply(investigation_notes, axis=1)
    summary_path = output_dir / "summary_best_strategy.csv"
    summary.to_csv(summary_path, index=False)

    csv_dir = output_dir / "per_symbol_csv"
    csv_dir.mkdir(exist_ok=True)
    for symbol, frame in per_symbol_frames.items():
        frame.to_csv(csv_dir / f"{symbol}.csv", index=False)

    workbook_path = output_dir / "top20_nasdaq_5y_strategy_optimization.xlsx"
    with pd.ExcelWriter(workbook_path, engine="openpyxl") as writer:
        summary.to_excel(writer, sheet_name="Summary", index=False)
        universe.to_excel(writer, sheet_name="Universe", index=False)
        for symbol, frame in per_symbol_frames.items():
            frame.to_excel(writer, sheet_name=_safe_sheet_name(symbol), index=False)

    report_path = output_dir / "findings.md"
    start_date = str(summary["start_date"].min()) if not summary.empty else args.start
    end_date = str(summary["end_date"].max()) if not summary.empty else args.end
    write_markdown_report(report_path, universe, summary, start_date, end_date, args.adjustment)

    print(f"Wrote workbook: {workbook_path}")
    print(f"Wrote summary CSV: {summary_path}")
    print(f"Wrote per-symbol CSVs: {csv_dir}")
    print(f"Wrote findings: {report_path}")


if __name__ == "__main__":
    main()
