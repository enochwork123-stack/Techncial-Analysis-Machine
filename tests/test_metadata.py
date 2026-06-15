from __future__ import annotations

import json

from regime_alpha.metadata import build_cache_metadata, write_metadata


def test_build_and_write_cache_metadata(tmp_path) -> None:
    data_path = tmp_path / "MSFT.csv"
    data_path.write_text("date,close\n2024-01-01,100\n", encoding="utf-8")

    metadata = build_cache_metadata(
        data_path,
        symbol="MSFT",
        source="unit-test",
        adjustment="auto_adjust",
        start_date="2024-01-01",
        end_date=None,
        extra={"rows": 1},
    )
    output_path = tmp_path / "MSFT.json"
    write_metadata(metadata, output_path)

    saved = json.loads(output_path.read_text(encoding="utf-8"))
    assert saved["symbol"] == "MSFT"
    assert saved["rows"] == 1
    assert len(saved["sha256"]) == 64
