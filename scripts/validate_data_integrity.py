from __future__ import annotations

import argparse
from pathlib import Path

import pandas as pd

from regime_alpha.data_quality import validate_ohlcv
from regime_alpha.universe import load_constituent_history, validate_constituent_history


def validate_ohlcv_directory(input_dir: Path) -> pd.DataFrame:
    reports: list[pd.DataFrame] = []
    for path in sorted(input_dir.glob("*.csv")):
        symbol = path.stem.upper()
        frame = pd.read_csv(path)
        report = validate_ohlcv(frame, symbol=symbol)
        if not report.empty:
            reports.append(report)
    if reports:
        return pd.concat(reports, ignore_index=True)
    return pd.DataFrame(columns=["severity", "symbol", "date", "issue", "detail"])


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--constituents",
        default="data/manual/nasdaq100_constituents_history.csv",
        help="Historical constituent interval CSV.",
    )
    parser.add_argument(
        "--ohlcv-dir",
        default="data/raw/ohlcv",
        help="Directory containing per-symbol OHLCV CSV files.",
    )
    parser.add_argument(
        "--output-dir",
        default="data/processed",
        help="Directory for validation reports.",
    )
    args = parser.parse_args()

    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    history = load_constituent_history(args.constituents)
    constituent_report = validate_constituent_history(history)
    constituent_report.to_csv(output_dir / "constituent_history_quality_report.csv", index=False)

    ohlcv_dir = Path(args.ohlcv_dir)
    if ohlcv_dir.exists():
        ohlcv_report = validate_ohlcv_directory(ohlcv_dir)
    else:
        ohlcv_report = pd.DataFrame(
            [
                {
                    "severity": "warning",
                    "symbol": "",
                    "date": pd.NaT,
                    "issue": "missing_ohlcv_directory",
                    "detail": str(ohlcv_dir),
                }
            ]
        )
    ohlcv_report.to_csv(output_dir / "ohlcv_quality_report.csv", index=False)

    error_count = int(
        (constituent_report["severity"].eq("error").sum() if not constituent_report.empty else 0)
        + (ohlcv_report["severity"].eq("error").sum() if not ohlcv_report.empty else 0)
    )
    warning_count = int(
        (constituent_report["severity"].eq("warning").sum() if not constituent_report.empty else 0)
        + (ohlcv_report["severity"].eq("warning").sum() if not ohlcv_report.empty else 0)
    )
    print(f"Data integrity reports written to {output_dir}")
    print(f"Errors: {error_count}; warnings: {warning_count}")


if __name__ == "__main__":
    main()
