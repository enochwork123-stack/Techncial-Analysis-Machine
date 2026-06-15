from __future__ import annotations

import pandas as pd

from scripts.import_nasdaq100_wikipedia_history import (
    ChangeRow,
    normalize_components,
    reconstruct_intervals,
)


def test_reconstruct_intervals_walks_changes_backward() -> None:
    components = normalize_components(
        pd.DataFrame(
            {
                "ticker": ["AAA", "BBB"],
                "company": ["Alpha", "Beta"],
            }
        )
    )
    changes = [
        ChangeRow(
            date=pd.Timestamp("2024-01-02"),
            added_symbol="AAA",
            added_name="Alpha",
            removed_symbol="CCC",
            removed_name="Charlie",
            reason="test change",
        )
    ]

    intervals = reconstruct_intervals(components, changes, source_asof="2026-06-14")

    aaa = intervals.loc[intervals["symbol"] == "AAA"].iloc[0]
    ccc = intervals.loc[intervals["symbol"] == "CCC"].iloc[0]
    assert str(aaa["start_date"]) == "2024-01-02"
    assert str(ccc["end_date"]) == "2024-01-01"
    assert intervals["source"].str.contains("wikipedia").all()

