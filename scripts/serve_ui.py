from __future__ import annotations

import argparse
import json
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlparse

import pandas as pd

from regime_alpha.backtest import ExecutionConfig
from regime_alpha.io import available_ohlcv_symbols, load_ohlcv_directory
from regime_alpha.portfolio import PortfolioConfig, run_portfolio_backtest
from regime_alpha.research import run_strategy_suite, summarize_strategy_suite
from regime_alpha.robustness import generate_group_memos, group_strategy_summary, screen_cached_strategies
from regime_alpha.walk_forward import WalkForwardConfig, run_walk_forward


ROOT = Path(__file__).resolve().parents[1]
WEB_DIR = ROOT / "web"


def _json_safe(value):
    if isinstance(value, float) and (pd.isna(value) or value in {float("inf"), float("-inf")}):
        return None
    if isinstance(value, pd.Timestamp):
        return value.isoformat()
    return value


def _frame_records(frame: pd.DataFrame, limit: int | None = None) -> list[dict[str, object]]:
    data = frame.copy()
    if limit is not None:
        data = data.tail(limit)
    data = data.replace([float("inf"), float("-inf")], pd.NA)
    return [
        {key: _json_safe(value) for key, value in row.items()}
        for row in data.to_dict(orient="records")
    ]


def _read_json(handler: BaseHTTPRequestHandler) -> dict[str, object]:
    length = int(handler.headers.get("Content-Length", "0"))
    if length == 0:
        return {}
    return json.loads(handler.rfile.read(length).decode("utf-8"))


class UiHandler(BaseHTTPRequestHandler):
    def _send_json(self, payload: dict[str, object], status: int = 200) -> None:
        body = json.dumps(payload, default=str).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _send_file(self, path: Path) -> None:
        if not path.exists() or not path.is_file():
            self.send_error(404)
            return
        content_type = {
            ".html": "text/html",
            ".css": "text/css",
            ".js": "application/javascript",
        }.get(path.suffix, "application/octet-stream")
        body = path.read_bytes()
        self.send_response(200)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self) -> None:
        parsed = urlparse(self.path)
        if parsed.path == "/api/symbols":
            self._send_json({"symbols": available_ohlcv_symbols(ROOT / "data/raw/ohlcv")})
            return
        path = WEB_DIR / "index.html" if parsed.path == "/" else WEB_DIR / parsed.path.lstrip("/")
        self._send_file(path)

    def do_POST(self) -> None:
        try:
            payload = _read_json(self)
            if self.path == "/api/portfolio":
                self._handle_portfolio(payload)
                return
            if self.path == "/api/symbol-suite":
                self._handle_symbol_suite(payload)
                return
            if self.path == "/api/walk-forward":
                self._handle_walk_forward(payload)
                return
            if self.path == "/api/robustness":
                self._handle_robustness(payload)
                return
            self.send_error(404)
        except Exception as exc:
            self._send_json({"error": str(exc)}, status=400)

    def _symbols(self, payload: dict[str, object]) -> list[str] | None:
        symbols = payload.get("symbols") or []
        cleaned = [str(symbol).strip().upper() for symbol in symbols if str(symbol).strip()]
        return cleaned or None

    def _handle_portfolio(self, payload: dict[str, object]) -> None:
        price_data = load_ohlcv_directory(self._symbols(payload), ROOT / "data/raw/ohlcv")
        if not price_data:
            raise ValueError("No cached OHLCV data found for the selected symbols.")
        config = PortfolioConfig(
            initial_capital=float(payload.get("initial_capital", 100_000)),
            risk_per_trade=float(payload.get("risk_per_trade", 0.01)),
            max_portfolio_heat=float(payload.get("max_portfolio_heat", 0.20)),
            max_positions=int(payload.get("max_positions", 20)),
            max_position_pct=float(payload.get("max_position_pct", 0.20)),
            commission_pct=float(payload.get("commission_pct", 0.001)),
            slippage_pct=float(payload.get("slippage_pct", 0.0005)),
            use_correlation_filter=bool(payload.get("use_correlation_filter", True)),
            execution_timing=str(payload.get("execution_timing", "close")),
        )
        benchmark = None
        benchmark_symbol = str(payload.get("benchmark_symbol", "")).strip().upper()
        if benchmark_symbol:
            benchmark_data = load_ohlcv_directory([benchmark_symbol], ROOT / "data/raw/ohlcv")
            benchmark = benchmark_data.get(benchmark_symbol)
        result = run_portfolio_backtest(
            price_data,
            strategy_name=str(payload.get("strategy", "ema_cross")),
            config=config,
            benchmark=benchmark,
        )
        self._send_json(
            {
                "message": f"Portfolio run complete for {len(price_data)} symbol(s).",
                "metrics": result.metrics,
                "trades": _frame_records(result.trades, limit=500),
                "equity": _frame_records(result.equity_curve.reset_index(), limit=500),
                "benchmark": _frame_records(result.benchmark_curve.reset_index(), limit=500),
            }
        )

    def _handle_symbol_suite(self, payload: dict[str, object]) -> None:
        symbols = self._symbols(payload)
        if not symbols or len(symbols) != 1:
            raise ValueError("Single symbol suite requires exactly one symbol.")
        price_data = load_ohlcv_directory(symbols, ROOT / "data/raw/ohlcv")
        if not price_data:
            raise ValueError(f"No cached OHLCV data found for {symbols[0]}.")
        config = ExecutionConfig(
            initial_capital=float(payload.get("initial_capital", 100_000)),
            commission_pct=float(payload.get("commission_pct", 0.001)),
            slippage_pct=float(payload.get("slippage_pct", 0.0005)),
        )
        results = run_strategy_suite(next(iter(price_data.values())), execution_config=config)
        summary = summarize_strategy_suite(results)
        best_metrics = results[str(summary.iloc[0]["strategy"])].metrics if not summary.empty else {}
        self._send_json(
            {
                "message": f"Strategy suite complete for {symbols[0]}.",
                "metrics": best_metrics,
                "rows": _frame_records(summary),
            }
        )

    def _handle_walk_forward(self, payload: dict[str, object]) -> None:
        symbols = self._symbols(payload)
        if not symbols or len(symbols) != 1:
            raise ValueError("Walk-forward validation requires exactly one symbol.")
        price_data = load_ohlcv_directory(symbols, ROOT / "data/raw/ohlcv")
        if not price_data:
            raise ValueError(f"No cached OHLCV data found for {symbols[0]}.")
        result = run_walk_forward(
            next(iter(price_data.values())),
            strategy_name=str(payload.get("strategy", "ema_cross")),
            config=WalkForwardConfig(
                train_years=int(payload.get("train_years", 4)),
                test_years=int(payload.get("test_years", 1)),
                objective=str(payload.get("objective", "sharpe")),
                selection_mode=str(payload.get("selection_mode", "plateau")),
            ),
            execution_config=ExecutionConfig(
                initial_capital=float(payload.get("initial_capital", 100_000)),
                commission_pct=float(payload.get("commission_pct", 0.001)),
                slippage_pct=float(payload.get("slippage_pct", 0.0005)),
            ),
        )
        self._send_json(
            {
                "message": f"Walk-forward run complete for {symbols[0]}.",
                "metrics": result.metrics,
                "rows": _frame_records(result.windows),
                "equity": _frame_records(result.equity_curve.reset_index(), limit=500),
                "benchmark": _frame_records(result.benchmark_curve.reset_index(), limit=500),
                "timing": _frame_records(result.timing_curve.reset_index(), limit=500),
                "trades": _frame_records(result.trades, limit=500),
            }
        )

    def _handle_robustness(self, payload: dict[str, object]) -> None:
        screen = screen_cached_strategies(self._symbols(payload), input_dir=str(ROOT / "data/raw/ohlcv"))
        grouped = group_strategy_summary(screen)
        memos = generate_group_memos(grouped)
        self._send_json(
            {
                "message": f"Robustness report complete for {len(screen)} cached symbol(s).",
                "metrics": {
                    "number_of_symbols": float(len(screen)),
                    "number_of_groups": float(grouped["group"].nunique()) if not grouped.empty else 0.0,
                },
                "rows": _frame_records(screen),
                "groups": _frame_records(grouped),
                "memos": _frame_records(memos),
            }
        )


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8765)
    args = parser.parse_args()
    server = ThreadingHTTPServer((args.host, args.port), UiHandler)
    print(f"Serving Regime Alpha Lab at http://{args.host}:{args.port}")
    server.serve_forever()


if __name__ == "__main__":
    main()
