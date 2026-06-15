from __future__ import annotations

import argparse
import csv
import json
import urllib.request
from pathlib import Path


NASDAQ100_URL = "https://api.nasdaq.com/api/quote/list-type/nasdaq100"


def fetch_current_nasdaq100() -> tuple[str, list[dict]]:
    request = urllib.request.Request(
        NASDAQ100_URL,
        headers={
            "User-Agent": "Mozilla/5.0",
            "Accept": "application/json",
        },
    )
    with urllib.request.urlopen(request, timeout=30) as response:
        payload = json.loads(response.read().decode("utf-8"))
    rows = payload["data"]["data"]["rows"]
    asof = payload["data"]["date"]
    return asof, rows


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", default="data/raw/current_nasdaq100.csv")
    args = parser.parse_args()

    asof, rows = fetch_current_nasdaq100()
    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)

    with output.open("w", newline="") as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=["asof", "symbol", "company_name", "market_cap", "last_sale_price"],
        )
        writer.writeheader()
        for row in rows:
            writer.writerow(
                {
                    "asof": asof,
                    "symbol": row["symbol"],
                    "company_name": row["companyName"],
                    "market_cap": row["marketCap"].replace(",", ""),
                    "last_sale_price": row["lastSalePrice"].replace("$", "").replace(",", ""),
                }
            )
    print(f"Wrote {len(rows)} rows to {output}")


if __name__ == "__main__":
    main()

