from __future__ import annotations

import argparse
import json
from itertools import product
from pathlib import Path

import pandas as pd
import yfinance as yf

from regime_alpha.backtest import annualized_sharpe, max_drawdown
from regime_alpha.io import load_ohlcv_file
from regime_alpha.research import STRATEGY_FUNCTIONS
from regime_alpha.strategies import strategy_parameter_grids
from download_ohlcv import normalize_ohlcv


SYMBOLS = [
    "NVDA",
    "GOOGL",
    "GOOG",
    "AAPL",
    "MSFT",
    "AMZN",
    "AVGO",
    "TSLA",
    "META",
    "MU",
    "WMT",
    "AMD",
    "ASML",
    "INTC",
    "CSCO",
    "LRCX",
    "AMAT",
    "COST",
    "ARM",
    "NFLX",
]


def _safe_sheet_name(name: str) -> str:
    return name.replace("/", "-").replace("\\", "-")[:31]


def parameter_combinations(grid: dict[str, list[int | float]]) -> list[dict[str, int | float]]:
    keys = list(grid)
    if not keys:
        return [{}]
    return [dict(zip(keys, values, strict=True)) for values in product(*(grid[key] for key in keys))]


def download_symbols(
    symbols: list[str],
    output_dir: Path,
    start: str,
    end: str | None,
    adjustment: str,
) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    for symbol in symbols:
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
        normalized.to_csv(output_dir / f"{symbol}.csv", index=False)


def first_trading_days_by_month(index: pd.DatetimeIndex) -> set[pd.Timestamp]:
    dates = pd.Series(index=index, data=index)
    return set(dates.groupby(index.to_period("M")).first())


def signal_state(signals: pd.DataFrame) -> pd.Series:
    state = pd.Series(0, index=signals.index, dtype="int8")
    current = 0
    for date, row in signals.iterrows():
        direction = int(row["signal_direction"])
        if direction > 0:
            current = 1
        elif direction < 0:
            current = -1
        state.loc[date] = current
    return state


def xirr(cash_flows: list[tuple[pd.Timestamp, float]]) -> float:
    if not cash_flows:
        return 0.0
    if not any(value < 0 for _, value in cash_flows) or not any(value > 0 for _, value in cash_flows):
        return 0.0
    start = cash_flows[0][0]

    def npv(rate: float) -> float:
        total = 0.0
        for date, value in cash_flows:
            years = (date - start).days / 365.25
            total += value / ((1 + rate) ** years)
        return total

    low, high = -0.9999, 10.0
    low_npv, high_npv = npv(low), npv(high)
    while low_npv * high_npv > 0 and high < 1_000:
        high *= 2
        high_npv = npv(high)
    if low_npv * high_npv > 0:
        return 0.0
    for _ in range(100):
        mid = (low + high) / 2
        mid_npv = npv(mid)
        if abs(mid_npv) < 1e-6:
            return mid
        if low_npv * mid_npv <= 0:
            high = mid
            high_npv = mid_npv
        else:
            low = mid
            low_npv = mid_npv
    return (low + high) / 2


def _buy_with_cash(
    cash: float,
    price: float,
    commission_pct: float,
    slippage_pct: float,
) -> tuple[float, float, float]:
    if cash <= 0:
        return 0.0, cash, 0.0
    fill_price = price * (1 + slippage_pct)
    trade_value = cash / (1 + commission_pct)
    commission = trade_value * commission_pct
    shares = trade_value / fill_price
    return shares, 0.0, commission


def _sell_shares(
    shares: float,
    price: float,
    commission_pct: float,
    slippage_pct: float,
    sell_fraction: float,
) -> tuple[float, float, float]:
    shares_to_sell = shares * sell_fraction
    if shares_to_sell <= 0:
        return shares, 0.0, 0.0
    fill_price = price * (1 - slippage_pct)
    gross = shares_to_sell * fill_price
    commission = gross * commission_pct
    return shares - shares_to_sell, gross - commission, commission


def run_dca_backtest(
    prices: pd.DataFrame,
    monthly_contribution: float,
    commission_pct: float,
    slippage_pct: float,
    timing_state: pd.Series | None = None,
    entry_signal: pd.Series | None = None,
    monthly_immediate_pct: float = 1.0,
    reserve_pct: float = 0.0,
    deploy_rule: str = "always",
    allow_sell: bool = False,
    sell_fraction: float = 1.0,
    cash_yield: float = 0.0,
) -> tuple[pd.DataFrame, pd.DataFrame, dict[str, float]]:
    if not 0 <= monthly_immediate_pct <= 1:
        raise ValueError("monthly_immediate_pct must be in [0, 1]")
    if not 0 <= reserve_pct <= 1:
        raise ValueError("reserve_pct must be in [0, 1]")
    if round(monthly_immediate_pct + reserve_pct, 10) != 1:
        raise ValueError("monthly_immediate_pct and reserve_pct must sum to 1")
    if deploy_rule not in {"always", "bullish_state", "entry_signal"}:
        raise ValueError("deploy_rule must be 'always', 'bullish_state', or 'entry_signal'")

    monthly_dates = first_trading_days_by_month(prices.index)
    cash = 0.0
    shares = 0.0
    total_contributed = 0.0
    total_commission = 0.0
    contribution_count = 0
    buy_count = 0
    sell_count = 0
    cash_flows: list[tuple[pd.Timestamp, float]] = []
    rows = []
    trades = []
    previous_date: pd.Timestamp | None = None
    state = (
        timing_state.reindex(prices.index).ffill().fillna(0).astype(int)
        if timing_state is not None
        else None
    )
    entries = (
        entry_signal.reindex(prices.index).fillna(False).astype(bool)
        if entry_signal is not None
        else pd.Series(False, index=prices.index)
    )

    for date, row in prices.iterrows():
        close = float(row["close"])
        if previous_date is not None and cash_yield:
            days = (date - previous_date).days
            cash *= (1 + cash_yield) ** (days / 365.25)
        previous_date = date

        technical_state = 1 if state is None else int(state.loc[date])
        if allow_sell and state is not None and shares > 0 and technical_state < 0:
            old_shares = shares
            shares, proceeds, commission = _sell_shares(
                shares, close, commission_pct, slippage_pct, sell_fraction
            )
            cash += proceeds
            total_commission += commission
            sell_count += 1
            trades.append(
                {
                    "date": date,
                    "action": "sell",
                    "price": close,
                    "shares": old_shares - shares,
                    "cash_after": cash,
                    "technical_state": technical_state,
                    "commission": commission,
                }
            )

        if date in monthly_dates:
            immediate_cash = monthly_contribution * monthly_immediate_pct
            reserve_cash = monthly_contribution * reserve_pct
            cash += reserve_cash
            total_contributed += monthly_contribution
            contribution_count += 1
            cash_flows.append((date, -monthly_contribution))
            if immediate_cash > 0:
                new_shares, cash_after, commission = _buy_with_cash(
                    immediate_cash, close, commission_pct, slippage_pct
                )
                if new_shares > 0:
                    shares += new_shares
                    total_commission += commission
                    buy_count += 1
                    trades.append(
                        {
                            "date": date,
                            "action": "immediate_buy",
                            "price": close,
                            "shares": new_shares,
                            "cash_after": cash_after,
                            "technical_state": technical_state,
                            "commission": commission,
                        }
                    )

        should_buy = (
            deploy_rule == "always"
            or (deploy_rule == "bullish_state" and technical_state > 0)
            or (deploy_rule == "entry_signal" and bool(entries.loc[date]))
        )
        if should_buy and cash > 0:
            new_shares, cash_after, commission = _buy_with_cash(
                cash, close, commission_pct, slippage_pct
            )
            if new_shares > 0:
                shares += new_shares
                total_commission += commission
                buy_count += 1
                trades.append(
                    {
                        "date": date,
                        "action": "reserve_buy",
                        "price": close,
                        "shares": new_shares,
                        "cash_after": cash_after,
                        "technical_state": technical_state,
                        "commission": commission,
                    }
                )
            cash = cash_after

        position_value = shares * close
        equity = cash + position_value
        rows.append(
            {
                "date": date,
                "cash": cash,
                "shares": shares,
                "position_value": position_value,
                "equity": equity,
                "total_contributed": total_contributed,
                "technical_state": technical_state,
            }
        )

    equity_curve = pd.DataFrame(rows).set_index("date")
    trades_frame = pd.DataFrame(trades)
    final_equity = float(equity_curve["equity"].iloc[-1]) if not equity_curve.empty else 0.0
    cash_flows.append((equity_curve.index[-1], final_equity))
    profit = final_equity - total_contributed
    metrics = {
        "final_equity": final_equity,
        "total_contributed": total_contributed,
        "net_profit": profit,
        "profit_on_contributed_pct": profit / total_contributed * 100 if total_contributed else 0.0,
        "money_weighted_irr_pct": xirr(cash_flows) * 100,
        "max_drawdown_pct": max_drawdown(equity_curve["equity"]) * 100,
        "sharpe": annualized_sharpe(equity_curve["equity"]),
        "ending_cash": float(equity_curve["cash"].iloc[-1]) if not equity_curve.empty else 0.0,
        "ending_invested_value": float(equity_curve["position_value"].iloc[-1])
        if not equity_curve.empty
        else 0.0,
        "average_cash_pct": float((equity_curve["cash"] / equity_curve["equity"]).replace([pd.NA], 0).mean() * 100),
        "contribution_count": float(contribution_count),
        "buy_count": float(buy_count),
        "sell_count": float(sell_count),
        "total_commission": total_commission,
        "monthly_immediate_pct": monthly_immediate_pct,
        "reserve_pct": reserve_pct,
    }
    return equity_curve, trades_frame, metrics


def evaluate_symbol(
    symbol: str,
    prices: pd.DataFrame,
    monthly_contribution: float,
    commission_pct: float,
    slippage_pct: float,
    sell_fraction: float,
    cash_yield: float,
) -> tuple[pd.DataFrame, pd.DataFrame, dict[str, pd.DataFrame]]:
    dca_equity, dca_trades, dca_metrics = run_dca_backtest(
        prices,
        monthly_contribution,
        commission_pct,
        slippage_pct,
        monthly_immediate_pct=1.0,
        reserve_pct=0.0,
        deploy_rule="always",
        cash_yield=cash_yield,
    )
    rows = [
        {
            "symbol": symbol,
            "framework": "A_100pct_monthly_dca",
            "strategy": "plain_dca",
            "params_json": "{}",
            **dca_metrics,
        }
    ]
    detail_frames = {
        "plain_equity": dca_equity,
        "plain_trades": dca_trades,
    }
    best_b = None
    best_c = None

    for strategy_name, strategy_fn in STRATEGY_FUNCTIONS.items():
        grid = strategy_parameter_grids().get(strategy_name, {})
        for params in parameter_combinations(grid):
            signals = strategy_fn(prices, **params)
            state = signal_state(signals)
            entry_signal = signals["signal_direction"] > 0

            b_equity, b_trades, b_metrics = run_dca_backtest(
                prices,
                monthly_contribution,
                commission_pct,
                slippage_pct,
                timing_state=state,
                entry_signal=entry_signal,
                monthly_immediate_pct=0.0,
                reserve_pct=1.0,
                deploy_rule="bullish_state",
                allow_sell=False,
                sell_fraction=sell_fraction,
                cash_yield=cash_yield,
            )
            b_row = {
                "symbol": symbol,
                "framework": "B_entry_timing_only_no_sell",
                "strategy": strategy_name,
                "params_json": json.dumps(params, sort_keys=True),
                **b_metrics,
            }
            b_row["excess_profit_vs_plain_dca"] = (
                b_metrics["net_profit"] - dca_metrics["net_profit"]
            )
            b_row["excess_final_equity_vs_plain_dca"] = (
                b_metrics["final_equity"] - dca_metrics["final_equity"]
            )
            b_row["excess_irr_pct_vs_plain_dca"] = (
                b_metrics["money_weighted_irr_pct"] - dca_metrics["money_weighted_irr_pct"]
            )
            rows.append(b_row)
            if best_b is None or (
                b_row["final_equity"],
                b_row["money_weighted_irr_pct"],
            ) > (
                best_b["row"]["final_equity"],
                best_b["row"]["money_weighted_irr_pct"],
            ):
                best_b = {"row": b_row, "equity": b_equity, "trades": b_trades}

            c_equity, c_trades, c_metrics = run_dca_backtest(
                prices,
                monthly_contribution,
                commission_pct,
                slippage_pct,
                timing_state=state,
                entry_signal=entry_signal,
                monthly_immediate_pct=0.6,
                reserve_pct=0.4,
                deploy_rule="entry_signal",
                allow_sell=False,
                sell_fraction=sell_fraction,
                cash_yield=cash_yield,
            )
            c_row = {
                "symbol": symbol,
                "framework": "C_60pct_dca_40pct_tactical_reserve",
                "strategy": strategy_name,
                "params_json": json.dumps(params, sort_keys=True),
                **c_metrics,
            }
            c_row["excess_profit_vs_plain_dca"] = (
                c_metrics["net_profit"] - dca_metrics["net_profit"]
            )
            c_row["excess_final_equity_vs_plain_dca"] = (
                c_metrics["final_equity"] - dca_metrics["final_equity"]
            )
            c_row["excess_irr_pct_vs_plain_dca"] = (
                c_metrics["money_weighted_irr_pct"] - dca_metrics["money_weighted_irr_pct"]
            )
            rows.append(c_row)
            if best_c is None or (
                c_row["final_equity"],
                c_row["money_weighted_irr_pct"],
            ) > (
                best_c["row"]["final_equity"],
                best_c["row"]["money_weighted_irr_pct"],
            ):
                best_c = {"row": c_row, "equity": c_equity, "trades": c_trades}

    dca_row = rows[0]
    dca_row["excess_profit_vs_plain_dca"] = 0.0
    dca_row["excess_final_equity_vs_plain_dca"] = 0.0
    dca_row["excess_irr_pct_vs_plain_dca"] = 0.0
    if best_b is not None:
        detail_frames["best_b_equity"] = best_b["equity"]
        detail_frames["best_b_trades"] = best_b["trades"]
    if best_c is not None:
        detail_frames["best_c_equity"] = best_c["equity"]
        detail_frames["best_c_trades"] = best_c["trades"]
    return pd.DataFrame(rows), pd.DataFrame([dca_row, best_b["row"], best_c["row"]]), detail_frames


def investigation_note(row: pd.Series) -> str:
    excess = float(row["excess_final_equity_vs_plain_dca"])
    avg_cash = float(row["average_cash_pct"])
    framework = str(row["framework"])
    if excess > 0:
        if framework.startswith("C_"):
            return "The reserve sleeve added value by waiting for recovery signals while the 60% core stayed continuously invested."
        return "Entry timing improved the monthly plan by waiting for bullish regimes before deploying accumulated cash."
    if avg_cash > 25:
        return "Timing lagged because too much contribution cash waited on the sidelines during a rising market."
    return "Timing lagged because continuous monthly exposure captured the trend better than delayed deployment."


def write_report(path: Path, summary: pd.DataFrame, start: str, end: str, adjustment: str) -> None:
    plain = summary[summary["framework"] == "A_100pct_monthly_dca"].set_index("symbol")
    b_timing = summary[summary["framework"] == "B_entry_timing_only_no_sell"].copy()
    c_timing = summary[summary["framework"] == "C_60pct_dca_40pct_tactical_reserve"].copy()
    timing = pd.concat([b_timing, c_timing], ignore_index=True)
    b_winners = b_timing[b_timing["excess_final_equity_vs_plain_dca"] > 0]
    c_winners = c_timing[c_timing["excess_final_equity_vs_plain_dca"] > 0]
    b_strategy_counts = b_timing["strategy"].value_counts().to_dict()
    c_strategy_counts = c_timing["strategy"].value_counts().to_dict()
    lines = [
        "# Monthly DCA vs Technical-Timing DCA",
        "",
        f"Data window: `{start}` to `{end}`.",
        f"Price adjustment mode: `{adjustment}`.",
        "Monthly contribution: `$10,000`, contributed on the first trading day of each month.",
        "Costs: `0.10%` commission and `0.05%` slippage on every buy and sell.",
        "",
        "Framework A invests every monthly contribution immediately and never sells.",
        "Framework B holds each contribution as cash until the selected technical state is bullish, then buys with all available cash. It never sells existing shares.",
        "Framework C invests 60% of each monthly contribution immediately and keeps 40% as a tactical reserve, deploying reserve cash only on fresh bullish/pullback-recovery entry signals. It never sells existing shares.",
        "",
        "## Summary",
        "",
        f"- Framework B beat plain DCA for {len(b_winners)} of {len(b_timing)} symbols.",
        f"- Framework C beat plain DCA for {len(c_winners)} of {len(c_timing)} symbols.",
        f"- Framework B best strategy families: {json.dumps(b_strategy_counts, sort_keys=True)}.",
        f"- Framework C best strategy families: {json.dumps(c_strategy_counts, sort_keys=True)}.",
        "- The most important comparison metrics are final equity, net profit on contributed capital, and money-weighted IRR.",
        "",
        "## Best B And C vs Plain DCA",
        "",
        "| Symbol | Framework | Best Strategy | Params | Final Equity | Plain DCA | Excess | IRR | Plain IRR | Avg Cash |",
        "| --- | --- | --- | --- | ---: | ---: | ---: | ---: | ---: | ---: |",
    ]
    for _, row in timing.sort_values(
        ["symbol", "framework", "excess_final_equity_vs_plain_dca"]
    ).iterrows():
        plain_row = plain.loc[row["symbol"]]
        lines.append(
            "| {symbol} | {framework} | {strategy} | `{params}` | ${timing_equity:,.0f} | ${plain_equity:,.0f} | ${excess:,.0f} | {timing_irr:.2f}% | {plain_irr:.2f}% | {avg_cash:.1f}% |".format(
                symbol=row["symbol"],
                framework=row["framework"],
                strategy=row["strategy"],
                params=row["params_json"],
                timing_equity=row["final_equity"],
                plain_equity=plain_row["final_equity"],
                excess=row["excess_final_equity_vs_plain_dca"],
                timing_irr=row["money_weighted_irr_pct"],
                plain_irr=plain_row["money_weighted_irr_pct"],
                avg_cash=row["average_cash_pct"],
            )
        )
    lines.extend(["", "## Laggard Investigation", ""])
    laggards = timing[timing["excess_final_equity_vs_plain_dca"] <= 0]
    if laggards.empty:
        lines.append("No Framework B or C strategy lagged plain monthly DCA in this run.")
    else:
        for _, row in laggards.sort_values(["symbol", "framework"]).iterrows():
            lines.append(
                f"- **{row['symbol']} {row['framework']}**: best `{row['strategy']}` ended "
                f"${abs(row['excess_final_equity_vs_plain_dca']):,.0f} below plain DCA. "
                f"{investigation_note(row)}"
            )
    lines.extend(
        [
            "",
            "## Research Caveats",
            "",
            "- This remains an in-sample comparison because the best technical rule is selected after observing the full period.",
            "- Monthly DCA changes the objective: cash drag and missed rebound days matter more than avoiding every drawdown.",
            "- Framework B and C do not sell existing shares in this version; they only control new cash and reserve deployment.",
            "- Use adjusted data for investment research. Raw mode is available only for TradingView price-level matching.",
            "- The next fairer step is walk-forward selection: choose timing rules using prior data, then test future monthly contributions.",
            "",
        ]
    )
    path.write_text("\n".join(lines))


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--symbols", default=",".join(SYMBOLS))
    parser.add_argument("--start", default="2021-06-14")
    parser.add_argument("--end", default="2026-06-13")
    parser.add_argument("--adjustment", choices=["auto_adjust", "raw"], default="auto_adjust")
    parser.add_argument("--monthly-contribution", type=float, default=10_000)
    parser.add_argument("--commission-pct", type=float, default=0.001)
    parser.add_argument("--slippage-pct", type=float, default=0.0005)
    parser.add_argument("--sell-fraction", type=float, default=1.0)
    parser.add_argument("--cash-yield", type=float, default=0.0)
    parser.add_argument("--output-dir", default="data/processed/dca_timing_comparison")
    parser.add_argument("--skip-download", action="store_true")
    args = parser.parse_args()

    output_dir = Path(args.output_dir)
    data_dir = output_dir / ("raw_ohlcv" if args.adjustment == "raw" else "adjusted_ohlcv")
    output_dir.mkdir(parents=True, exist_ok=True)
    symbols = [symbol.strip().upper() for symbol in args.symbols.split(",") if symbol.strip()]

    if not args.skip_download:
        download_symbols(symbols, data_dir, args.start, args.end, args.adjustment)

    summary_frames = []
    all_frames = {}
    details_dir = output_dir / "details"
    details_dir.mkdir(exist_ok=True)

    for symbol in symbols:
        path = data_dir / f"{symbol}.csv"
        if not path.exists():
            print(f"Skipping {symbol}: missing {path}")
            continue
        prices = load_ohlcv_file(path)
        prices = prices.loc[
            (prices.index >= pd.Timestamp(args.start))
            & (prices.index <= pd.Timestamp(args.end) - pd.Timedelta(days=1))
        ].copy()
        if len(prices) < 200:
            print(f"Skipping {symbol}: only {len(prices)} rows")
            continue
        print(f"Evaluating {symbol} over {prices.index.min().date()} to {prices.index.max().date()}")
        all_rows, summary, details = evaluate_symbol(
            symbol,
            prices,
            args.monthly_contribution,
            args.commission_pct,
            args.slippage_pct,
            args.sell_fraction,
            args.cash_yield,
        )
        all_frames[symbol] = all_rows
        summary_frames.append(summary)
        all_rows.to_csv(details_dir / f"{symbol}_all_frameworks.csv", index=False)
        for name, frame in details.items():
            frame.to_csv(details_dir / f"{symbol}_{name}.csv")

    summary_all = pd.concat(summary_frames, ignore_index=True)
    summary_all["investigation_note"] = summary_all.apply(
        lambda row: investigation_note(row)
        if row["framework"] != "A_100pct_monthly_dca"
        else "Plain DCA baseline.",
        axis=1,
    )
    summary_path = output_dir / "summary_dca_vs_timing.csv"
    summary_all.to_csv(summary_path, index=False)

    workbook_path = output_dir / "dca_vs_technical_timing.xlsx"
    with pd.ExcelWriter(workbook_path, engine="openpyxl") as writer:
        summary_all.to_excel(writer, sheet_name="Summary", index=False)
        for symbol, frame in all_frames.items():
            frame.to_excel(writer, sheet_name=_safe_sheet_name(symbol), index=False)

    report_path = output_dir / "findings.md"
    write_report(report_path, summary_all, args.start, "2026-06-12", args.adjustment)

    print(f"Wrote workbook: {workbook_path}")
    print(f"Wrote summary CSV: {summary_path}")
    print(f"Wrote details: {details_dir}")
    print(f"Wrote findings: {report_path}")


if __name__ == "__main__":
    main()
