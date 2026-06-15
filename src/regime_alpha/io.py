from __future__ import annotations

from pathlib import Path

import pandas as pd

from regime_alpha.data_quality import normalize_ohlcv_schema


def available_ohlcv_symbols(input_dir: str | Path = "data/raw/ohlcv") -> list[str]:
    path = Path(input_dir)
    if not path.exists():
        return []
    return sorted(file.stem.upper() for file in path.glob("*.csv"))


def load_ohlcv_file(path: str | Path) -> pd.DataFrame:
    frame = normalize_ohlcv_schema(pd.read_csv(path))
    if "date" not in frame.columns:
        raise ValueError(f"{path} must contain a date column")
    return frame.sort_values("date").set_index("date")


def load_ohlcv_directory(
    symbols: list[str] | None = None,
    input_dir: str | Path = "data/raw/ohlcv",
) -> dict[str, pd.DataFrame]:
    path = Path(input_dir)
    selected = [symbol.upper() for symbol in symbols] if symbols else available_ohlcv_symbols(path)
    data = {}
    for symbol in selected:
        file_path = path / f"{symbol}.csv"
        if file_path.exists():
            data[symbol] = load_ohlcv_file(file_path)
    return data

