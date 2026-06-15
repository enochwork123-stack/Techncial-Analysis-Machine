const state = {
  lastRows: [],
  lastColumns: [],
  lastEquity: [],
  lastBenchmark: [],
  lastTiming: []
};

const strategies = [
  "ema_cross",
  "supertrend",
  "macd_momentum",
  "rsi_pullback",
  "donchian_breakout",
  "pullback_continuation",
  "bollinger_mean_reversion",
  "volume_breakout"
];

function $(id) {
  return document.getElementById(id);
}

function asNumber(id) {
  return Number($(id).value);
}

function formatValue(value, key) {
  if (value === null || value === undefined || Number.isNaN(value)) return "";
  const number = Number(value);
  if (!Number.isFinite(number)) return String(value);
  if (
    key.includes("return")
    || key.includes("drawdown")
    || key.includes("rate")
    || key.includes("exposure")
    || key.includes("cagr")
    || key.includes("turnover")
  ) {
    return `${(number * 100).toFixed(2)}%`;
  }
  if (key.includes("trade") || key.includes("positions")) return number.toFixed(0);
  return number.toFixed(3);
}

function setStatus(message, isError = false) {
  $("status").textContent = message;
  $("status").className = isError ? "status error" : "status";
}

function renderMetrics(metrics) {
  const keys = [
    "total_return",
    "cagr",
    "max_drawdown",
    "sharpe",
    "number_of_trades",
    "win_rate",
    "average_exposure",
    "annual_turnover",
    "benchmark_return",
    "excess_return",
    "profit_factor",
    "number_of_symbols",
    "number_of_groups",
    "timing_return",
    "excess_vs_timing"
  ];
  $("metrics").innerHTML = keys
    .filter((key) => metrics && Object.prototype.hasOwnProperty.call(metrics, key))
    .map((key) => `<div class="metric"><span>${key.replaceAll("_", " ")}</span><strong>${formatValue(metrics[key], key)}</strong></div>`)
    .join("");
}

function renderChart(equityRows, benchmarkRows = [], timingRows = []) {
  state.lastEquity = equityRows || [];
  state.lastBenchmark = benchmarkRows || [];
  state.lastTiming = timingRows || [];
  const canvas = $("chart");
  const ctx = canvas.getContext("2d");
  const rect = canvas.getBoundingClientRect();
  const dpr = window.devicePixelRatio || 1;
  canvas.width = Math.floor(rect.width * dpr);
  canvas.height = Math.floor(360 * dpr);
  ctx.scale(dpr, dpr);
  const width = rect.width;
  const height = 360;
  ctx.clearRect(0, 0, width, height);
  ctx.fillStyle = "#0f171b";
  ctx.fillRect(0, 0, width, height);

  const series = [];
  if (equityRows && equityRows.length) series.push({rows: equityRows, key: "equity", color: "#22c55e"});
  if (benchmarkRows && benchmarkRows.length) series.push({rows: benchmarkRows, key: "equity", color: "#38bdf8"});
  if (timingRows && timingRows.length) series.push({rows: timingRows, key: "equity", color: "#f59e0b"});
  if (!series.length) return;

  const values = series.flatMap((item) => item.rows.map((row) => Number(row[item.key])).filter(Number.isFinite));
  const min = Math.min(...values);
  const max = Math.max(...values);
  const pad = 28;
  const span = max - min || 1;

  ctx.strokeStyle = "#22343a";
  ctx.lineWidth = 1;
  ctx.font = "12px system-ui";
  ctx.fillStyle = "#8aa0a8";
  for (let i = 0; i <= 4; i += 1) {
    const y = pad + ((height - pad * 2) * i) / 4;
    ctx.beginPath();
    ctx.moveTo(pad, y);
    ctx.lineTo(width - pad, y);
    ctx.stroke();
    const value = max - (span * i) / 4;
    ctx.fillText(value.toFixed(0), 8, y + 4);
  }

  for (const item of series) {
    ctx.strokeStyle = item.color;
    ctx.lineWidth = 2;
    ctx.beginPath();
    item.rows.forEach((row, index) => {
      const x = pad + ((width - pad * 2) * index) / Math.max(item.rows.length - 1, 1);
      const y = height - pad - ((Number(row[item.key]) - min) / span) * (height - pad * 2);
      if (index === 0) ctx.moveTo(x, y);
      else ctx.lineTo(x, y);
    });
    ctx.stroke();
  }
}

function renderMemos(memos) {
  $("memos").innerHTML = (memos || []).map((memo) => `
    <div class="memo">
      <strong>${memo.group} / ${memo.strategy}</strong>
      <div>${memo.symbols}</div>
      <p>${memo.memo}</p>
    </div>
  `).join("");
}

function renderTable(rows) {
  state.lastRows = rows || [];
  state.lastColumns = rows && rows.length ? Object.keys(rows[0]) : [];
  if (!rows || !rows.length) {
    $("resultTable").innerHTML = "";
    return;
  }
  const head = `<thead><tr>${state.lastColumns.map((column) => `<th>${column}</th>`).join("")}</tr></thead>`;
  const body = rows.map((row) => {
    const cells = state.lastColumns.map((column) => `<td>${formatValue(row[column], column)}</td>`).join("");
    return `<tr>${cells}</tr>`;
  }).join("");
  $("resultTable").innerHTML = `${head}<tbody>${body}</tbody>`;
}

async function refreshSymbols() {
  const response = await fetch("/api/symbols");
  const payload = await response.json();
  $("symbolList").innerHTML = payload.symbols.map((symbol) => `<span class="chip">${symbol}</span>`).join("");
  if (!$("symbols").value && payload.symbols.length) {
    $("symbols").value = payload.symbols.slice(0, 10).join(", ");
  }
  setStatus(`${payload.symbols.length} cached symbol(s) available.`);
}

async function runBacktest() {
  setStatus("Running...");
  renderMetrics({});
  renderTable([]);
  renderChart([]);
  renderMemos([]);
  const mode = $("mode").value;
  const payload = {
    symbols: $("symbols").value.split(",").map((item) => item.trim()).filter(Boolean),
    strategy: $("strategy").value,
    initial_capital: asNumber("initialCapital"),
    risk_per_trade: asNumber("riskPerTrade"),
    max_portfolio_heat: asNumber("maxHeat"),
    max_positions: asNumber("maxPositions"),
    max_position_pct: asNumber("maxPositionPct"),
    commission_pct: asNumber("commissionPct"),
    slippage_pct: asNumber("slippagePct"),
    use_correlation_filter: $("correlationFilter").checked,
    execution_timing: $("executionTiming").value,
    benchmark_symbol: $("benchmarkSymbol").value.trim(),
    train_years: asNumber("trainYears"),
    test_years: asNumber("testYears"),
    objective: "sharpe",
    selection_mode: "plateau"
  };
  const endpoint = mode === "portfolio"
    ? "/api/portfolio"
    : mode === "walkForward"
      ? "/api/walk-forward"
      : mode === "robustness"
        ? "/api/robustness"
        : "/api/symbol-suite";
  const response = await fetch(endpoint, {
    method: "POST",
    headers: {"Content-Type": "application/json"},
    body: JSON.stringify(payload)
  });
  const data = await response.json();
  if (!response.ok) {
    setStatus(data.error || "Backtest failed.", true);
    return;
  }
  $("tableTitle").textContent = mode === "portfolio"
    ? "Portfolio trades"
    : mode === "walkForward"
      ? "Walk-forward windows"
      : mode === "robustness"
        ? "Robustness strategy screen"
        : "Strategy comparison";
  renderMetrics(data.metrics || {});
  renderTable(mode === "portfolio" ? data.trades : data.rows);
  renderChart(data.equity || [], data.benchmark || [], data.timing || []);
  renderMemos(data.memos || []);
  setStatus(data.message || "Done.");
}

function downloadCsv() {
  if (!state.lastRows.length) return;
  const rows = [state.lastColumns.join(",")].concat(
    state.lastRows.map((row) => state.lastColumns.map((column) => JSON.stringify(row[column] ?? "")).join(","))
  );
  const blob = new Blob([rows.join("\n")], {type: "text/csv"});
  const url = URL.createObjectURL(blob);
  const link = document.createElement("a");
  link.href = url;
  link.download = "regime-alpha-results.csv";
  link.click();
  URL.revokeObjectURL(url);
}

function init() {
  $("strategy").innerHTML = strategies.map((strategy) => `<option value="${strategy}">${strategy}</option>`).join("");
  $("refreshSymbols").addEventListener("click", refreshSymbols);
  $("run").addEventListener("click", runBacktest);
  $("downloadCsv").addEventListener("click", downloadCsv);
  $("mode").addEventListener("change", () => {
    $("strategyWrap").style.display = $("mode").value === "symbol" ? "none" : "grid";
  });
  refreshSymbols().catch((error) => setStatus(error.message, true));
}

init();
