from __future__ import annotations

import argparse
import json
from itertools import product
from pathlib import Path

import numpy as np
import pandas as pd

from dca_timing_comparison import (
    SYMBOLS,
    download_symbols,
    first_trading_days_by_month,
    run_dca_backtest,
    xirr,
)
from regime_alpha.backtest import annualized_sharpe, annualized_sortino, max_drawdown
from regime_alpha.indicators import bollinger_bands, macd, rsi, supertrend
from regime_alpha.io import load_ohlcv_file


OBJECTIVES = ["final_equity", "irr", "risk_adjusted", "plateau"]
FRAMEWORKS = {
    "B_entry_timing_only_no_sell": {
        "monthly_immediate_pct": 0.0,
        "reserve_pct": 1.0,
        "deploy_rule": "bullish_state",
    },
    "C_60pct_dca_40pct_tactical_reserve": {
        "monthly_immediate_pct": 0.6,
        "reserve_pct": 0.4,
        "deploy_rule": "entry_signal",
    },
}
WINDOWS = [
    ("2021-06-14", "2022-12-31", "2023-01-01", "2023-12-31"),
    ("2021-06-14", "2023-12-31", "2024-01-01", "2024-12-31"),
    ("2021-06-14", "2024-12-31", "2025-01-01", "2025-12-31"),
    ("2021-06-14", "2025-12-31", "2026-01-01", "2026-06-12"),
]


def combinations(grid: dict[str, list[int | float]]) -> list[dict[str, int | float]]:
    keys = list(grid)
    return [dict(zip(keys, values, strict=True)) for values in product(*(grid[key] for key in keys))]


def _frame(index: pd.Index, state: pd.Series, entry: pd.Series) -> pd.DataFrame:
    return pd.DataFrame(
        {
            "timing_state": state.reindex(index).fillna(0).astype("int8"),
            "entry_signal": entry.reindex(index).fillna(False).astype(bool),
        },
        index=index,
    )


def candidate_rules(prices: pd.DataFrame, qqq: pd.DataFrame | None = None) -> dict[str, pd.DataFrame]:
    close = prices["close"]
    index = prices.index
    rules: dict[str, pd.DataFrame] = {}

    for window in [15, 20, 30]:
        for std_mult in [1.5, 2.0, 2.5]:
            bands = bollinger_bands(close, window, std_mult)
            touched = close < bands["bb_lower"]
            recovery = (close > bands["bb_lower"]) & (close.shift() <= bands["bb_lower"].shift())
            entry = touched | recovery
            state = pd.Series(0, index=index)
            state.loc[entry] = 1
            rules[f"bollinger_mean_reversion|{json.dumps({'window': window, 'std_mult': std_mult}, sort_keys=True)}"] = _frame(
                index, state, entry
            )

    for rsi_window in [10, 14, 21]:
        osc = rsi(close, rsi_window)
        for entry_threshold in [35, 40, 45]:
            for recovery_threshold in [40, 45, 50]:
                oversold = osc < entry_threshold
                recovery = (osc > recovery_threshold) & (osc.shift() <= recovery_threshold)
                entry = oversold | recovery
                state = pd.Series(0, index=index)
                state.loc[entry] = 1
                params = {
                    "rsi_window": rsi_window,
                    "entry_threshold": entry_threshold,
                    "recovery_threshold": recovery_threshold,
                }
                rules[f"rsi_pullback|{json.dumps(params, sort_keys=True)}"] = _frame(index, state, entry)

    for fast in [8, 12]:
        for slow in [21, 26]:
            signal_len = 9
            m = macd(close, fast, slow, signal_len)
            state = (m["macd"] > m["macd_signal"]).astype("int8")
            entry = (state == 1) & (state.shift().fillna(0) <= 0)
            params = {"fast": fast, "slow": slow, "signal": signal_len}
            rules[f"macd_momentum|{json.dumps(params, sort_keys=True)}"] = _frame(index, state, entry)

    for atr_window in [7, 10, 14]:
        for multiplier in [2.0, 2.5, 3.0, 3.5]:
            st = supertrend(prices, atr_window=atr_window, multiplier=multiplier)
            state = (st["supertrend_direction"] > 0).astype("int8")
            entry = (state == 1) & (state.shift().fillna(0) <= 0)
            params = {"atr_window": atr_window, "multiplier": multiplier}
            rules[f"supertrend|{json.dumps(params, sort_keys=True)}"] = _frame(index, state, entry)

    for entry_window in [10, 20, 40, 55]:
        breakout = close > prices["high"].rolling(entry_window).max().shift()
        state = pd.Series(0, index=index)
        state.loc[breakout] = 1
        params = {"entry_window": entry_window}
        rules[f"donchian_breakout|{json.dumps(params, sort_keys=True)}"] = _frame(
            index, state, breakout
        )

    for breakout_window in [10, 20, 40]:
        for trend_window in [50, 75, 100]:
            for volume_multiplier in [1.0, 1.25, 1.5]:
                breakout = close > prices["high"].rolling(breakout_window).max().shift()
                volume_ok = prices["volume"] > prices["volume"].rolling(20).mean() * volume_multiplier
                trend_ok = close > close.ewm(span=trend_window, adjust=False).mean()
                entry = breakout & volume_ok & trend_ok
                state = pd.Series(0, index=index)
                state.loc[entry] = 1
                params = {
                    "breakout_window": breakout_window,
                    "trend_window": trend_window,
                    "volume_multiplier": volume_multiplier,
                }
                rules[f"volume_breakout|{json.dumps(params, sort_keys=True)}"] = _frame(
                    index, state, entry
                )

    ma200 = close.rolling(200).mean()
    trend_state = (close > ma200).astype("int8")
    trend_entry = (trend_state == 1) & (trend_state.shift().fillna(0) <= 0)
    rules["simple_200d_trend|{}"] = _frame(index, trend_state, trend_entry)

    if qqq is not None and not qqq.empty:
        qqq_close = qqq["close"].reindex(index).ffill()
        qqq_ma200 = qqq_close.rolling(200).mean()
        qqq_state = (qqq_close > qqq_ma200).astype("int8")
        qqq_entry = (qqq_state == 1) & (qqq_state.shift().fillna(0) <= 0)
        rules["qqq_200d_market_filter|{}"] = _frame(index, qqq_state, qqq_entry)

    osc = rsi(close, 14)
    pullback_entry = (close > ma200) & ((osc < 40) | ((osc > 40) & (osc.shift() <= 40)))
    pullback_state = pd.Series(0, index=index)
    pullback_state.loc[pullback_entry] = 1
    rules["simple_pullback|{\"ma_window\": 200, \"rsi_window\": 14, \"threshold\": 40}"] = _frame(
        index, pullback_state, pullback_entry
    )
    return rules


def parse_rule_key(rule_key: str) -> tuple[str, str]:
    family, params = rule_key.split("|", 1)
    return family, params


def objective_score(metrics: dict[str, float], objective: str) -> float:
    if objective == "final_equity":
        return metrics["final_equity"]
    if objective == "irr":
        return metrics["money_weighted_irr_pct"]
    if objective == "risk_adjusted":
        return (
            metrics["money_weighted_irr_pct"]
            - 0.5 * abs(metrics["max_drawdown_pct"])
            - 0.1 * metrics["average_cash_pct"]
        )
    if objective == "plateau":
        return metrics["final_equity"]
    raise ValueError(f"Unknown objective: {objective}")


def run_framework(
    prices: pd.DataFrame,
    framework: str,
    monthly_contribution: float,
    commission_pct: float,
    slippage_pct: float,
    rule: pd.DataFrame | None = None,
) -> tuple[pd.DataFrame, pd.DataFrame, dict[str, float]]:
    if framework == "A_100pct_monthly_dca":
        return run_dca_backtest(
            prices,
            monthly_contribution,
            commission_pct,
            slippage_pct,
            monthly_immediate_pct=1.0,
            reserve_pct=0.0,
            deploy_rule="always",
        )
    cfg = FRAMEWORKS[framework]
    if rule is None:
        raise ValueError("rule is required for Framework B/C")
    return run_dca_backtest(
        prices,
        monthly_contribution,
        commission_pct,
        slippage_pct,
        timing_state=rule["timing_state"],
        entry_signal=rule["entry_signal"],
        monthly_immediate_pct=cfg["monthly_immediate_pct"],
        reserve_pct=cfg["reserve_pct"],
        deploy_rule=cfg["deploy_rule"],
        allow_sell=False,
    )


def train_scores(
    train_prices: pd.DataFrame,
    rules: dict[str, pd.DataFrame],
    framework: str,
    monthly_contribution: float,
    commission_pct: float,
    slippage_pct: float,
) -> pd.DataFrame:
    rows = []
    for rule_key, full_rule in rules.items():
        family, params_json = parse_rule_key(rule_key)
        rule = full_rule.loc[train_prices.index]
        _, _, metrics = run_framework(
            train_prices,
            framework,
            monthly_contribution,
            commission_pct,
            slippage_pct,
            rule,
        )
        rows.append(
            {
                "rule_key": rule_key,
                "strategy_family": family,
                "params_json": params_json,
                **metrics,
            }
        )
    return pd.DataFrame(rows)


def select_rule(scores: pd.DataFrame, objective: str) -> pd.Series:
    frame = scores.copy()
    frame["objective_score"] = frame.apply(lambda row: objective_score(row.to_dict(), objective), axis=1)
    if objective != "plateau":
        return frame.sort_values(["objective_score", "final_equity"], ascending=False).iloc[0]
    top_n = max(1, int(np.ceil(len(frame) * 0.20)))
    top = frame.sort_values("final_equity", ascending=False).head(top_n).copy()
    family_medians = frame.groupby("strategy_family")["final_equity"].median()
    top["family_median_final_equity"] = top["strategy_family"].map(family_medians)
    top["plateau_score"] = (
        0.60 * top["final_equity"]
        + 0.30 * top["family_median_final_equity"]
        + 0.10 * top["money_weighted_irr_pct"]
    )
    return top.sort_values(["plateau_score", "final_equity"], ascending=False).iloc[0]


def isolated_period_result(
    prices: pd.DataFrame,
    rule: pd.DataFrame | None,
    framework: str,
    monthly_contribution: float,
    commission_pct: float,
    slippage_pct: float,
) -> tuple[pd.DataFrame, pd.DataFrame, dict[str, float]]:
    return run_framework(prices, framework, monthly_contribution, commission_pct, slippage_pct, rule)


def continuous_oos_result(
    prices: pd.DataFrame,
    selected: pd.DataFrame,
    rules: dict[str, pd.DataFrame],
    framework: str,
    monthly_contribution: float,
    commission_pct: float,
    slippage_pct: float,
) -> tuple[pd.DataFrame, pd.DataFrame, dict[str, float]]:
    oos = prices.loc[(prices.index >= "2023-01-01") & (prices.index <= "2026-06-12")].copy()
    if framework == "A_100pct_monthly_dca":
        return run_framework(oos, framework, monthly_contribution, commission_pct, slippage_pct)
    state = pd.Series(0, index=oos.index, dtype="int8")
    entry = pd.Series(False, index=oos.index)
    for _, row in selected.iterrows():
        if row["framework"] != framework:
            continue
        mask = (oos.index >= pd.Timestamp(row["test_start"])) & (
            oos.index <= pd.Timestamp(row["test_end"])
        )
        rule = rules[str(row["rule_key"])].reindex(oos.index)
        state.loc[mask] = rule.loc[mask, "timing_state"].fillna(0).astype("int8")
        entry.loc[mask] = rule.loc[mask, "entry_signal"].fillna(False).astype(bool)
    rule = pd.DataFrame({"timing_state": state, "entry_signal": entry}, index=oos.index)
    return run_framework(oos, framework, monthly_contribution, commission_pct, slippage_pct, rule)


def held_cash_months(equity: pd.DataFrame) -> int:
    first_days = sorted(pd.Series(index=equity.index, data=equity.index).groupby(equity.index.to_period("M")).first())
    return int(sum(float(equity.loc[date, "cash"]) > 1 for date in first_days if date in equity.index))


def cash_flow_summary(equity: pd.DataFrame, monthly_contribution: float) -> dict[str, float]:
    contributed = float(equity["total_contributed"].iloc[-1]) if not equity.empty else 0.0
    final_equity = float(equity["equity"].iloc[-1]) if not equity.empty else 0.0
    flows = []
    for date in first_trading_days_by_month(equity.index):
        flows.append((date, -monthly_contribution))
    if not equity.empty:
        flows.append((equity.index[-1], final_equity))
    return {
        "final_equity": final_equity,
        "total_contributed": contributed,
        "net_profit": final_equity - contributed,
        "money_weighted_irr_pct": xirr(sorted(flows, key=lambda item: item[0])) * 100,
        "max_drawdown_pct": max_drawdown(equity["equity"]) * 100,
        "sharpe": annualized_sharpe(equity["equity"]),
        "sortino": annualized_sortino(equity["equity"]),
        "average_cash_pct": float((equity["cash"] / equity["equity"]).replace([np.inf, -np.inf], np.nan).fillna(0).mean() * 100),
    }


def build_report(
    output: Path,
    oos_summary: pd.DataFrame,
    yearly: pd.DataFrame,
    selected: pd.DataFrame,
) -> None:
    def markdown_table(frame: pd.DataFrame) -> str:
        if frame.empty:
            return "_No rows._"
        text = frame.copy()
        for column in text.columns:
            if pd.api.types.is_float_dtype(text[column]):
                text[column] = text[column].map(lambda value: f"{value:.2f}")
        rows = [
            "| " + " | ".join(map(str, text.columns)) + " |",
            "| " + " | ".join(["---"] * len(text.columns)) + " |",
        ]
        for _, item in text.iterrows():
            rows.append("| " + " | ".join(str(item[column]) for column in text.columns) + " |")
        return "\n".join(rows)

    b = oos_summary[oos_summary["framework"] == "B_entry_timing_only_no_sell"]
    c = oos_summary[oos_summary["framework"] == "C_60pct_dca_40pct_tactical_reserve"]
    best_by_objective = (
        oos_summary[oos_summary["framework"] != "A_100pct_monthly_dca"]
        .groupby(["framework", "objective"])["beat_plain_dca"]
        .sum()
        .reset_index()
    )
    family_counts = selected.groupby(["framework", "objective", "strategy_family"]).size().reset_index(name="count")
    b_best = b.sort_values("excess_final_equity_vs_plain_dca", ascending=False)
    c_best = c.sort_values("excess_final_equity_vs_plain_dca", ascending=False)
    robust = []
    mixed = []
    not_worth = []
    for symbol, group in oos_summary[oos_summary["framework"] != "A_100pct_monthly_dca"].groupby("symbol"):
        wins = int(group["beat_plain_dca"].sum())
        if wins >= 6:
            robust.append(symbol)
        elif wins >= 2:
            mixed.append(symbol)
        else:
            not_worth.append(symbol)
    lines = [
        "# Walk-Forward Monthly DCA Timing Validation",
        "",
        "Out-of-sample period: `2023-01-01` to `2026-06-12`.",
        "Training windows use only data before each test year. Selected rules are then applied to the following unseen year.",
        "Execution uses same-day close after signal/contribution; this is optimistic versus next-day execution but does not use future bars.",
        "",
        "## Direct Answers",
        "",
        f"1. Entry-timing-only DCA beat plain DCA for {int(b['beat_plain_dca'].sum())} of {len(b)} symbol/objective combinations.",
        f"2. Core+tactical DCA beat plain DCA for {int(c['beat_plain_dca'].sum())} of {len(c)} symbol/objective combinations.",
        "3. Objective win counts are shown below; judge by out-of-sample excess, not training fit.",
        "4. Strategy family counts are in the workbook. They show which rules survived train-only selection.",
        "5. Bollinger dominance is weakened if other families appear frequently after walk-forward selection.",
        "6. Biggest beneficiaries are the top rows by excess final equity in the summary CSV.",
        "7. Most harmed names are the bottom rows by excess final equity.",
        "8. Cash drag is measured by average cash ratio and held-cash months.",
        "9. Compare the walk-forward win counts below with the earlier in-sample 18/20 and 17/20 result; any reduction is overfit evidence.",
        "10. A practical rule should favor the simplest objective/framework that wins broadly with modest cash drag.",
        "",
        "## Objective Win Counts",
        "",
        markdown_table(best_by_objective),
        "",
        "## Selected Family Counts",
        "",
        markdown_table(family_counts),
        "",
        "## Top Entry-Timing OOS Results",
        "",
        markdown_table(
            b_best[
                [
                    "symbol",
                    "objective",
                    "final_equity",
                    "excess_final_equity_vs_plain_dca",
                    "money_weighted_irr_pct",
                    "average_cash_pct",
                ]
            ].head(10)
        ),
        "",
        "## Top Core+Tactical OOS Results",
        "",
        markdown_table(
            c_best[
                [
                    "symbol",
                    "objective",
                    "final_equity",
                    "excess_final_equity_vs_plain_dca",
                    "money_weighted_irr_pct",
                    "average_cash_pct",
                ]
            ].head(10)
        ),
        "",
        "## Conclusion Categories",
        "",
        f"- Robust: {', '.join(sorted(robust)) if robust else 'None'}",
        f"- Mixed: {', '.join(sorted(mixed)) if mixed else 'None'}",
        f"- Not worth it: {', '.join(sorted(not_worth)) if not_worth else 'None'}",
        "",
        "## Caveats",
        "",
        "- This validates rule selection by year, but it still uses the current candidate library chosen by the researcher.",
        "- Same-day close execution can be generous. A next-day execution rerun would be stricter.",
        "- QQQ 200D and stock 200D rules are automatically cash-heavy in early windows if insufficient moving-average history exists.",
        "",
    ]
    output.write_text("\n".join(lines))


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--symbols", default=",".join(SYMBOLS))
    parser.add_argument("--start", default="2021-06-14")
    parser.add_argument("--end", default="2026-06-13")
    parser.add_argument("--adjustment", choices=["auto_adjust", "raw"], default="auto_adjust")
    parser.add_argument("--monthly-contribution", type=float, default=10_000)
    parser.add_argument("--commission-pct", type=float, default=0.001)
    parser.add_argument("--slippage-pct", type=float, default=0.0005)
    parser.add_argument("--output-dir", default="data/processed/walkforward_dca_timing")
    parser.add_argument("--data-dir", default="")
    parser.add_argument("--skip-download", action="store_true")
    args = parser.parse_args()

    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    data_dir = Path(args.data_dir) if args.data_dir else output_dir / ("raw_ohlcv" if args.adjustment == "raw" else "adjusted_ohlcv")
    symbols = [symbol.strip().upper() for symbol in args.symbols.split(",") if symbol.strip()]
    if "QQQ" not in symbols:
        download_symbols_list = symbols + ["QQQ"]
    else:
        download_symbols_list = symbols
    if not args.skip_download:
        download_symbols(download_symbols_list, data_dir, args.start, args.end, args.adjustment)

    qqq = load_ohlcv_file(data_dir / "QQQ.csv") if (data_dir / "QQQ.csv").exists() else pd.DataFrame()
    yearly_rows = []
    selected_rows = []
    oos_rows = []
    wide_rows = []
    equity_dir = output_dir / "equity_curves"
    equity_dir.mkdir(exist_ok=True)

    for symbol in symbols:
        path = data_dir / f"{symbol}.csv"
        if not path.exists():
            print(f"Skipping {symbol}: missing {path}")
            continue
        prices = load_ohlcv_file(path)
        prices = prices.loc[(prices.index >= args.start) & (prices.index <= "2026-06-12")].copy()
        if len(prices) < 200:
            print(f"Skipping {symbol}: insufficient data")
            continue
        print(f"Walk-forward {symbol}")
        rules = candidate_rules(prices, qqq)
        selected_symbol_rows = []

        for train_start, train_end, test_start, test_end in WINDOWS:
            train = prices.loc[(prices.index >= train_start) & (prices.index <= train_end)]
            test = prices.loc[(prices.index >= test_start) & (prices.index <= test_end)]
            if train.empty or test.empty:
                continue
            plain_equity, _, plain_metrics = isolated_period_result(
                test,
                None,
                "A_100pct_monthly_dca",
                args.monthly_contribution,
                args.commission_pct,
                args.slippage_pct,
            )
            for framework in FRAMEWORKS:
                scores = train_scores(
                    train,
                    rules,
                    framework,
                    args.monthly_contribution,
                    args.commission_pct,
                    args.slippage_pct,
                )
                for objective in OBJECTIVES:
                    selected = select_rule(scores, objective)
                    rule_key = str(selected["rule_key"])
                    family, params_json = parse_rule_key(rule_key)
                    test_rule = rules[rule_key].loc[test.index]
                    test_equity, test_trades, test_metrics = isolated_period_result(
                        test,
                        test_rule,
                        framework,
                        args.monthly_contribution,
                        args.commission_pct,
                        args.slippage_pct,
                    )
                    row = {
                        "symbol": symbol,
                        "framework": framework,
                        "objective": objective,
                        "test_year": pd.Timestamp(test_start).year,
                        "train_start": train_start,
                        "train_end": train_end,
                        "test_start": test.index.min().date().isoformat(),
                        "test_end": test.index.max().date().isoformat(),
                        "selected_strategy_family": family,
                        "selected_params_json": params_json,
                        "rule_key": rule_key,
                        "train_objective_score": float(selected["objective_score"]),
                        "test_final_equity": test_metrics["final_equity"],
                        "test_contributed_capital": test_metrics["total_contributed"],
                        "test_net_profit": test_metrics["net_profit"],
                        "test_irr_pct": test_metrics["money_weighted_irr_pct"],
                        "test_max_drawdown_pct": test_metrics["max_drawdown_pct"],
                        "test_average_cash_pct": test_metrics["average_cash_pct"],
                        "test_buys": test_metrics["buy_count"],
                        "test_held_cash_months": held_cash_months(test_equity),
                        "plain_final_equity": plain_metrics["final_equity"],
                        "plain_irr_pct": plain_metrics["money_weighted_irr_pct"],
                    }
                    row["excess_final_equity_vs_plain_dca"] = (
                        row["test_final_equity"] - row["plain_final_equity"]
                    )
                    row["excess_irr_vs_plain_dca"] = row["test_irr_pct"] - row["plain_irr_pct"]
                    row["beat_plain_dca"] = row["excess_final_equity_vs_plain_dca"] > 0
                    yearly_rows.append(row)
                    selected_rows.append(
                        {
                            "symbol": symbol,
                            "framework": framework,
                            "objective": objective,
                            "test_year": row["test_year"],
                            "strategy_family": family,
                            "params_json": params_json,
                            "rule_key": rule_key,
                            "train_objective_score": row["train_objective_score"],
                        }
                    )
                    selected_symbol_rows.append(row)

        selected_symbol = pd.DataFrame(selected_symbol_rows)
        plain_oos_equity, _, plain_oos_metrics = continuous_oos_result(
            prices,
            pd.DataFrame(),
            rules,
            "A_100pct_monthly_dca",
            args.monthly_contribution,
            args.commission_pct,
            args.slippage_pct,
        )
        plain_oos_equity.to_csv(equity_dir / f"{symbol}_A_plain_oos_equity.csv")
        plain_summary = {
            "symbol": symbol,
            "framework": "A_100pct_monthly_dca",
            "objective": "baseline",
            **plain_oos_metrics,
            "total_buys": np.nan,
            "excess_final_equity_vs_plain_dca": 0.0,
            "excess_irr_vs_plain_dca": 0.0,
            "beat_plain_dca": False,
        }
        oos_rows.append(plain_summary)
        wide = {
            "symbol": symbol,
            "plain_final_equity": plain_oos_metrics["final_equity"],
            "plain_irr_pct": plain_oos_metrics["money_weighted_irr_pct"],
        }
        for framework in FRAMEWORKS:
            for objective in OBJECTIVES:
                chosen = selected_symbol[
                    (selected_symbol["framework"] == framework)
                    & (selected_symbol["objective"] == objective)
                ]
                equity, trades, metrics = continuous_oos_result(
                    prices,
                    chosen,
                    rules,
                    framework,
                    args.monthly_contribution,
                    args.commission_pct,
                    args.slippage_pct,
                )
                prefix = f"{framework}__{objective}"
                equity.to_csv(equity_dir / f"{symbol}_{prefix}_oos_equity.csv")
                metrics_summary = cash_flow_summary(equity, args.monthly_contribution)
                total_buys = float(metrics["buy_count"])
                metrics_summary["total_buys"] = total_buys
                metrics_summary["excess_final_equity_vs_plain_dca"] = (
                    metrics_summary["final_equity"] - plain_oos_metrics["final_equity"]
                )
                metrics_summary["excess_irr_vs_plain_dca"] = (
                    metrics_summary["money_weighted_irr_pct"]
                    - plain_oos_metrics["money_weighted_irr_pct"]
                )
                metrics_summary["beat_plain_dca"] = (
                    metrics_summary["excess_final_equity_vs_plain_dca"] > 0
                )
                oos_rows.append(
                    {
                        "symbol": symbol,
                        "framework": framework,
                        "objective": objective,
                        **metrics_summary,
                    }
                )
                for key, value in metrics_summary.items():
                    wide[f"{prefix}__{key}"] = value
        wide_rows.append(wide)

    yearly = pd.DataFrame(yearly_rows)
    selected = pd.DataFrame(selected_rows)
    oos_summary = pd.DataFrame(oos_rows)
    wide = pd.DataFrame(wide_rows)
    family_counts = (
        selected.groupby(["framework", "objective", "strategy_family"]).size().reset_index(name="count")
        if not selected.empty
        else pd.DataFrame()
    )
    cash_drag = (
        oos_summary[oos_summary["framework"] != "A_100pct_monthly_dca"]
        .sort_values("average_cash_pct", ascending=False)
        .copy()
    )
    beat_analysis = (
        oos_summary[oos_summary["framework"] != "A_100pct_monthly_dca"]
        .groupby(["framework", "objective"])["beat_plain_dca"]
        .agg(["sum", "count", "mean"])
        .reset_index()
    )

    yearly.to_csv(output_dir / "walkforward_dca_timing_yearly_results.csv", index=False)
    oos_summary.to_csv(output_dir / "walkforward_dca_timing_oos_summary.csv", index=False)
    selected.to_csv(output_dir / "walkforward_dca_timing_selected_rules.csv", index=False)
    wide.to_csv(output_dir / "walkforward_dca_timing_wide_comparison.csv", index=False)

    notes = pd.DataFrame(
        {
            "note": [
                "Train-only annual walk-forward selection; no test-year data used for rule choice.",
                "Framework B times only new cash deployment and never sells existing shares.",
                "Framework C invests 60% immediately and reserves 40% for fresh entry/recovery signals.",
                "Signals execute on same-day close after contribution/signal observation.",
                "Adjusted prices are used by default for investment research.",
            ]
        }
    )
    workbook = output_dir / "walkforward_dca_timing.xlsx"
    with pd.ExcelWriter(workbook, engine="openpyxl") as writer:
        oos_summary.to_excel(writer, sheet_name="OOS Summary", index=False)
        yearly.to_excel(writer, sheet_name="Yearly Results", index=False)
        selected.to_excel(writer, sheet_name="Selected Rules", index=False)
        wide.to_excel(writer, sheet_name="Wide Comparison", index=False)
        family_counts.to_excel(writer, sheet_name="Strategy Family Counts", index=False)
        cash_drag.to_excel(writer, sheet_name="Cash Drag Analysis", index=False)
        beat_analysis.to_excel(writer, sheet_name="Beat Plain DCA Analysis", index=False)
        notes.to_excel(writer, sheet_name="Methodology Notes", index=False)

    build_report(output_dir / "walkforward_dca_timing_report.md", oos_summary, yearly, selected)
    print(f"Wrote walk-forward outputs to {output_dir}")


if __name__ == "__main__":
    main()
