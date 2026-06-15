from __future__ import annotations

import pandas as pd

from regime_alpha.filters import ema_trend_filter, relative_strength_filter, volume_filter
from regime_alpha.indicators import donchian_channels, supertrend
from regime_alpha.strategies import (
    donchian_breakout_signals,
    pullback_continuation_signals,
    strategy_parameter_grids,
    volume_breakout_signals,
)


def _sample_prices(length: int = 80) -> pd.DataFrame:
    index = pd.date_range("2024-01-01", periods=length, freq="B")
    close = pd.Series(range(100, 100 + length), index=index, dtype="float64")
    return pd.DataFrame(
        {
            "open": close - 0.5,
            "high": close + 1,
            "low": close - 1,
            "close": close,
            "volume": [100 + i * 2 for i in range(length)],
        },
        index=index,
    )


def test_donchian_channels_preserve_index() -> None:
    prices = _sample_prices()
    channels = donchian_channels(prices, window=20)

    assert channels.index.equals(prices.index)
    assert {"donchian_upper", "donchian_lower", "donchian_middle"}.issubset(channels.columns)


def test_supertrend_returns_direction_column() -> None:
    prices = _sample_prices()
    values = supertrend(prices, atr_window=10, multiplier=3)

    assert "supertrend_direction" in values.columns
    assert set(values["supertrend_direction"].dropna().unique()).issubset({-1, 1})


def test_volume_breakout_signal_schema() -> None:
    prices = _sample_prices()
    signals = volume_breakout_signals(
        prices,
        breakout_window=10,
        volume_window=5,
        volume_multiplier=1.0,
        trend_window=20,
    )

    assert {"signal_direction", "initial_stop_loss"}.issubset(signals.columns)
    assert signals["signal_direction"].isin([-1, 0, 1]).all()


def test_pullback_and_donchian_signal_schema() -> None:
    prices = _sample_prices(260)

    pullback = pullback_continuation_signals(prices)
    donchian = donchian_breakout_signals(prices)

    assert pullback["signal_direction"].isin([-1, 0, 1]).all()
    assert donchian["signal_direction"].isin([-1, 0, 1]).all()


def test_filters_and_parameter_grids() -> None:
    asset = _sample_prices(260)
    benchmark = asset.copy()
    benchmark["close"] = benchmark["close"] * 0.9

    assert volume_filter(asset, window=5, multiplier=0.5).dropna().any()
    assert ema_trend_filter(asset, trend_window=20, long_window=50).dropna().any()
    assert relative_strength_filter(asset, benchmark, window=20).dropna().any()
    assert "supertrend" in strategy_parameter_grids()

