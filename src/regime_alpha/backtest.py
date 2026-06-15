from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd


TRADING_DAYS_PER_YEAR = 252


@dataclass(frozen=True)
class ExecutionConfig:
    initial_capital: float = 100_000.0
    allocation_pct: float = 1.0
    commission_pct: float = 0.001
    slippage_pct: float = 0.0005


@dataclass(frozen=True)
class BacktestResult:
    equity_curve: pd.DataFrame
    trades: pd.DataFrame
    metrics: dict[str, float]


def max_drawdown(equity: pd.Series) -> float:
    peak = equity.cummax()
    drawdown = equity / peak - 1
    return float(drawdown.min()) if not drawdown.empty else 0.0


def cagr(equity: pd.Series, periods_per_year: int = TRADING_DAYS_PER_YEAR) -> float:
    clean = equity.dropna()
    if len(clean) < 2 or clean.iloc[0] <= 0:
        return 0.0
    years = (len(clean) - 1) / periods_per_year
    if years <= 0:
        return 0.0
    return float((clean.iloc[-1] / clean.iloc[0]) ** (1 / years) - 1)


def annualized_sharpe(equity: pd.Series, periods_per_year: int = TRADING_DAYS_PER_YEAR) -> float:
    returns = equity.pct_change().replace([np.inf, -np.inf], np.nan).dropna()
    if returns.empty or returns.std(ddof=0) == 0:
        return 0.0
    return float((returns.mean() / returns.std(ddof=0)) * np.sqrt(periods_per_year))


def annualized_sortino(equity: pd.Series, periods_per_year: int = TRADING_DAYS_PER_YEAR) -> float:
    returns = equity.pct_change().replace([np.inf, -np.inf], np.nan).dropna()
    downside = returns[returns < 0]
    if returns.empty or downside.empty or downside.std(ddof=0) == 0:
        return 0.0
    return float((returns.mean() / downside.std(ddof=0)) * np.sqrt(periods_per_year))


def calmar_ratio(equity: pd.Series, periods_per_year: int = TRADING_DAYS_PER_YEAR) -> float:
    dd = abs(max_drawdown(equity))
    if dd == 0:
        return 0.0
    return float(cagr(equity, periods_per_year) / dd)


def summarize_trades(trades: pd.DataFrame) -> dict[str, float]:
    if trades.empty:
        return {
            "number_of_trades": 0.0,
            "win_rate": 0.0,
            "average_trade_return": 0.0,
            "profit_factor": 0.0,
        }

    returns = trades["return_pct"]
    wins = returns[returns > 0]
    losses = returns[returns < 0]
    gross_profit = wins.sum()
    gross_loss = losses.abs().sum()
    profit_factor = float(gross_profit / gross_loss) if gross_loss > 0 else float("inf")
    return {
        "number_of_trades": float(len(trades)),
        "win_rate": float(len(wins) / len(trades)),
        "average_trade_return": float(returns.mean()),
        "profit_factor": profit_factor,
    }


def performance_metrics(equity_curve: pd.DataFrame, trades: pd.DataFrame) -> dict[str, float]:
    equity = equity_curve["equity"]
    total_return = float(equity.iloc[-1] / equity.iloc[0] - 1) if len(equity) > 1 else 0.0
    metrics = {
        "total_return": total_return,
        "cagr": cagr(equity),
        "max_drawdown": max_drawdown(equity),
        "sharpe": annualized_sharpe(equity),
        "sortino": annualized_sortino(equity),
        "calmar": calmar_ratio(equity),
    }
    metrics.update(summarize_trades(trades))
    return metrics


def run_long_only_backtest(
    prices: pd.DataFrame,
    signals: pd.DataFrame,
    config: ExecutionConfig | None = None,
) -> BacktestResult:
    """Run a simple close-based, long-only backtest for one symbol.

    Signals are evaluated on the same bar close. This is intentionally simple
    research plumbing; production studies should also test next-open execution.
    """
    cfg = config or ExecutionConfig()
    if not 0 < cfg.allocation_pct <= 1:
        raise ValueError("allocation_pct must be in the range (0, 1]")
    if "close" not in prices.columns:
        raise ValueError("prices must contain a 'close' column")
    if "signal_direction" not in signals.columns:
        raise ValueError("signals must contain a 'signal_direction' column")

    data = prices.join(signals, how="left")
    data["signal_direction"] = data["signal_direction"].fillna(0).astype(int)
    if "initial_stop_loss" not in data.columns:
        data["initial_stop_loss"] = np.nan

    cash = cfg.initial_capital
    shares = 0.0
    entry_date = None
    entry_price = 0.0
    entry_equity = 0.0
    active_stop = np.nan
    trade_rows: list[dict[str, object]] = []
    equity_rows: list[dict[str, object]] = []

    for date, row in data.iterrows():
        close = float(row["close"])
        low = float(row["low"]) if "low" in data.columns and pd.notna(row["low"]) else close
        signal = int(row["signal_direction"])

        if shares > 0:
            stop_hit = pd.notna(active_stop) and low <= active_stop
            exit_signal = signal < 0
            if stop_hit or exit_signal:
                reason = "stop_loss" if stop_hit else "signal_exit"
                raw_exit_price = float(active_stop) if stop_hit else close
                exit_price = raw_exit_price * (1 - cfg.slippage_pct)
                exit_value = shares * exit_price
                exit_commission = exit_value * cfg.commission_pct
                cash += exit_value - exit_commission
                trade_return = (cash - entry_equity) / entry_equity
                trade_rows.append(
                    {
                        "entry_date": entry_date,
                        "exit_date": date,
                        "entry_price": entry_price,
                        "exit_price": exit_price,
                        "shares": shares,
                        "return_pct": trade_return,
                        "exit_reason": reason,
                    }
                )
                shares = 0.0
                entry_date = None
                entry_price = 0.0
                entry_equity = 0.0
                active_stop = np.nan

        current_equity = cash + shares * close

        if shares == 0 and signal > 0:
            investable_equity = current_equity * cfg.allocation_pct
            trade_value = investable_equity / (1 + cfg.commission_pct)
            fill_price = close * (1 + cfg.slippage_pct)
            shares = trade_value / fill_price
            entry_commission = trade_value * cfg.commission_pct
            cash = current_equity - trade_value - entry_commission
            entry_date = date
            entry_price = fill_price
            entry_equity = current_equity
            active_stop = float(row["initial_stop_loss"]) if pd.notna(row["initial_stop_loss"]) else np.nan
            current_equity = cash + shares * close

        equity_rows.append(
            {
                "date": date,
                "cash": cash,
                "position_value": shares * close,
                "equity": cash + shares * close,
                "shares": shares,
            }
        )

    equity_curve = pd.DataFrame(equity_rows).set_index("date")
    trades = pd.DataFrame(trade_rows)
    metrics = performance_metrics(equity_curve, trades)
    return BacktestResult(equity_curve=equity_curve, trades=trades, metrics=metrics)
