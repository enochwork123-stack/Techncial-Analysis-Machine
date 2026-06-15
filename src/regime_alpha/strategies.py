from __future__ import annotations

import pandas as pd

from regime_alpha.filters import ema_trend_filter, volume_filter
from regime_alpha.indicators import atr, bollinger_bands, ema, macd, rsi, supertrend


def _standard_signal(index: pd.Index, direction: pd.Series, initial_stop: pd.Series) -> pd.DataFrame:
    return pd.DataFrame(
        {
            "signal_direction": direction.astype("int8"),
            "initial_stop_loss": initial_stop,
        },
        index=index,
    )


def rsi_pullback_signals(
    df: pd.DataFrame,
    rsi_window: int = 14,
    entry_threshold: float = 40,
    exit_threshold: float = 60,
    long_ma_window: int = 200,
) -> pd.DataFrame:
    """Long pullback signal: enter oversold while long-term trend is positive."""
    close = df["close"]
    osc = rsi(close, rsi_window)
    long_ma = close.rolling(long_ma_window).mean()
    trend_ok = close > long_ma
    entry = (osc < entry_threshold) & trend_ok
    exit_ = osc > exit_threshold
    direction = pd.Series(0, index=df.index)
    direction.loc[entry] = 1
    direction.loc[exit_] = -1
    return _standard_signal(df.index, direction, pd.Series(float("nan"), index=df.index))


def bollinger_mean_reversion_signals(
    df: pd.DataFrame,
    window: int = 20,
    std_mult: float = 2.0,
) -> pd.DataFrame:
    close = df["close"]
    bands = bollinger_bands(close, window, std_mult)
    entry = close < bands["bb_lower"]
    exit_ = close > bands["bb_middle"]
    direction = pd.Series(0, index=df.index)
    direction.loc[entry] = 1
    direction.loc[exit_] = -1
    return _standard_signal(df.index, direction, pd.Series(float("nan"), index=df.index))


def macd_momentum_signals(
    df: pd.DataFrame,
    fast: int = 12,
    slow: int = 26,
    signal: int = 9,
) -> pd.DataFrame:
    m = macd(df["close"], fast, slow, signal)
    entry = (m["macd"].shift() < m["macd_signal"].shift()) & (m["macd"] >= m["macd_signal"])
    exit_ = (m["macd"].shift() > m["macd_signal"].shift()) & (m["macd"] <= m["macd_signal"])
    direction = pd.Series(0, index=df.index)
    direction.loc[entry] = 1
    direction.loc[exit_] = -1
    return _standard_signal(df.index, direction, pd.Series(float("nan"), index=df.index))


def ema_cross_signals(
    df: pd.DataFrame,
    fast_window: int = 20,
    slow_window: int = 50,
) -> pd.DataFrame:
    close = df["close"]
    fast = close.ewm(span=fast_window, adjust=False).mean()
    slow = close.ewm(span=slow_window, adjust=False).mean()
    entry = (fast.shift() < slow.shift()) & (fast >= slow)
    exit_ = (fast.shift() > slow.shift()) & (fast <= slow)
    direction = pd.Series(0, index=df.index)
    direction.loc[entry] = 1
    direction.loc[exit_] = -1
    return _standard_signal(df.index, direction, pd.Series(float("nan"), index=df.index))


def supertrend_signals(
    df: pd.DataFrame,
    atr_window: int = 10,
    multiplier: float = 3.0,
) -> pd.DataFrame:
    st = supertrend(df, atr_window=atr_window, multiplier=multiplier)
    direction = pd.Series(0, index=df.index)
    entry = (st["supertrend_direction"].shift() < 0) & (st["supertrend_direction"] > 0)
    exit_ = (st["supertrend_direction"].shift() > 0) & (st["supertrend_direction"] < 0)
    direction.loc[entry] = 1
    direction.loc[exit_] = -1
    return _standard_signal(df.index, direction, st["supertrend"])


def donchian_breakout_signals(
    df: pd.DataFrame,
    entry_window: int = 20,
    exit_window: int = 10,
) -> pd.DataFrame:
    entry_upper = df["high"].rolling(entry_window).max().shift()
    exit_lower = df["low"].rolling(exit_window).min().shift()
    entry = df["close"] > entry_upper
    exit_ = df["close"] < exit_lower
    direction = pd.Series(0, index=df.index)
    direction.loc[entry] = 1
    direction.loc[exit_] = -1
    return _standard_signal(df.index, direction, exit_lower)


def volume_breakout_signals(
    df: pd.DataFrame,
    breakout_window: int = 20,
    volume_window: int = 20,
    volume_multiplier: float = 1.1,
    trend_window: int = 50,
) -> pd.DataFrame:
    breakout_level = df["high"].rolling(breakout_window).max().shift()
    trend_ok = ema_trend_filter(df, trend_window=trend_window, long_window=None, require_rising=True)
    volume_ok = volume_filter(df, window=volume_window, multiplier=volume_multiplier)
    entry = (df["close"] > breakout_level) & trend_ok & volume_ok
    exit_ = df["close"] < ema(df["close"], trend_window)
    initial_stop = df["close"] - atr(df, 14) * 2.5
    direction = pd.Series(0, index=df.index)
    direction.loc[entry] = 1
    direction.loc[exit_] = -1
    return _standard_signal(df.index, direction, initial_stop)


def pullback_continuation_signals(
    df: pd.DataFrame,
    pullback_ema_window: int = 20,
    trend_window: int = 50,
    long_window: int = 200,
    atr_window: int = 14,
    atr_stop_multiplier: float = 2.5,
) -> pd.DataFrame:
    close = df["close"]
    pullback_ema = ema(close, pullback_ema_window)
    trend_ema = ema(close, trend_window)
    long_ema = ema(close, long_window)
    trend_ok = (close > trend_ema) & (trend_ema > long_ema)
    touched_pullback_zone = df["low"] <= pullback_ema
    reclaim = (close > pullback_ema) & (close.shift() <= pullback_ema.shift())
    bullish_candle = close > df["open"]
    entry = trend_ok & touched_pullback_zone & reclaim & bullish_candle
    exit_ = close < trend_ema
    initial_stop = close - atr(df, atr_window) * atr_stop_multiplier
    direction = pd.Series(0, index=df.index)
    direction.loc[entry] = 1
    direction.loc[exit_] = -1
    return _standard_signal(df.index, direction, initial_stop)


def strategy_parameter_grids() -> dict[str, dict[str, list[int | float]]]:
    """Small, explainable parameter grids for walk-forward research."""
    return {
        "ema_cross": {
            "fast_window": [5, 10, 15, 20],
            "slow_window": [20, 30, 50, 60],
        },
        "supertrend": {
            "atr_window": [7, 10, 14],
            "multiplier": [2.0, 2.5, 3.0, 3.5],
        },
        "donchian_breakout": {
            "entry_window": [10, 20, 40, 55],
            "exit_window": [5, 10, 20],
        },
        "rsi_pullback": {
            "rsi_window": [10, 14, 21],
            "entry_threshold": [35, 40, 45],
            "exit_threshold": [55, 60, 65],
        },
        "bollinger_mean_reversion": {
            "window": [15, 20, 30],
            "std_mult": [1.5, 2.0, 2.5],
        },
        "macd_momentum": {
            "fast": [8, 12],
            "slow": [21, 26],
            "signal": [5, 9],
        },
        "volume_breakout": {
            "breakout_window": [10, 20, 40],
            "volume_multiplier": [1.0, 1.2, 1.5],
            "trend_window": [50, 75, 100],
        },
        "pullback_continuation": {
            "pullback_ema_window": [10, 20],
            "trend_window": [50, 75],
            "long_window": [150, 200],
            "atr_stop_multiplier": [2.0, 2.5, 3.0],
        },
    }
