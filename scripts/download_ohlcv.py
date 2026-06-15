from __future__ import annotations

import argparse
from pathlib import Path

import pandas as pd
import yfinance as yf

from regime_alpha.data_quality import validate_ohlcv
from regime_alpha.metadata import build_cache_metadata, write_metadata


def read_symbols(path: Path) -> list[str]:
    frame = pd.read_csv(path)
    if "symbol" not in frame.columns:
        raise ValueError(f"{path} must contain a 'symbol' column")
    return frame["symbol"].dropna().astype(str).unique().tolist()


def normalize_ohlcv(frame: pd.DataFrame, symbol: str) -> pd.DataFrame:
    if frame.empty:
        return frame
    source = frame.copy()
    if isinstance(source.columns, pd.MultiIndex):
        if symbol in source.columns.get_level_values(-1):
            source = source.xs(symbol, axis=1, level=-1)
        else:
            source.columns = [
                "_".join(str(part) for part in column if str(part))
                for column in source.columns.to_flat_index()
            ]

    out = source.reset_index()
    out.columns = [str(c).lower().replace(" ", "_") for c in out.columns]
    out["symbol"] = symbol
    if "datetime" in out.columns and "date" not in out.columns:
        out = out.rename(columns={"datetime": "date"})
    keep = [c for c in ["date", "open", "high", "low", "close", "volume"] if c in out.columns]
    return out[["symbol", *keep]]


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--universe", default="data/raw/current_nasdaq100.csv")
    parser.add_argument("--start", default="2010-01-01")
    parser.add_argument("--end", default=None)
    parser.add_argument("--output-dir", default="data/raw/ohlcv")
    parser.add_argument("--source", default="yfinance")
    parser.add_argument(
        "--adjustment",
        choices=["auto_adjust", "raw"],
        default="auto_adjust",
        help="Use auto-adjusted OHLCV for research, or raw Yahoo OHLCV for TradingView/MCP calibration.",
    )
    parser.add_argument("--quality-report", default="data/processed/ohlcv_quality_report.csv")
    parser.add_argument("--metadata-dir", default="data/raw/ohlcv_metadata")
    args = parser.parse_args()

    symbols = read_symbols(Path(args.universe))
    output_dir = Path(args.output_dir)
    metadata_dir = Path(args.metadata_dir)
    quality_report_path = Path(args.quality_report)
    output_dir.mkdir(parents=True, exist_ok=True)
    metadata_dir.mkdir(parents=True, exist_ok=True)

    failures: list[str] = []
    quality_reports: list[pd.DataFrame] = []
    for symbol in symbols:
        print(f"Downloading {symbol}...")
        try:
            frame = yf.download(
                symbol,
                start=args.start,
                end=args.end,
                auto_adjust=args.adjustment == "auto_adjust",
                progress=False,
                threads=False,
            )
            normalized = normalize_ohlcv(frame, symbol)
            if normalized.empty:
                failures.append(symbol)
                continue
            output_path = output_dir / f"{symbol}.csv"
            normalized.to_csv(output_path, index=False)

            quality = validate_ohlcv(normalized, symbol=symbol)
            if not quality.empty:
                quality_reports.append(quality)

            metadata = build_cache_metadata(
                output_path,
                symbol=symbol,
                source=args.source,
                adjustment=args.adjustment,
                start_date=args.start,
                end_date=args.end,
                extra={"rows": int(len(normalized)), "quality_issue_count": int(len(quality))},
            )
            write_metadata(metadata, metadata_dir / f"{symbol}.json")
        except Exception as exc:
            print(f"Failed {symbol}: {exc}")
            failures.append(symbol)

    quality_report_path.parent.mkdir(parents=True, exist_ok=True)
    if quality_reports:
        pd.concat(quality_reports, ignore_index=True).to_csv(quality_report_path, index=False)
    else:
        pd.DataFrame(columns=["severity", "symbol", "date", "issue", "detail"]).to_csv(
            quality_report_path, index=False
        )

    if failures:
        print("Failures:", ", ".join(failures))


if __name__ == "__main__":
    main()
