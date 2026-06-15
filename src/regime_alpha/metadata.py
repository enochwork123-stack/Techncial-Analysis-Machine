from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


def file_sha256(path: str | Path) -> str:
    digest = hashlib.sha256()
    with Path(path).open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def build_cache_metadata(
    data_path: str | Path,
    *,
    symbol: str,
    source: str,
    adjustment: str,
    start_date: str | None,
    end_date: str | None,
    extra: dict[str, Any] | None = None,
) -> dict[str, Any]:
    path = Path(data_path)
    metadata = {
        "symbol": symbol,
        "source": source,
        "adjustment": adjustment,
        "start_date": start_date,
        "end_date": end_date,
        "downloaded_at_utc": datetime.now(timezone.utc).isoformat(),
        "file_name": path.name,
        "file_size_bytes": path.stat().st_size,
        "sha256": file_sha256(path),
    }
    if extra:
        metadata.update(extra)
    return metadata


def write_metadata(metadata: dict[str, Any], path: str | Path) -> None:
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(metadata, indent=2, sort_keys=True) + "\n", encoding="utf-8")

