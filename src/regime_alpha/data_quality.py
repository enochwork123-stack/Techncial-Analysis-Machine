from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd


REQUIRED_OHLCV_COLUMNS = {"date", "open", "high", "low", "close", "volume"}


@dataclass(frozen=True)
class QualityConfig:
    max_missing_business_days_pct: float = 0.08
    extreme_return_threshold: float = 0.35
    split_like_return_threshold: float = 0.45
    min_nonzero_volume_pct: float = 0.95


def normalize_ohlcv_schema(frame: pd.DataFrame) -> pd.DataFrame:
    """Normalize common OHLCV column casing and parse dates."""
    out = frame.copy()
    out.columns = [str(c).lower().replace(" ", "_") for c in out.columns]
    if "date" in out.columns:
        out["date"] = pd.to_datetime(out["date"], errors="coerce")
    for column in ["open", "high", "low", "close", "volume"]:
        if column in out.columns:
            out[column] = pd.to_numeric(out[column], errors="coerce")
    return out


def validate_ohlcv(frame: pd.DataFrame, symbol: str = "", config: QualityConfig | None = None) -> pd.DataFrame:
    """Return OHLCV data issues as a structured report."""
    cfg = config or QualityConfig()
    issues: list[dict[str, object]] = []
    data = normalize_ohlcv_schema(frame)

    missing_columns = REQUIRED_OHLCV_COLUMNS - set(data.columns)
    for column in sorted(missing_columns):
        issues.append(
            {
                "severity": "error",
                "symbol": symbol,
                "date": pd.NaT,
                "issue": "missing_required_column",
                "detail": column,
            }
        )
    if missing_columns:
        return pd.DataFrame(issues)

    invalid_dates = data["date"].isna()
    if invalid_dates.any():
        issues.append(
            {
                "severity": "error",
                "symbol": symbol,
                "date": pd.NaT,
                "issue": "invalid_dates",
                "detail": int(invalid_dates.sum()),
            }
        )

    duplicate_dates = data["date"].duplicated(keep=False)
    for date in data.loc[duplicate_dates, "date"].dropna().drop_duplicates():
        issues.append(
            {
                "severity": "error",
                "symbol": symbol,
                "date": date,
                "issue": "duplicate_date",
                "detail": "",
            }
        )

    data = data.dropna(subset=["date"]).sort_values("date").reset_index(drop=True)
    bad_ohlc = (
        (data["high"] < data[["open", "close", "low"]].max(axis=1))
        | (data["low"] > data[["open", "close", "high"]].min(axis=1))
        | (data[["open", "high", "low", "close"]] <= 0).any(axis=1)
    )
    for _, row in data.loc[bad_ohlc].iterrows():
        issues.append(
            {
                "severity": "error",
                "symbol": symbol,
                "date": row["date"],
                "issue": "invalid_ohlc",
                "detail": "",
            }
        )

    zero_volume = data["volume"].fillna(0) <= 0
    nonzero_volume_pct = 1 - float(zero_volume.mean()) if len(data) else 0.0
    if len(data) and nonzero_volume_pct < cfg.min_nonzero_volume_pct:
        issues.append(
            {
                "severity": "warning",
                "symbol": symbol,
                "date": pd.NaT,
                "issue": "high_zero_volume_frequency",
                "detail": f"nonzero_volume_pct={nonzero_volume_pct:.3f}",
            }
        )

    returns = data["close"].pct_change().replace([np.inf, -np.inf], np.nan)
    extreme_returns = returns.abs() > cfg.extreme_return_threshold
    for idx, value in returns.loc[extreme_returns].items():
        issue = (
            "split_like_return"
            if abs(value) > cfg.split_like_return_threshold
            else "extreme_return"
        )
        issues.append(
            {
                "severity": "warning",
                "symbol": symbol,
                "date": data.loc[idx, "date"],
                "issue": issue,
                "detail": f"return={value:.4f}",
            }
        )

    if len(data) >= 2:
        expected = pd.bdate_range(data["date"].min(), data["date"].max())
        observed = pd.DatetimeIndex(data["date"])
        missing_business_days = expected.difference(observed)
        missing_pct = len(missing_business_days) / len(expected) if len(expected) else 0.0
        if missing_pct > cfg.max_missing_business_days_pct:
            issues.append(
                {
                    "severity": "warning",
                    "symbol": symbol,
                    "date": pd.NaT,
                    "issue": "many_missing_business_days",
                    "detail": f"missing={len(missing_business_days)} pct={missing_pct:.3f}",
                }
            )

    return pd.DataFrame(issues, columns=["severity", "symbol", "date", "issue", "detail"])

