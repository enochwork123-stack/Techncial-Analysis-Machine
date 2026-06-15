from __future__ import annotations

from pathlib import Path

import pandas as pd


REQUIRED_HISTORY_COLUMNS = {"symbol", "start_date", "end_date"}
OPTIONAL_HISTORY_COLUMNS = {
    "company_name",
    "security_name",
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
}


def load_constituent_history(path: str | Path) -> pd.DataFrame:
    """Load point-in-time constituent intervals.

    Expected columns:
    - symbol
    - start_date
    - end_date, empty for still-active constituents

    Intervals are inclusive on both ends. Empty `end_date` means the symbol is
    active until replaced by future data.
    """
    frame = pd.read_csv(path)
    missing = REQUIRED_HISTORY_COLUMNS - set(frame.columns)
    if missing:
        raise ValueError(f"{path} is missing required columns: {sorted(missing)}")

    out = frame.copy()
    out["symbol"] = out["symbol"].astype(str).str.strip().str.upper()
    out["start_date"] = pd.to_datetime(out["start_date"], errors="coerce")
    out["end_date"] = pd.to_datetime(out["end_date"], errors="coerce")

    bad_start = out["start_date"].isna()
    if bad_start.any():
        bad_symbols = out.loc[bad_start, "symbol"].tolist()
        raise ValueError(f"Invalid start_date for symbols: {bad_symbols}")

    bad_interval = out["end_date"].notna() & (out["end_date"] < out["start_date"])
    if bad_interval.any():
        bad_symbols = out.loc[bad_interval, "symbol"].tolist()
        raise ValueError(f"end_date before start_date for symbols: {bad_symbols}")

    return out.sort_values(["symbol", "start_date"]).reset_index(drop=True)


def validate_constituent_history(history: pd.DataFrame) -> pd.DataFrame:
    """Return constituent-history data issues as a structured report."""
    issues: list[dict[str, object]] = []
    missing = REQUIRED_HISTORY_COLUMNS - set(history.columns)
    for column in sorted(missing):
        issues.append(
            {
                "severity": "error",
                "symbol": "",
                "issue": "missing_required_column",
                "detail": column,
            }
        )
    if missing:
        return pd.DataFrame(issues)

    frame = history.copy()
    frame["symbol"] = frame["symbol"].astype(str).str.strip().str.upper()
    frame["start_date"] = pd.to_datetime(frame["start_date"], errors="coerce")
    frame["end_date"] = pd.to_datetime(frame["end_date"], errors="coerce")

    for idx, row in frame.iterrows():
        symbol = row["symbol"]
        if not symbol or symbol == "NAN":
            issues.append(
                {
                    "severity": "error",
                    "symbol": "",
                    "issue": "missing_symbol",
                    "detail": f"row={idx}",
                }
            )
        if pd.isna(row["start_date"]):
            issues.append(
                {
                    "severity": "error",
                    "symbol": symbol,
                    "issue": "invalid_start_date",
                    "detail": f"row={idx}",
                }
            )
        if pd.notna(row["end_date"]) and pd.notna(row["start_date"]):
            if row["end_date"] < row["start_date"]:
                issues.append(
                    {
                        "severity": "error",
                        "symbol": symbol,
                        "issue": "invalid_interval",
                        "detail": "end_date before start_date",
                    }
                )

    frame = frame.dropna(subset=["start_date"]).sort_values(["symbol", "start_date"])
    for symbol, group in frame.groupby("symbol", sort=False):
        previous_end = None
        for _, row in group.iterrows():
            start_date = row["start_date"]
            end_date = row["end_date"]
            if previous_end is not None and start_date <= previous_end:
                issues.append(
                    {
                        "severity": "error",
                        "symbol": symbol,
                        "issue": "overlapping_intervals",
                        "detail": f"starts {start_date.date()} before prior interval ends",
                    }
                )
            previous_end = pd.Timestamp.max if pd.isna(end_date) else end_date

    open_ended_count = frame["end_date"].isna().sum()
    if len(frame) > 0 and open_ended_count == len(frame):
        issues.append(
            {
                "severity": "warning",
                "symbol": "",
                "issue": "all_intervals_open_ended",
                "detail": "likely current-list snapshot; not survivorship-bias-free",
            }
        )

    if len(frame) <= 1:
        issues.append(
            {
                "severity": "warning",
                "symbol": "",
                "issue": "insufficient_constituent_history",
                "detail": "historical Nasdaq-100 membership file is still a placeholder",
            }
        )

    known_columns = REQUIRED_HISTORY_COLUMNS | OPTIONAL_HISTORY_COLUMNS
    unknown_columns = sorted(set(history.columns) - known_columns)
    for column in unknown_columns:
        issues.append(
            {
                "severity": "info",
                "symbol": "",
                "issue": "unknown_optional_column",
                "detail": column,
            }
        )

    return pd.DataFrame(issues, columns=["severity", "symbol", "issue", "detail"])


def point_in_time_universe(history: pd.DataFrame, as_of: str | pd.Timestamp) -> list[str]:
    """Return symbols active on a given date from constituent intervals."""
    date = pd.Timestamp(as_of).normalize()
    start = pd.to_datetime(history["start_date"])
    end = pd.to_datetime(history["end_date"])
    active = (start <= date) & (end.isna() | (end >= date))
    return sorted(history.loc[active, "symbol"].astype(str).str.upper().unique().tolist())


def current_snapshot_as_history(
    snapshot: pd.DataFrame,
    start_date: str | pd.Timestamp,
    asof_column: str = "asof",
) -> pd.DataFrame:
    """Convert a current snapshot into open-ended intervals for prototyping.

    This is explicitly not survivorship-bias-free. It is useful for smoke tests
    and local development before a proper constituent history is available.
    """
    if "symbol" not in snapshot.columns:
        raise ValueError("snapshot must contain a 'symbol' column")

    out = pd.DataFrame()
    out["symbol"] = snapshot["symbol"].astype(str).str.strip().str.upper()
    out["start_date"] = pd.Timestamp(start_date).normalize()
    out["end_date"] = pd.NaT
    if "company_name" in snapshot.columns:
        out["company_name"] = snapshot["company_name"]
    if asof_column in snapshot.columns:
        out["source_asof"] = snapshot[asof_column]
    out["notes"] = "Current-list prototype interval; not survivorship-bias-free."
    return out.drop_duplicates(subset=["symbol"]).sort_values("symbol").reset_index(drop=True)
