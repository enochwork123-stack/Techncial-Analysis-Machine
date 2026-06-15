from __future__ import annotations

import argparse
from pathlib import Path

from regime_alpha.robustness import generate_group_memos, group_strategy_summary, screen_cached_strategies


def parse_symbols(value: str) -> list[str] | None:
    symbols = [item.strip().upper() for item in value.split(",") if item.strip()]
    return symbols or None


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--symbols", default="")
    parser.add_argument("--input-dir", default="data/raw/ohlcv")
    parser.add_argument("--output-dir", default="data/processed/robustness")
    args = parser.parse_args()

    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    screen = screen_cached_strategies(parse_symbols(args.symbols), input_dir=args.input_dir)
    grouped = group_strategy_summary(screen)
    memos = generate_group_memos(grouped)
    screen.to_csv(output_dir / "strategy_screen.csv", index=False)
    grouped.to_csv(output_dir / "group_strategy_summary.csv", index=False)
    memos.to_csv(output_dir / "group_memos.csv", index=False)
    print(screen.to_string(index=False) if not screen.empty else "No cached symbols found.")
    print(f"Wrote robustness reports to {output_dir}")


if __name__ == "__main__":
    main()
