from __future__ import annotations

import numpy as np
import pandas as pd


def kaufman_efficiency_ratio(close: pd.Series, window: int = 60) -> pd.Series:
    """Kaufman's Efficiency Ratio: directional change divided by path length."""
    direction = close.diff(window).abs()
    volatility = close.diff().abs().rolling(window).sum()
    return direction / volatility.replace(0, np.nan)


def hurst_exponent(close: pd.Series, window: int = 120, max_lag: int = 20) -> pd.Series:
    """Rolling Hurst exponent using log-log lag variance regression.

    Interpretation:
    - H < 0.5: mean-reverting / anti-persistent
    - H ~= 0.5: random walk-like
    - H > 0.5: trending / persistent
    """
    if max_lag < 3:
        raise ValueError("max_lag must be at least 3")

    lags = np.arange(2, max_lag + 1)
    log_lags = np.log(lags)

    def _hurst(values: np.ndarray) -> float:
        if np.isnan(values).any():
            return np.nan
        variances = []
        for lag in lags:
            diff = values[lag:] - values[:-lag]
            var = np.var(diff)
            variances.append(var)
        variances_arr = np.asarray(variances)
        valid = variances_arr > 0
        if valid.sum() < 3:
            return np.nan
        slope, _ = np.polyfit(log_lags[valid], np.log(variances_arr[valid]), 1)
        return float(slope / 2.0)

    return close.rolling(window).apply(_hurst, raw=True)


def true_range(df: pd.DataFrame) -> pd.Series:
    high_low = df["high"] - df["low"]
    high_close = (df["high"] - df["close"].shift()).abs()
    low_close = (df["low"] - df["close"].shift()).abs()
    return pd.concat([high_low, high_close, low_close], axis=1).max(axis=1)


def atr(df: pd.DataFrame, window: int = 20) -> pd.Series:
    return true_range(df).ewm(alpha=1 / window, adjust=False).mean()


def ema(close: pd.Series, window: int) -> pd.Series:
    return close.ewm(span=window, adjust=False).mean()


def rsi(close: pd.Series, window: int = 14) -> pd.Series:
    delta = close.diff()
    gain = delta.clip(lower=0)
    loss = -delta.clip(upper=0)
    avg_gain = gain.ewm(alpha=1 / window, adjust=False).mean()
    avg_loss = loss.ewm(alpha=1 / window, adjust=False).mean()
    rs = avg_gain / avg_loss.replace(0, np.nan)
    return 100 - (100 / (1 + rs))


def bollinger_bands(
    close: pd.Series, window: int = 20, std_mult: float = 2.0
) -> pd.DataFrame:
    middle = close.rolling(window).mean()
    std = close.rolling(window).std(ddof=0)
    return pd.DataFrame(
        {
            "bb_lower": middle - std_mult * std,
            "bb_middle": middle,
            "bb_upper": middle + std_mult * std,
        }
    )


def donchian_channels(df: pd.DataFrame, window: int = 20) -> pd.DataFrame:
    return pd.DataFrame(
        {
            "donchian_upper": df["high"].rolling(window).max(),
            "donchian_lower": df["low"].rolling(window).min(),
            "donchian_middle": (
                df["high"].rolling(window).max() + df["low"].rolling(window).min()
            )
            / 2,
        },
        index=df.index,
    )


def macd(
    close: pd.Series, fast: int = 12, slow: int = 26, signal: int = 9
) -> pd.DataFrame:
    fast_ema = close.ewm(span=fast, adjust=False).mean()
    slow_ema = close.ewm(span=slow, adjust=False).mean()
    macd_line = fast_ema - slow_ema
    signal_line = macd_line.ewm(span=signal, adjust=False).mean()
    return pd.DataFrame(
        {
            "macd": macd_line,
            "macd_signal": signal_line,
            "macd_hist": macd_line - signal_line,
        }
    )


def rate_of_change(close: pd.Series, window: int = 20) -> pd.Series:
    return close.pct_change(window)


def supertrend(df: pd.DataFrame, atr_window: int = 10, multiplier: float = 3.0) -> pd.DataFrame:
    """Compute Supertrend bands and direction.

    Direction is `1` for bullish and `-1` for bearish.
    """
    hl2 = (df["high"] + df["low"]) / 2
    atr_value = atr(df, atr_window)
    basic_upper = hl2 + multiplier * atr_value
    basic_lower = hl2 - multiplier * atr_value

    final_upper = basic_upper.copy()
    final_lower = basic_lower.copy()
    direction = pd.Series(1, index=df.index, dtype="int8")
    trend = pd.Series(index=df.index, dtype="float64")

    for i in range(1, len(df)):
        prev = df.index[i - 1]
        cur = df.index[i]
        prev_close = df["close"].iloc[i - 1]
        close = df["close"].iloc[i]

        if basic_upper.loc[cur] < final_upper.loc[prev] or prev_close > final_upper.loc[prev]:
            final_upper.loc[cur] = basic_upper.loc[cur]
        else:
            final_upper.loc[cur] = final_upper.loc[prev]

        if basic_lower.loc[cur] > final_lower.loc[prev] or prev_close < final_lower.loc[prev]:
            final_lower.loc[cur] = basic_lower.loc[cur]
        else:
            final_lower.loc[cur] = final_lower.loc[prev]

        if direction.loc[prev] == -1 and close > final_upper.loc[cur]:
            direction.loc[cur] = 1
        elif direction.loc[prev] == 1 and close < final_lower.loc[cur]:
            direction.loc[cur] = -1
        else:
            direction.loc[cur] = direction.loc[prev]

        trend.loc[cur] = final_lower.loc[cur] if direction.loc[cur] == 1 else final_upper.loc[cur]

    if len(df):
        first = df.index[0]
        trend.loc[first] = final_lower.loc[first]

    return pd.DataFrame(
        {
            "supertrend": trend,
            "supertrend_upper": final_upper,
            "supertrend_lower": final_lower,
            "supertrend_direction": direction,
        },
        index=df.index,
    )
