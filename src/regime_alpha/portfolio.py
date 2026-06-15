from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd

from regime_alpha.backtest import annualized_sharpe, cagr, max_drawdown, summarize_trades
from regime_alpha.indicators import atr
from regime_alpha.research import STRATEGY_FUNCTIONS


@dataclass(frozen=True)
class PortfolioConfig:
    initial_capital: float = 100_000.0
    risk_per_trade: float = 0.01
    max_portfolio_heat: float = 0.20
    max_positions: int = 20
    max_position_pct: float = 0.20
    commission_pct: float = 0.001
    slippage_pct: float = 0.0005
    correlation_window: int = 30
    max_pairwise_correlation: float = 0.80
    use_correlation_filter: bool = True
    atr_window: int = 14
    atr_stop_multiplier: float = 2.5
    execution_timing: str = "close"


@dataclass(frozen=True)
class PortfolioResult:
    equity_curve: pd.DataFrame
    trades: pd.DataFrame
    positions: pd.DataFrame
    metrics: dict[str, float]
    benchmark_curve: pd.DataFrame


def _prepare_symbol_frame(
    prices: pd.DataFrame,
    strategy_name: str,
    config: PortfolioConfig,
) -> pd.DataFrame:
    if strategy_name not in STRATEGY_FUNCTIONS:
        raise ValueError(f"Unknown strategy: {strategy_name}")
    signals = STRATEGY_FUNCTIONS[strategy_name](prices)
    out = prices.join(signals, how="left")
    out["signal_direction"] = out["signal_direction"].fillna(0).astype(int)
    out["atr"] = atr(out, window=config.atr_window)
    fallback_stop = out["close"] - out["atr"] * config.atr_stop_multiplier
    out["initial_stop_loss"] = out["initial_stop_loss"].where(
        out["initial_stop_loss"].notna(), fallback_stop
    )
    if config.execution_timing == "next_open":
        out["exec_signal_direction"] = out["signal_direction"].shift().fillna(0).astype(int)
        out["exec_initial_stop_loss"] = out["initial_stop_loss"].shift()
    elif config.execution_timing == "close":
        out["exec_signal_direction"] = out["signal_direction"]
        out["exec_initial_stop_loss"] = out["initial_stop_loss"]
    else:
        raise ValueError("execution_timing must be 'close' or 'next_open'")
    return out


def _is_correlated(
    symbol: str,
    open_symbols: list[str],
    returns: pd.DataFrame,
    date: pd.Timestamp,
    config: PortfolioConfig,
) -> bool:
    if not config.use_correlation_filter or not open_symbols:
        return False
    if symbol not in returns.columns:
        return False
    history = returns.loc[:date].tail(config.correlation_window)
    if len(history) < max(5, config.correlation_window // 2):
        return False
    for other in open_symbols:
        if other not in history.columns:
            continue
        pair = history[[symbol, other]].dropna()
        if len(pair) < max(5, config.correlation_window // 2):
            continue
        corr = pair[symbol].corr(pair[other])
        if pd.notna(corr) and corr > config.max_pairwise_correlation:
            return True
    return False


def _benchmark_curve(
    benchmark: pd.DataFrame | None,
    initial_capital: float,
    dates: list[pd.Timestamp],
) -> pd.DataFrame:
    if benchmark is None or benchmark.empty:
        return pd.DataFrame(columns=["equity", "benchmark_return"])
    close = benchmark["close"].reindex(dates).ffill().dropna()
    if close.empty:
        return pd.DataFrame(columns=["equity", "benchmark_return"])
    curve = pd.DataFrame(index=close.index)
    curve["equity"] = initial_capital * (close / close.iloc[0])
    curve["benchmark_return"] = curve["equity"] / initial_capital - 1
    return curve


def _summarize_portfolio(
    equity_curve: pd.DataFrame,
    trades: pd.DataFrame,
    benchmark_curve: pd.DataFrame | None = None,
) -> dict[str, float]:
    equity = equity_curve["equity"]
    total_return = float(equity.iloc[-1] / equity.iloc[0] - 1) if len(equity) > 1 else 0.0
    exposure = (
        float(
            (equity_curve["position_value"] / equity_curve["equity"])
            .replace([np.inf, -np.inf], 0)
            .mean()
        )
        if not equity_curve.empty
        else 0.0
    )
    traded_value = float(trades["traded_value"].sum()) if "traded_value" in trades.columns else 0.0
    avg_equity = float(equity.mean()) if not equity.empty else 0.0
    years = (len(equity) - 1) / 252 if len(equity) > 1 else 0.0
    turnover = traded_value / avg_equity / years if avg_equity > 0 and years > 0 else 0.0
    metrics = {
        "total_return": total_return,
        "cagr": cagr(equity),
        "max_drawdown": max_drawdown(equity),
        "sharpe": annualized_sharpe(equity),
        "average_exposure": exposure,
        "annual_turnover": turnover,
    }
    if benchmark_curve is not None and not benchmark_curve.empty:
        benchmark_equity = benchmark_curve["equity"]
        benchmark_return = float(benchmark_equity.iloc[-1] / benchmark_equity.iloc[0] - 1)
        metrics["benchmark_return"] = benchmark_return
        metrics["benchmark_cagr"] = cagr(benchmark_equity)
        metrics["benchmark_max_drawdown"] = max_drawdown(benchmark_equity)
        metrics["excess_return"] = total_return - benchmark_return
    metrics.update(summarize_trades(trades))
    return metrics


def run_portfolio_backtest(
    price_data: dict[str, pd.DataFrame],
    strategy_name: str,
    config: PortfolioConfig | None = None,
    benchmark: pd.DataFrame | None = None,
) -> PortfolioResult:
    """Run a daily long-only portfolio simulation over cached symbol data.

    The simulator is intentionally conservative and transparent. It uses same-bar
    close fills, ATR/stop-distance risk sizing, max position count, portfolio
    heat, optional correlation gating, and daily mark-to-market accounting.
    """
    cfg = config or PortfolioConfig()
    if not price_data:
        raise ValueError("price_data is empty")
    if cfg.max_positions < 1:
        raise ValueError("max_positions must be at least 1")
    if not 0 < cfg.risk_per_trade <= 1:
        raise ValueError("risk_per_trade must be in the range (0, 1]")
    if cfg.execution_timing not in {"close", "next_open"}:
        raise ValueError("execution_timing must be 'close' or 'next_open'")

    frames = {
        symbol: _prepare_symbol_frame(frame, strategy_name=strategy_name, config=cfg)
        for symbol, frame in price_data.items()
        if not frame.empty
    }
    dates = sorted(set().union(*(frame.index for frame in frames.values())))
    close_prices = pd.DataFrame({symbol: frame["close"] for symbol, frame in frames.items()})
    returns = close_prices.pct_change()

    cash = cfg.initial_capital
    positions: dict[str, dict[str, object]] = {}
    trade_rows: list[dict[str, object]] = []
    equity_rows: list[dict[str, object]] = []
    position_rows: list[dict[str, object]] = []

    for date in dates:
        current_prices = {
            symbol: float(frame.at[date, "close"])
            for symbol, frame in frames.items()
            if date in frame.index and pd.notna(frame.at[date, "close"])
        }
        fill_prices = {
            symbol: float(frame.at[date, "open" if cfg.execution_timing == "next_open" else "close"])
            for symbol, frame in frames.items()
            if date in frame.index
            and pd.notna(frame.at[date, "open" if cfg.execution_timing == "next_open" else "close"])
        }
        position_value = sum(
            float(position["shares"]) * current_prices.get(symbol, float(position["last_price"]))
            for symbol, position in positions.items()
        )
        equity = cash + position_value

        for symbol in list(positions):
            if symbol not in frames or date not in frames[symbol].index:
                continue
            row = frames[symbol].loc[date]
            position = positions[symbol]
            close = float(row["close"])
            fill = fill_prices.get(symbol, close)
            low = float(row["low"]) if pd.notna(row.get("low", np.nan)) else close
            position["last_price"] = close
            stop_price = float(position["stop_price"])
            stop_hit = low <= stop_price
            exit_signal = int(row["exec_signal_direction"]) < 0
            if not (stop_hit or exit_signal):
                continue

            raw_exit_price = stop_price if stop_hit else fill
            exit_price = raw_exit_price * (1 - cfg.slippage_pct)
            shares = float(position["shares"])
            exit_value = shares * exit_price
            commission = exit_value * cfg.commission_pct
            cash += exit_value - commission
            entry_value = float(position["entry_value"])
            pnl = exit_value - commission - entry_value
            trade_rows.append(
                {
                    "symbol": symbol,
                    "entry_date": position["entry_date"],
                    "exit_date": date,
                    "entry_price": position["entry_price"],
                    "exit_price": exit_price,
                    "shares": shares,
                    "pnl": pnl,
                    "return_pct": pnl / entry_value if entry_value else 0.0,
                    "traded_value": float(position["entry_value"]) + exit_value,
                    "exit_reason": "stop_loss" if stop_hit else "signal_exit",
                }
            )
            del positions[symbol]

        current_position_value = sum(
            float(position["shares"]) * current_prices.get(symbol, float(position["last_price"]))
            for symbol, position in positions.items()
        )
        equity = cash + current_position_value
        open_symbols = list(positions)

        candidates: list[tuple[str, float, float, float]] = []
        for symbol, frame in frames.items():
            if symbol in positions or symbol not in current_prices or date not in frame.index:
                continue
            row = frame.loc[date]
            if int(row["exec_signal_direction"]) <= 0:
                continue
            close = float(row["close"])
            fill = fill_prices.get(symbol, close)
            stop_price = float(row["exec_initial_stop_loss"])
            if not np.isfinite(stop_price) or stop_price >= fill:
                continue
            risk_per_share = fill - stop_price
            if risk_per_share <= 0:
                continue
            atr_rank = float(row["atr"]) if pd.notna(row["atr"]) else risk_per_share
            candidates.append((symbol, fill, stop_price, atr_rank))

        candidates.sort(key=lambda item: item[3], reverse=True)
        for symbol, close, stop_price, _ in candidates:
            if len(positions) >= cfg.max_positions:
                break
            if _is_correlated(symbol, open_symbols, returns, date, cfg):
                continue

            position_value = sum(
                float(position["shares"]) * current_prices.get(sym, float(position["last_price"]))
                for sym, position in positions.items()
            )
            equity = cash + position_value
            current_heat = sum(float(position["risk_dollars"]) for position in positions.values())
            risk_budget = equity * cfg.risk_per_trade
            remaining_heat = max(equity * cfg.max_portfolio_heat - current_heat, 0.0)
            risk_dollars = min(risk_budget, remaining_heat)
            if risk_dollars <= 0:
                break

            fill_price = close * (1 + cfg.slippage_pct)
            risk_per_share = fill_price - stop_price
            if risk_per_share <= 0:
                continue
            shares_by_risk = risk_dollars / risk_per_share
            max_value = equity * cfg.max_position_pct
            affordable_value = max(cash, 0.0) / (1 + cfg.commission_pct)
            target_value = min(shares_by_risk * fill_price, max_value, affordable_value)
            if target_value <= 0:
                continue
            shares = target_value / fill_price
            commission = target_value * cfg.commission_pct
            cash -= target_value + commission
            positions[symbol] = {
                "entry_date": date,
                "entry_price": fill_price,
                "shares": shares,
                "stop_price": stop_price,
                "risk_dollars": shares * risk_per_share,
                "entry_value": target_value + commission,
                "last_price": close,
            }
            open_symbols.append(symbol)

        final_position_value = sum(
            float(position["shares"]) * current_prices.get(symbol, float(position["last_price"]))
            for symbol, position in positions.items()
        )
        final_equity = cash + final_position_value
        equity_rows.append(
            {
                "date": date,
                "cash": cash,
                "position_value": final_position_value,
                "equity": final_equity,
                "open_positions": len(positions),
                "portfolio_heat": sum(float(p["risk_dollars"]) for p in positions.values()) / final_equity
                if final_equity
                else 0.0,
            }
        )
        for symbol, position in positions.items():
            price = current_prices.get(symbol, float(position["last_price"]))
            position_rows.append(
                {
                    "date": date,
                    "symbol": symbol,
                    "shares": position["shares"],
                    "close": price,
                    "market_value": float(position["shares"]) * price,
                    "stop_price": position["stop_price"],
                }
            )

    equity_curve = pd.DataFrame(equity_rows).set_index("date")
    trades = pd.DataFrame(trade_rows)
    positions_frame = pd.DataFrame(position_rows)
    benchmark_frame = _benchmark_curve(benchmark, cfg.initial_capital, dates)
    metrics = _summarize_portfolio(equity_curve, trades, benchmark_frame)
    return PortfolioResult(
        equity_curve=equity_curve,
        trades=trades,
        positions=positions_frame,
        metrics=metrics,
        benchmark_curve=benchmark_frame,
    )
