from __future__ import annotations

import pandas as pd

from regime_alpha.data_quality import validate_ohlcv


def test_validate_ohlcv_flags_duplicate_dates_and_invalid_prices() -> None:
    frame = pd.DataFrame(
        {
            "date": ["2024-01-02", "2024-01-02", "2024-01-03"],
            "open": [10, 11, 12],
            "high": [11, 10, 13],
            "low": [9, 12, 11],
            "close": [10.5, 11.5, 12.5],
            "volume": [100, 100, 100],
        }
    )

    report = validate_ohlcv(frame, symbol="TEST")

    assert "duplicate_date" in report["issue"].tolist()
    assert "invalid_ohlc" in report["issue"].tolist()


def test_validate_ohlcv_flags_extreme_returns_and_zero_volume_frequency() -> None:
    frame = pd.DataFrame(
        {
            "date": pd.bdate_range("2024-01-01", periods=4),
            "open": [10, 11, 30, 31],
            "high": [10, 11, 30, 31],
            "low": [10, 11, 30, 31],
            "close": [10, 11, 30, 31],
            "volume": [0, 0, 0, 100],
        }
    )

    report = validate_ohlcv(frame, symbol="TEST")

    assert "split_like_return" in report["issue"].tolist()
    assert "high_zero_volume_frequency" in report["issue"].tolist()

