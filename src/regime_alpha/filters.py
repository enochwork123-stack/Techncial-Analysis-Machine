from __future__ import annotations

import pandas as pd

from regime_alpha.indicators import ema, rate_of_change, rsi


def market_trend_filter(benchmark: pd.DataFrame, ma_window: int = 200) -> pd.Series:
    """True when the benchmark trades above its long-term moving average."""
    close = benchmark["close"]
    return close > close.rolling(ma_window).mean()


def relative_strength_filter(
    asset: pd.DataFrame,
    benchmark: pd.DataFrame,
    window: int = 60,
) -> pd.Series:
    """True when asset return over `window` exceeds benchmark return."""
    asset_return = asset["close"].pct_change(window)
    benchmark_return = benchmark["close"].pct_change(window).reindex(asset.index)
    return asset_return > benchmark_return


def volume_filter(
    df: pd.DataFrame,
    window: int = 20,
    multiplier: float = 1.1,
) -> pd.Series:
    return df["volume"] > df["volume"].rolling(window).mean() * multiplier


def momentum_filter(
    df: pd.DataFrame,
    mode: str = "rsi",
    rsi_window: int = 14,
    rsi_threshold: float = 50,
    rsi_ceiling: float | None = 80,
    roc_window: int = 20,
) -> pd.Series:
    close = df["close"]
    if mode == "rsi":
        values = rsi(close, rsi_window)
        passed = values > rsi_threshold
        if rsi_ceiling is not None:
            passed &= values < rsi_ceiling
        return passed
    if mode == "roc":
        return rate_of_change(close, roc_window) > 0
    raise ValueError("mode must be 'rsi' or 'roc'")


def ema_trend_filter(
    df: pd.DataFrame,
    trend_window: int = 50,
    long_window: int | None = 200,
    require_rising: bool = True,
) -> pd.Series:
    trend = ema(df["close"], trend_window)
    passed = df["close"] > trend
    if long_window is not None:
        long = ema(df["close"], long_window)
        passed &= trend > long
    if require_rising:
        passed &= trend > trend.shift()
    return passed

