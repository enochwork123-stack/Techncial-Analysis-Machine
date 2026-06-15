from __future__ import annotations

from dataclasses import dataclass

import pandas as pd

from regime_alpha.indicators import atr, hurst_exponent, kaufman_efficiency_ratio


@dataclass(frozen=True)
class RegimeThresholds:
    high_hurst: float = 0.55
    low_hurst: float = 0.45
    high_ker: float = 0.35
    low_ker: float = 0.15
    high_atr_pct: float = 0.04


def classify_regime(
    df: pd.DataFrame,
    hurst_window: int = 120,
    ker_window: int = 60,
    atr_window: int = 20,
    thresholds: RegimeThresholds | None = None,
) -> pd.DataFrame:
    """Classify each bar into broad strategy families.

    The output is intentionally coarse. Exact strategy parameters should be
    selected by robust walk-forward validation, not by fitting this classifier
    tightly to one period.
    """
    t = thresholds or RegimeThresholds()
    close = df["close"]

    out = pd.DataFrame(index=df.index)
    out["hurst"] = hurst_exponent(close, window=hurst_window)
    out["ker"] = kaufman_efficiency_ratio(close, window=ker_window)
    out["atr"] = atr(df, window=atr_window)
    out["atr_pct"] = out["atr"] / close

    trend = (out["hurst"] > t.high_hurst) & (out["ker"] > t.high_ker)
    mean_reversion = (out["hurst"] < t.low_hurst) & (out["ker"] < t.low_ker)
    volatility_expansion = out["atr_pct"] > t.high_atr_pct

    out["regime"] = "neutral"
    out.loc[trend, "regime"] = "trend"
    out.loc[mean_reversion, "regime"] = "mean_reversion"
    out.loc[volatility_expansion & ~trend, "regime"] = "momentum"

    out["strategy_family"] = out["regime"].map(
        {
            "trend": "supertrend_or_ema_cross",
            "mean_reversion": "rsi_or_bollinger",
            "momentum": "macd_momentum",
            "neutral": "cash_or_low_conviction",
        }
    )
    return out

