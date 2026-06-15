from __future__ import annotations

import pandas as pd

from regime_alpha.universe import (
    current_snapshot_as_history,
    point_in_time_universe,
    validate_constituent_history,
)


def test_point_in_time_universe_uses_inclusive_intervals() -> None:
    history = pd.DataFrame(
        {
            "symbol": ["AAA", "BBB", "CCC"],
            "start_date": pd.to_datetime(["2020-01-01", "2021-01-01", "2020-01-01"]),
            "end_date": pd.to_datetime(["2020-12-31", None, "2022-01-31"]),
        }
    )

    assert point_in_time_universe(history, "2020-12-31") == ["AAA", "CCC"]
    assert point_in_time_universe(history, "2021-01-01") == ["BBB", "CCC"]
    assert point_in_time_universe(history, "2023-01-01") == ["BBB"]


def test_current_snapshot_as_history_creates_open_ended_intervals() -> None:
    snapshot = pd.DataFrame(
        {
            "symbol": ["msft", "MSFT", "nvda"],
            "company_name": ["Microsoft", "Microsoft duplicate", "NVIDIA"],
            "asof": ["2026-06-11", "2026-06-11", "2026-06-11"],
        }
    )

    history = current_snapshot_as_history(snapshot, "2026-06-11")

    assert history["symbol"].tolist() == ["MSFT", "NVDA"]
    assert history["end_date"].isna().all()


def test_validate_constituent_history_flags_placeholder_like_data() -> None:
    history = pd.DataFrame(
        {
            "symbol": ["QQQ"],
            "start_date": ["1999-03-10"],
            "end_date": [None],
        }
    )

    report = validate_constituent_history(history)

    assert "insufficient_constituent_history" in report["issue"].tolist()
    assert "all_intervals_open_ended" in report["issue"].tolist()


def test_validate_constituent_history_flags_overlapping_intervals() -> None:
    history = pd.DataFrame(
        {
            "symbol": ["AAA", "AAA"],
            "start_date": ["2020-01-01", "2020-06-01"],
            "end_date": ["2020-12-31", None],
        }
    )

    report = validate_constituent_history(history)

    assert "overlapping_intervals" in report["issue"].tolist()
