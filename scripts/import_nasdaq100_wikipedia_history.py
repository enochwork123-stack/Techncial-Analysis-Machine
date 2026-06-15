from __future__ import annotations

import argparse
from io import StringIO
from dataclasses import dataclass
from pathlib import Path

import pandas as pd
import requests


WIKIPEDIA_URL = "https://en.wikipedia.org/wiki/Nasdaq-100"


@dataclass(frozen=True)
class ChangeRow:
    date: pd.Timestamp
    added_symbol: str
    added_name: str
    removed_symbol: str
    removed_name: str
    reason: str


def _flatten_columns(frame: pd.DataFrame) -> pd.DataFrame:
    out = frame.copy()
    flattened = []
    for column in out.columns:
        if isinstance(column, tuple):
            parts = [str(part) for part in column if "Unnamed" not in str(part)]
            flattened.append("_".join(parts).strip().lower())
        else:
            flattened.append(str(column).strip().lower())
    out.columns = flattened
    return out


def _clean_symbol(value: object) -> str:
    if pd.isna(value):
        return ""
    return str(value).strip().upper().replace(".", "-")


def _clean_text(value: object) -> str:
    if pd.isna(value):
        return ""
    return str(value).strip()


def read_wikipedia_tables(url: str = WIKIPEDIA_URL) -> tuple[pd.DataFrame, pd.DataFrame]:
    response = requests.get(
        url,
        headers={"User-Agent": "regime-alpha-framework/0.1 data research"},
        timeout=30,
    )
    response.raise_for_status()
    tables = pd.read_html(StringIO(response.text))
    components = None
    changes = None
    for table in tables:
        frame = _flatten_columns(table)
        columns = set(frame.columns)
        if {"ticker", "company"}.issubset(columns):
            components = frame
        if any("date" in c for c in columns) and any("added" in c for c in columns):
            if any("removed" in c for c in columns):
                changes = frame
    if components is None:
        raise ValueError("Could not find current Nasdaq-100 components table")
    if changes is None:
        raise ValueError("Could not find Nasdaq-100 component changes table")
    return components, changes


def normalize_components(components: pd.DataFrame) -> pd.DataFrame:
    out = pd.DataFrame()
    out["symbol"] = components["ticker"].map(_clean_symbol)
    out["company_name"] = components["company"].map(_clean_text)
    out["exchange"] = "NASDAQ"
    return out.loc[out["symbol"] != ""].drop_duplicates("symbol").reset_index(drop=True)


def normalize_changes(changes: pd.DataFrame) -> list[ChangeRow]:
    def find_column(*needles: str) -> str:
        for column in changes.columns:
            if all(needle in column for needle in needles):
                return column
        raise ValueError(f"Could not find column matching {needles}")

    date_col = find_column("date")
    added_symbol_col = find_column("added", "ticker")
    added_name_col = find_column("added", "security")
    removed_symbol_col = find_column("removed", "ticker")
    removed_name_col = find_column("removed", "security")
    reason_col = find_column("reason") if any("reason" in c for c in changes.columns) else changes.columns[-1]

    rows: list[ChangeRow] = []
    for _, row in changes.iterrows():
        date = pd.to_datetime(row[date_col], errors="coerce")
        if pd.isna(date):
            continue
        rows.append(
            ChangeRow(
                date=pd.Timestamp(date).normalize(),
                added_symbol=_clean_symbol(row[added_symbol_col]),
                added_name=_clean_text(row[added_name_col]),
                removed_symbol=_clean_symbol(row[removed_symbol_col]),
                removed_name=_clean_text(row[removed_name_col]),
                reason=_clean_text(row[reason_col]),
            )
        )
    return sorted(rows, key=lambda item: item.date, reverse=True)


def reconstruct_intervals(
    components: pd.DataFrame,
    changes: list[ChangeRow],
    source_asof: str,
) -> pd.DataFrame:
    active: dict[str, dict[str, object]] = {}
    intervals: list[dict[str, object]] = []

    for _, row in components.iterrows():
        active[row["symbol"]] = {
            "symbol": row["symbol"],
            "company_name": row["company_name"],
            "exchange": row["exchange"],
            "end_date": pd.NaT,
            "notes": "Current component; start date inferred from Wikipedia change history when available.",
        }

    for change in changes:
        if change.added_symbol and change.added_symbol in active:
            interval = active.pop(change.added_symbol)
            interval["start_date"] = change.date
            interval["source_reason"] = change.reason
            intervals.append(interval)

        if change.removed_symbol and change.removed_symbol not in active:
            active[change.removed_symbol] = {
                "symbol": change.removed_symbol,
                "company_name": change.removed_name,
                "exchange": "NASDAQ",
                "end_date": change.date - pd.Timedelta(days=1),
                "notes": "Removed component reconstructed backward from Wikipedia change history.",
                "source_reason": change.reason,
            }

    earliest_change = min((row.date for row in changes), default=pd.Timestamp("1985-01-31"))
    for interval in active.values():
        end_date = interval.get("end_date")
        if pd.notna(end_date) and pd.Timestamp(end_date) < earliest_change:
            interval["start_date"] = pd.Timestamp(end_date)
            interval["notes"] = (
                "Only terminal membership date is known from the earliest available "
                "Wikipedia change row; true start date is earlier."
            )
        else:
            interval["start_date"] = earliest_change
        interval.setdefault(
            "notes",
            "Start date is the earliest available change date; true membership may begin earlier.",
        )
        intervals.append(interval)

    out = pd.DataFrame(intervals)
    out["cusip"] = ""
    out["figi"] = ""
    out["perm_id"] = ""
    out["successor_symbol"] = ""
    out["delisted"] = False
    out["delisting_date"] = pd.NaT
    out["source"] = "wikipedia_nasdaq100_component_changes_reconstruction"
    out["source_asof"] = source_asof
    out["start_date"] = pd.to_datetime(out["start_date"]).dt.date
    out["end_date"] = pd.to_datetime(out["end_date"]).dt.date
    out["delisting_date"] = pd.to_datetime(out["delisting_date"]).dt.date
    ordered_columns = [
        "symbol",
        "start_date",
        "end_date",
        "company_name",
        "exchange",
        "cusip",
        "figi",
        "perm_id",
        "successor_symbol",
        "delisted",
        "delisting_date",
        "source",
        "source_asof",
        "notes",
    ]
    return out[ordered_columns].sort_values(["symbol", "start_date"]).reset_index(drop=True)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--url", default=WIKIPEDIA_URL)
    parser.add_argument("--output", default="data/manual/nasdaq100_constituents_history.csv")
    parser.add_argument("--source-asof", default=pd.Timestamp.today().date().isoformat())
    args = parser.parse_args()

    components_raw, changes_raw = read_wikipedia_tables(args.url)
    components = normalize_components(components_raw)
    changes = normalize_changes(changes_raw)
    intervals = reconstruct_intervals(components, changes, args.source_asof)

    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    intervals.to_csv(output, index=False)
    print(f"Wrote {len(intervals)} reconstructed intervals to {output}")
    print("Source: Wikipedia Nasdaq-100 current components and component changes tables")
    print("Warning: this is an approximate public-source reconstruction, not vendor-grade PIT data.")


if __name__ == "__main__":
    main()
