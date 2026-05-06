"""
Real-time traffic dashboard.

Generates HTTP traffic against a target URL, then serves a live web dashboard
at http://localhost:9999 with auto-updating charts.

Usage:
    python scripts/traffic_dashboard.py
    python scripts/traffic_dashboard.py --gen-token
    python scripts/traffic_dashboard.py --url http://localhost:8000/health --workers 16 --duration 120
    python scripts/traffic_dashboard.py --gen-token --url http://localhost:8000/api/businesses?searchQuery=&city=Arizona --workers 24 --duration 180
"""

from __future__ import annotations

import argparse
import base64
import hashlib
import hmac
import json
import math
import queue
import threading
import time
import urllib.error
import urllib.request
import webbrowser
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import List

# ---------------------------------------------------------------------------
# Config defaults
# ---------------------------------------------------------------------------
DEFAULT_TARGET = (
    "http://localhost:8000/api/businesses"
    "?searchQuery=&city=Arizona&minStars=&searchPath=auto"
)
DEFAULT_PORT = 9999

# ---------------------------------------------------------------------------
# JWT helper (HS256, stdlib only)
# ---------------------------------------------------------------------------
def _b64url(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode()


def generate_dev_token(
    secret: str = "dev-secret-change-me",
    issuer: str = "yelp-auth",
    audience: str = "yelp-api",
    subject: str = "dev-load-tester",
    roles: list | None = None,
    ttl_seconds: int = 7200,
) -> str:
    """Generate a signed HS256 JWT using only stdlib (no PyJWT needed at runtime)."""
    now = int(datetime.now(timezone.utc).timestamp())
    header = _b64url(json.dumps({"alg": "HS256", "typ": "JWT"}).encode())
    payload = _b64url(json.dumps({
        "sub": subject,
        "iss": issuer,
        "aud": audience,
        "iat": now,
        "exp": now + ttl_seconds,
        "roles": roles or ["business:read", "recommendation:read"],
      "dev_load_test": True,
    }).encode())
    sig = _b64url(hmac.new(
        secret.encode(),
        f"{header}.{payload}".encode(),
        hashlib.sha256,
    ).digest())
    return f"{header}.{payload}.{sig}"


# ---------------------------------------------------------------------------
# Shared state
# ---------------------------------------------------------------------------
class SharedState:
    def __init__(self):
        self._lock = threading.Lock()
        self.total_requests = 0
        self.total_ok = 0
        self.total_errors = 0
        self._all_latencies: List[float] = []
        self._sec_ok = 0
        self._sec_errors = 0
        self._sec_latencies: List[float] = []

    def record(self, ok: bool, latency_ms: float):
        with self._lock:
            self.total_requests += 1
            self._all_latencies.append(latency_ms)
            if ok:
                self.total_ok += 1
                self._sec_ok += 1
            else:
                self.total_errors += 1
                self._sec_errors += 1
            self._sec_latencies.append(latency_ms)

    def flush_second(self):
        with self._lock:
            ok = self._sec_ok
            errors = self._sec_errors
            lats = self._sec_latencies[:]
            self._sec_ok = 0
            self._sec_errors = 0
            self._sec_latencies.clear()
            return ok, errors, lats

    def snapshot(self):
        with self._lock:
            return (
                self.total_requests,
                self.total_ok,
                self.total_errors,
                self._all_latencies[:],
            )


def _percentile(values: List[float], p: float) -> float:
    if not values:
        return 0.0
    ordered = sorted(values)
    pos = (len(ordered) - 1) * p
    lo = math.floor(pos)
    hi = math.ceil(pos)
    if lo == hi:
        return ordered[lo]
    return ordered[lo] + (ordered[hi] - ordered[lo]) * (pos - lo)


# ---------------------------------------------------------------------------
# SSE subscriber management + snapshot store
# ---------------------------------------------------------------------------
_subscribers: List[queue.Queue] = []
_subscribers_lock = threading.Lock()
_snapshot_lock = threading.Lock()
_timeline_snapshot: List[dict] = []
_last_summary: dict = {}


def _broadcast(data: dict):
    msg = "data: " + json.dumps(data) + "\n\n"
    with _subscribers_lock:
        for q in _subscribers[:]:
            try:
                q.put_nowait(msg)
            except queue.Full:
                pass
    # keep rolling snapshot for /snapshot endpoint
    if data.get("type") != "done":
        with _snapshot_lock:
            _timeline_snapshot.append(data)
            if len(_timeline_snapshot) > 3600:
                _timeline_snapshot.pop(0)
    else:
        with _snapshot_lock:
            _last_summary.update(data)


def _subscribe() -> queue.Queue:
    q: queue.Queue = queue.Queue(maxsize=120)
    with _subscribers_lock:
        _subscribers.append(q)
    return q


def _unsubscribe(q: queue.Queue):
    with _subscribers_lock:
        try:
            _subscribers.remove(q)
        except ValueError:
            pass


# ---------------------------------------------------------------------------
# Stress presets
# ---------------------------------------------------------------------------
PRESETS: dict[str, dict] = {
    "low":    {"workers": 4,  "duration": 60,  "timeout": 5.0},
    "medium": {"workers": 12, "duration": 90,  "timeout": 5.0},
    "heavy":  {"workers": 24, "duration": 120, "timeout": 4.0},
}

# Set by POST /start — signals main() to begin traffic generation
_run_event: threading.Event = threading.Event()
_run_config: dict = {}


# ---------------------------------------------------------------------------
# HTML dashboard
# ---------------------------------------------------------------------------
_HTML = """\
<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Traffic Dashboard</title>
<script src="https://cdn.jsdelivr.net/npm/chart.js@4.4.3/dist/chart.umd.min.js"></script>
<style>
  :root {
    --bg: #0f172a;
    --panel: rgba(15,23,42,0.9);
    --border: #1e293b;
    --ink: #e2e8f0;
    --muted: #64748b;
    --accent: #38bdf8;
    --green: #34d399;
    --yellow: #fbbf24;
    --red: #f87171;
    --purple: #a78bfa;
  }
  /* ── Selector view ─────────────────────────────────────── */
  #selector-view {
    max-width: 860px;
    margin: 60px auto 0;
  }
  .sel-header { text-align: center; margin-bottom: 48px; }
  .sel-header h1 { font-size: 28px; letter-spacing: .02em; }
  .sel-header p { color: var(--muted); margin-top: 10px; font-size: 15px; }
  .preset-grid {
    display: grid;
    grid-template-columns: repeat(3, 1fr);
    gap: 18px;
    margin-bottom: 36px;
  }
  .preset-card {
    background: rgba(30,41,59,0.8);
    border: 2px solid var(--border);
    border-radius: 18px;
    padding: 32px 22px 26px;
    cursor: pointer;
    transition: border-color .2s, box-shadow .2s, transform .15s;
    text-align: center;
    user-select: none;
  }
  .preset-card:hover { border-color: #334155; transform: translateY(-3px); }
  .preset-card.selected.low    { border-color: var(--green);  box-shadow: 0 0 22px rgba(52,211,153,.28); }
  .preset-card.selected.medium { border-color: var(--yellow); box-shadow: 0 0 22px rgba(251,191,36,.28); }
  .preset-card.selected.heavy  { border-color: var(--red);    box-shadow: 0 0 22px rgba(248,113,113,.28); }
  .preset-icon { font-size: 38px; margin-bottom: 14px; }
  .preset-name { font-size: 22px; font-weight: 700; margin-bottom: 12px; }
  .preset-name.low    { color: var(--green); }
  .preset-name.medium { color: var(--yellow); }
  .preset-name.heavy  { color: var(--red); }
  .preset-stats { font-size: 13px; color: var(--muted); line-height: 2; }
  .preset-desc { font-size: 12px; color: #475569; margin-top: 12px; font-style: italic; }
  .target-row {
    display: grid;
    grid-template-columns: 1fr 1fr;
    gap: 14px;
    margin-bottom: 26px;
  }
  .target-field {
    display: flex;
    flex-direction: column;
    gap: 8px;
    font-size: 12px;
    color: var(--muted);
    letter-spacing: 0.05em;
    text-transform: uppercase;
  }
  .target-field select {
    background: rgba(30,41,59,0.9);
    border: 1px solid var(--border);
    border-radius: 12px;
    color: var(--ink);
    font-size: 14px;
    padding: 12px 14px;
    outline: none;
  }
  .target-field select:focus { border-color: var(--accent); }
  .start-row { text-align: center; }
  #start-btn {
    background: rgba(56,189,248,.18);
    border: 2px solid var(--accent);
    border-radius: 14px;
    color: var(--accent);
    cursor: pointer;
    font-size: 17px;
    font-weight: 700;
    padding: 14px 52px;
    transition: background .2s, opacity .2s;
    letter-spacing: .03em;
  }
  #start-btn:hover:not(:disabled) { background: rgba(56,189,248,.30); }
  #start-btn:disabled { opacity: .35; cursor: not-allowed; }
  #preset-detail { margin-top: 14px; font-size: 13px; color: var(--muted); min-height: 20px; }
  /* ── Dashboard view ────────────────────────────────────── */
  * { box-sizing: border-box; margin: 0; padding: 0; }
  body {
    background: radial-gradient(ellipse at top, #1e293b 0%, #0f172a 60%);
    color: var(--ink);
    font-family: "Segoe UI", system-ui, sans-serif;
    min-height: 100vh;
    padding: 20px;
  }
  header {
    display: flex;
    align-items: center;
    justify-content: space-between;
    margin-bottom: 20px;
  }
  header h1 { font-size: 22px; letter-spacing: 0.02em; }
  header h1 span { color: var(--accent); }
  .preset-badge {
    font-size: 12px;
    color: var(--muted);
    background: rgba(30,41,59,0.9);
    border: 1px solid var(--border);
    border-radius: 8px;
    padding: 4px 12px;
    margin-left: 12px;
    vertical-align: middle;
  }
  .status-dot {
    width: 10px; height: 10px;
    border-radius: 50%;
    background: var(--green);
    box-shadow: 0 0 8px var(--green);
    display: inline-block;
    margin-right: 7px;
    transition: background 0.3s, box-shadow 0.3s;
  }
  .status-dot.offline { background: var(--red); box-shadow: 0 0 8px var(--red); }
  .status-dot.done    { background: var(--muted); box-shadow: none; }
  #status-label { font-size: 13px; color: var(--muted); }
  #elapsed {
    font-variant-numeric: tabular-nums;
    font-size: 13px;
    color: var(--muted);
  }

  .kpi-row {
    display: grid;
    grid-template-columns: repeat(5, minmax(0,1fr));
    gap: 12px;
    margin-bottom: 18px;
  }
  .kpi {
    background: rgba(30,41,59,0.8);
    border: 1px solid var(--border);
    border-radius: 14px;
    padding: 14px 16px;
    backdrop-filter: blur(4px);
  }
  .kpi .label { font-size: 11px; text-transform: uppercase; letter-spacing: 0.06em; color: var(--muted); }
  .kpi .value { font-size: 30px; font-weight: 700; margin-top: 6px; font-variant-numeric: tabular-nums; }
  .kpi.accent .value { color: var(--accent); }
  .kpi.green  .value { color: var(--green); }
  .kpi.yellow .value { color: var(--yellow); }
  .kpi.red    .value { color: var(--red); }
  .kpi.purple .value { color: var(--purple); }

  .charts-grid {
    display: grid;
    grid-template-columns: 1fr 1fr;
    grid-template-rows: auto auto;
    gap: 14px;
  }
  .chart-card {
    background: rgba(15,23,42,0.85);
    border: 1px solid var(--border);
    border-radius: 14px;
    padding: 16px;
    backdrop-filter: blur(4px);
  }
  .chart-card.full { grid-column: 1 / -1; }
  .chart-card h3 { font-size: 13px; color: var(--muted); text-transform: uppercase; letter-spacing: 0.05em; margin-bottom: 10px; }
  canvas { width: 100% !important; height: 220px !important; }
  .chart-card.full canvas { height: 200px !important; }

  .progress-wrap { margin-top: 14px; }
  .progress-bar-bg {
    background: var(--border);
    border-radius: 99px;
    height: 6px;
    overflow: hidden;
  }
  .progress-bar-fill {
    height: 100%;
    background: linear-gradient(90deg, var(--accent), var(--purple));
    border-radius: 99px;
    transition: width 0.8s linear;
    width: 0%;
  }
  #progress-label { font-size: 12px; color: var(--muted); margin-top: 5px; }

  .save-row { display: flex; gap: 10px; margin-top: 14px; justify-content: flex-end; }
  .btn {
    background: rgba(30,41,59,0.9);
    border: 1px solid var(--border);
    border-radius: 10px;
    color: var(--ink);
    cursor: pointer;
    font-size: 13px;
    padding: 8px 18px;
    transition: background 0.2s, border-color 0.2s;
  }
  .btn:hover { background: rgba(56,189,248,0.15); border-color: var(--accent); }
  .btn.primary { background: rgba(56,189,248,0.18); border-color: var(--accent); color: var(--accent); font-weight: 600; }
  .btn.primary:hover { background: rgba(56,189,248,0.28); }

  @media (max-width: 860px) {
    .preset-grid { grid-template-columns: 1fr; }
    .target-row { grid-template-columns: 1fr; }
    .kpi-row { grid-template-columns: repeat(2, 1fr); }
    .charts-grid { grid-template-columns: 1fr; }
    .chart-card.full { grid-column: 1; }
  }
</style>
</head>
<body>

<!-- ═══════════════════════════ SELECTOR VIEW ═══════════════════════════ -->
<div id="selector-view">
  <div class="sel-header">
    <h1>Live Traffic <span style="color:var(--accent)">Dashboard</span></h1>
    <p>Choose a stress level, then click <strong>Start Run</strong> to begin the test.</p>
  </div>

  <div class="preset-grid">
    <div class="preset-card low" data-preset="low">
      <div class="preset-icon">🟢</div>
      <div class="preset-name low">Low</div>
      <div class="preset-stats">4 workers<br>60 seconds<br>timeout 5 s</div>
      <div class="preset-desc">Warm-up · sanity check</div>
    </div>
    <div class="preset-card medium" data-preset="medium">
      <div class="preset-icon">🟡</div>
      <div class="preset-name medium">Medium</div>
      <div class="preset-stats">12 workers<br>90 seconds<br>timeout 5 s</div>
      <div class="preset-desc">Realistic production load</div>
    </div>
    <div class="preset-card heavy" data-preset="heavy">
      <div class="preset-icon">🔴</div>
      <div class="preset-name heavy">Heavy</div>
      <div class="preset-stats">24 workers<br>120 seconds<br>timeout 4 s</div>
      <div class="preset-desc">Maximum stress test</div>
    </div>
  </div>

  <div class="target-row">
    <label class="target-field">
      Service
      <select id="service-select"></select>
    </label>
    <label class="target-field">
      Test
      <select id="test-select"></select>
    </label>
  </div>

  <div class="start-row">
    <button id="start-btn" disabled>Start Run →</button>
    <div id="preset-detail">Select a preset above to enable start.</div>
  </div>
</div>

<!-- ═══════════════════════════ DASHBOARD VIEW ══════════════════════════ -->
<div id="dashboard-view" style="display:none">
<header>
  <h1>Live Traffic <span>Dashboard</span><span class="preset-badge" id="preset-badge"></span></h1>
  <div>
    <span class="status-dot" id="dot"></span>
    <span id="status-label">Connecting…</span>
    &nbsp;&nbsp;
    <span id="elapsed">0s / —s</span>
  </div>
</header>

<div class="kpi-row">
  <div class="kpi accent"><div class="label">Total Requests</div><div class="value" id="k-total">0</div></div>
  <div class="kpi green"><div class="label">Success Rate</div><div class="value" id="k-srate">—</div></div>
  <div class="kpi yellow"><div class="label">Current RPS</div><div class="value" id="k-rps">0</div></div>
  <div class="kpi red"><div class="label">P95 Latency</div><div class="value" id="k-p95">—</div></div>
  <div class="kpi purple"><div class="label">Errors</div><div class="value" id="k-err">0</div></div>
</div>

<div class="charts-grid">
  <div class="chart-card full">
    <h3>Requests per Second</h3>
    <canvas id="c-rps"></canvas>
  </div>
  <div class="chart-card">
    <h3>Latency (ms)</h3>
    <canvas id="c-lat"></canvas>
  </div>
  <div class="chart-card">
    <h3>OK vs Errors</h3>
    <canvas id="c-err"></canvas>
  </div>
</div>

<div class="progress-wrap">
  <div class="progress-bar-bg"><div class="progress-bar-fill" id="progress-fill"></div></div>
  <div id="progress-label">Waiting for data…</div>
</div>

<div class="save-row">
  <button class="btn" onclick="saveChartPng('c-rps','rps')">Save RPS chart</button>
  <button class="btn" onclick="saveChartPng('c-lat','latency')">Save Latency chart</button>
  <button class="btn" onclick="saveChartPng('c-err','ok-errors')">Save OK/Err chart</button>
  <button class="btn primary" onclick="saveFullReport()">Save Full Report</button>
</div>
</div><!-- end #dashboard-view -->

<script>
// ── Presets & selector ───────────────────────────────────────────────
const PRESETS = {
  low:    { workers: 4,  duration: 60,  timeout: 5.0 },
  medium: { workers: 12, duration: 90,  timeout: 5.0 },
  heavy:  { workers: 24, duration: 120, timeout: 4.0 },
};

const SERVICE_TESTS = {
  gateway: {
    label: 'API Gateway (8000)',
    tests: [
      {
        id: 'business-search',
        label: 'Business Search',
        url: 'http://localhost:8000/api/businesses?searchQuery=&city=Arizona&minStars=&searchPath=auto',
      },
      {
        id: 'recommendations',
        label: 'Recommendations',
        url: 'http://localhost:8000/api/recommendations?user_id=1',
      },
      {
        id: 'gateway-health',
        label: 'Gateway Health',
        url: 'http://localhost:8000/health',
      },
    ],
  },
  business: {
    label: 'Business Service (8001)',
    tests: [
      { id: 'business-root', label: 'Business Root', url: 'http://localhost:8001/' },
      { id: 'business-health', label: 'Business Health', url: 'http://localhost:8001/health' },
      { id: 'business-list', label: 'Business List', url: 'http://localhost:8001/businesses?city=Arizona&limit=20' },
      { id: 'business-cities', label: 'Business Cities', url: 'http://localhost:8001/businesses/cities' },
      { id: 'business-cache-stats', label: 'Business Cache Stats', url: 'http://localhost:8001/cache/stats' },
    ],
  },
  recommendation: {
    label: 'Recommendation Service (8002)',
    tests: [
      { id: 'recommendation-root', label: 'Recommendation Root', url: 'http://localhost:8002/' },
      { id: 'recommendation-health', label: 'Recommendation Health', url: 'http://localhost:8002/health' },
      { id: 'recommendation-cache-stats', label: 'Recommendation Cache Stats', url: 'http://localhost:8002/cache/stats' },
    ],
  },
  ingestion: {
    label: 'Ingestion Service (8003)',
    tests: [
      { id: 'ingestion-health', label: 'Ingestion Health', url: 'http://localhost:8003/health' },
    ],
  },
};

let selectedPreset = null;
let selectedService = 'gateway';
let selectedTest = null;
let runMeta = {
  service: 'custom-service',
  test: 'custom-test',
  preset: 'custom',
  workers: null,
  duration: null,
  timeout: null,
  url: null,
};

function sanitizeName(value) {
  return String(value || '')
    .toLowerCase()
    .replace(/[^a-z0-9-_. ]+/g, '-')
    .replace(/\\s+/g, ' ')
    .trim();
}

function runLabel(meta) {
  const service = sanitizeName(meta?.service || 'custom-service');
  const test = sanitizeName(meta?.test || 'custom-test');
  const preset = String(meta?.preset || 'custom').toLowerCase();
  const workers = Number(meta?.workers ?? NaN);
  const duration = Number(meta?.duration ?? NaN);
  const timeout = Number(meta?.timeout ?? NaN);

  const safeWorkers = Number.isFinite(workers) ? workers : '?';
  const safeDuration = Number.isFinite(duration) ? duration : '?';
  const safeTimeout = Number.isFinite(timeout) ? timeout : '?';

  return `${service} - ${test} - ${preset} - ${safeWorkers} workers - ${safeDuration} sec - timeout ${safeTimeout}s`;
}

function currentTest() {
  const svc = SERVICE_TESTS[selectedService];
  if (!svc) {
    return null;
  }
  return svc.tests.find(t => t.id === selectedTest) || null;
}

function refreshTestOptions() {
  const testSelect = document.getElementById('test-select');
  const tests = SERVICE_TESTS[selectedService].tests;
  testSelect.innerHTML = '';
  tests.forEach((test) => {
    const opt = document.createElement('option');
    opt.value = test.id;
    opt.textContent = test.label;
    testSelect.appendChild(opt);
  });
  selectedTest = tests.length ? tests[0].id : null;
  testSelect.value = selectedTest || '';
}

function refreshStartUi() {
  const startBtn = document.getElementById('start-btn');
  const detail = document.getElementById('preset-detail');
  const test = currentTest();

  const canStart = Boolean(selectedPreset && selectedService && test);
  startBtn.disabled = !canStart;

  if (!selectedPreset) {
    detail.textContent = 'Select stress preset, service, and test to enable start.';
    return;
  }

  const cfg = PRESETS[selectedPreset];
  const svcLabel = SERVICE_TESTS[selectedService].label;
  detail.textContent =
    `${selectedPreset.toUpperCase()} · ${cfg.workers} workers · ${cfg.duration}s · timeout ${cfg.timeout}s · ${svcLabel} · ${test ? test.label : ''}`;
}

const serviceSelect = document.getElementById('service-select');
Object.entries(SERVICE_TESTS).forEach(([key, svc]) => {
  const opt = document.createElement('option');
  opt.value = key;
  opt.textContent = svc.label;
  serviceSelect.appendChild(opt);
});
serviceSelect.value = selectedService;
refreshTestOptions();
refreshStartUi();

serviceSelect.addEventListener('change', (e) => {
  selectedService = e.target.value;
  refreshTestOptions();
  refreshStartUi();
});

document.getElementById('test-select').addEventListener('change', (e) => {
  selectedTest = e.target.value;
  refreshStartUi();
});

document.querySelectorAll('.preset-card').forEach(card => {
  card.addEventListener('click', () => {
    document.querySelectorAll('.preset-card').forEach(c => c.classList.remove('selected'));
    card.classList.add('selected');
    selectedPreset = card.dataset.preset;
    refreshStartUi();
  });
});

document.getElementById('start-btn').addEventListener('click', async () => {
  if (!selectedPreset || !selectedService || !selectedTest) return;
  const btn = document.getElementById('start-btn');
  btn.disabled = true;
  btn.textContent = 'Starting…';

  const cfg = PRESETS[selectedPreset];
  const svc = SERVICE_TESTS[selectedService];
  const test = currentTest();
  runMeta = {
    service: selectedService,
    test: selectedTest,
    preset: selectedPreset,
    workers: cfg.workers,
    duration: cfg.duration,
    timeout: cfg.timeout,
    url: test ? test.url : null,
  };
  await fetch('/start', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      service: selectedService,
      test: selectedTest,
      url: test ? test.url : null,
      preset: selectedPreset,
      ...cfg,
    }),
  });

  const label = selectedPreset.charAt(0).toUpperCase() + selectedPreset.slice(1);
  document.getElementById('preset-badge').textContent =
    `${svc.label} · ${test ? test.label : ''} · ${label} · ${cfg.workers} workers · ${cfg.duration}s`;

  document.getElementById('selector-view').style.display = 'none';
  document.getElementById('dashboard-view').style.display = '';
  initDashboard();
});

// ── Dashboard (initialised after Start is clicked) ───────────────────
const MAX_POINTS = 120;

const chartDefaults = {
  responsive: true,
  maintainAspectRatio: false,
  animation: { duration: 400 },
  plugins: { legend: { labels: { color: '#94a3b8', boxWidth: 12, font: { size: 11 } } }, tooltip: { mode: 'index', intersect: false } },
  scales: {
    x: { ticks: { color: '#475569', maxTicksLimit: 12, font: { size: 10 } }, grid: { color: '#1e293b' } },
    y: { ticks: { color: '#475569', font: { size: 10 } }, grid: { color: '#1e293b' }, beginAtZero: true },
  },
};

function makeChart(id, datasets) {
  const ctx = document.getElementById(id).getContext('2d');
  return new Chart(ctx, {
    type: 'line',
    data: { labels: [], datasets },
    options: JSON.parse(JSON.stringify(chartDefaults)),
  });
}

let rpsChart, latChart, errChart;

function initDashboard() {
  rpsChart = makeChart('c-rps', [
    { label: 'RPS', data: [], borderColor: '#38bdf8', backgroundColor: 'rgba(56,189,248,0.10)', fill: true, tension: 0.35, pointRadius: 0 },
  ]);
  latChart = makeChart('c-lat', [
    { label: 'Avg ms', data: [], borderColor: '#fbbf24', backgroundColor: 'transparent', tension: 0.35, pointRadius: 0 },
    { label: 'P95 ms', data: [], borderColor: '#ef4444', backgroundColor: 'rgba(239,68,68,0.08)', fill: true, tension: 0.35, pointRadius: 0 },
  ]);
  errChart = makeChart('c-err', [
    { label: 'OK',     data: [], borderColor: '#34d399', backgroundColor: 'rgba(52,211,153,0.12)', fill: true, tension: 0.3, pointRadius: 0 },
    { label: 'Errors', data: [], borderColor: '#f87171', backgroundColor: 'rgba(248,113,113,0.12)', fill: true, tension: 0.3, pointRadius: 0 },
  ]);
  connect();
}

function push(chart, label, ...values) {
  chart.data.labels.push(label);
  values.forEach((v, i) => chart.data.datasets[i].data.push(v));
  if (chart.data.labels.length > MAX_POINTS) {
    chart.data.labels.shift();
    chart.data.datasets.forEach(d => d.data.shift());
  }
  chart.update('active');
}

function fmt(n, decimals = 0) {
  return Number(n).toFixed(decimals);
}

let duration = null;

function connect() {
  const dot        = document.getElementById('dot');
  const statusLbl  = document.getElementById('status-label');
  const elapsedLbl = document.getElementById('elapsed');
  const fill       = document.getElementById('progress-fill');
  const progressLbl = document.getElementById('progress-label');

  const es = new EventSource('/events');

  es.onopen = () => {
    dot.className = 'status-dot';
    statusLbl.textContent = 'Live';
  };

  es.onmessage = (e) => {
    const d = JSON.parse(e.data);

    if (d.type === 'done') {
      if (typeof d.total_requests === 'number') {
        document.getElementById('k-total').textContent = d.total_requests.toLocaleString();
      }
      if (typeof d.success_rate === 'number') {
        document.getElementById('k-srate').textContent = fmt(d.success_rate, 1) + '%';
      }
      if (typeof d.avg_rps === 'number') {
        document.getElementById('k-rps').textContent = fmt(d.avg_rps, 1);
      }
      if (typeof d.p95_latency_ms === 'number') {
        document.getElementById('k-p95').textContent = fmt(d.p95_latency_ms, 0) + ' ms';
      }
      if (typeof d.total_errors === 'number') {
        document.getElementById('k-err').textContent = d.total_errors.toLocaleString();
      }
      if (d.run_service || d.run_test || d.run_preset) {
        runMeta = {
          ...runMeta,
          service: d.run_service || runMeta.service,
          test: d.run_test || runMeta.test,
          preset: d.run_preset || runMeta.preset,
          workers: d.run_workers ?? runMeta.workers,
          duration: d.run_duration_s ?? runMeta.duration,
          timeout: d.run_timeout_s ?? runMeta.timeout,
          url: d.run_url ?? runMeta.url,
        };
      }
      dot.className = 'status-dot done';
      statusLbl.textContent = 'Run complete';
      progressLbl.textContent = 'Run finished — reload page to start a new run.';
      fill.style.width = '100%';
      es.close();
      return;
    }

    duration = d.duration_s;
    const sec = d.second;
    const label = sec + 's';

    document.getElementById('k-total').textContent = d.total_requests.toLocaleString();
    document.getElementById('k-srate').textContent = fmt(d.success_rate, 1) + '%';
    document.getElementById('k-rps').textContent   = fmt(d.rps, 0);
    document.getElementById('k-p95').textContent   = fmt(d.p95_ms, 0) + ' ms';
    document.getElementById('k-err').textContent   = d.total_errors.toLocaleString();

    push(rpsChart, label, d.rps);
    push(latChart, label, d.avg_ms, d.p95_ms);
    push(errChart, label, d.ok, d.errors);

    const pct = duration ? Math.min(100, (sec / duration) * 100) : 0;
    fill.style.width = pct + '%';
    elapsedLbl.textContent = sec + 's / ' + (duration ? duration + 's' : '—s');
    progressLbl.textContent = 'Second ' + sec + ' of ' + (duration || '?') + ' — ' + d.total_requests.toLocaleString() + ' requests sent';
  };

  es.onerror = () => {
    dot.className = 'status-dot offline';
    statusLbl.textContent = 'Reconnecting…';
    es.close();
    setTimeout(connect, 2000);
  };
}

// ── Save helpers ─────────────────────────────────────────────────────
function saveChartPng(canvasId, name) {
  const canvas = document.getElementById(canvasId);
  const a = document.createElement('a');
  a.href = canvas.toDataURL('image/png');
  const ts = new Date().toISOString().slice(0,19).replace(/:/g,'-');
  a.download = runLabel(runMeta) + ' - ' + name + ' - ' + ts + '.png';
  a.click();
}

async function saveFullReport() {
  const ts = new Date().toISOString().slice(0,19).replace(/:/g,'-');
  const rpsImg  = document.getElementById('c-rps').toDataURL('image/png');
  const latImg  = document.getElementById('c-lat').toDataURL('image/png');
  const errImg  = document.getElementById('c-err').toDataURL('image/png');

  let summary = {};
  try {
    const resp = await fetch('/snapshot');
    if (resp.ok) {
      const snap = await resp.json();
      summary = snap.summary || {};
    }
  } catch (_) {
    // Keep UI values as fallback if snapshot endpoint is unavailable.
  }

  const totalRequests = Number(summary.total_requests ?? 0);
  const successRate = Number(summary.success_rate ?? NaN);
  const avgRps = Number(summary.avg_rps ?? NaN);
  const p95Latency = Number(summary.p95_latency_ms ?? NaN);
  const totalErrors = Number(summary.total_errors ?? 0);

  const summaryMeta = {
    service: summary.run_service ?? runMeta.service,
    test: summary.run_test ?? runMeta.test,
    preset: summary.run_preset ?? runMeta.preset,
    workers: summary.run_workers ?? runMeta.workers,
    duration: summary.run_duration_s ?? runMeta.duration,
    timeout: summary.run_timeout_s ?? runMeta.timeout,
    url: summary.run_url ?? runMeta.url,
  };

  const fallbackKpi = {
    total: document.getElementById('k-total').textContent,
    srate: document.getElementById('k-srate').textContent,
    rps: document.getElementById('k-rps').textContent,
    p95: document.getElementById('k-p95').textContent,
    err: document.getElementById('k-err').textContent,
  };

  const kpis = [
    ['Total Requests', Number.isFinite(totalRequests) && totalRequests > 0 ? totalRequests.toLocaleString() : fallbackKpi.total],
    ['Success Rate',   Number.isFinite(successRate) ? fmt(successRate, 1) + '%' : fallbackKpi.srate],
    ['Avg RPS',        Number.isFinite(avgRps) ? fmt(avgRps, 1) : fallbackKpi.rps],
    ['P95 Latency',    Number.isFinite(p95Latency) ? fmt(p95Latency, 0) + ' ms' : fallbackKpi.p95],
    ['Errors',         Number.isFinite(totalErrors) ? totalErrors.toLocaleString() : fallbackKpi.err],
  ];
  const kpiHtml = kpis.map(([k,v]) =>
    `<div style="background:#1e293b;border-radius:10px;padding:12px 18px;min-width:120px">
       <div style="font-size:11px;color:#64748b;text-transform:uppercase">${k}</div>
       <div style="font-size:26px;font-weight:700;margin-top:4px">${v}</div>
     </div>`
  ).join('');
  const html = `<!doctype html><html><head><meta charset="utf-8"><title>Traffic Report ${ts}</title>
<style>body{margin:0;background:#0f172a;color:#e2e8f0;font-family:Segoe UI,sans-serif;padding:24px}
h1{font-size:22px;margin-bottom:18px}h2{font-size:13px;color:#64748b;text-transform:uppercase;letter-spacing:.06em;margin:18px 0 8px}
.krow{display:flex;gap:10px;flex-wrap:wrap;margin-bottom:16px}
img{width:100%;border-radius:12px;border:1px solid #1e293b;margin-bottom:12px}</style>
</head><body>
<h1>Traffic Report <span style="color:#38bdf8">${ts}</span></h1>
<div style="margin-bottom:14px;color:#94a3b8;font-size:13px">${runLabel(summaryMeta)}</div>
<div class="krow">${kpiHtml}</div>
<h2>Requests per Second</h2><img src="${rpsImg}">
<h2>Latency (ms)</h2><img src="${latImg}">
<h2>OK vs Errors</h2><img src="${errImg}">
</body></html>`;
  const a = document.createElement('a');
  a.href = 'data:text/html;charset=utf-8,' + encodeURIComponent(html);
  a.download = runLabel(summaryMeta) + '.html';
  a.click();
}
</script>
</body>
</html>
"""

# ---------------------------------------------------------------------------
# HTTP handler
# ---------------------------------------------------------------------------
class _Handler(BaseHTTPRequestHandler):
    def log_message(self, format: str, *args: object) -> None:  # noqa: A002
        pass  # silence server log noise

    def do_GET(self):
        if self.path == "/":
            body = _HTML.encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        elif self.path == "/snapshot":
            with _snapshot_lock:
                data = {"timeline": _timeline_snapshot, "summary": _last_summary}
                body = json.dumps(data).encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        elif self.path == "/events":
            self.send_response(200)
            self.send_header("Content-Type", "text/event-stream")
            self.send_header("Cache-Control", "no-cache")
            self.send_header("Access-Control-Allow-Origin", "*")
            self.end_headers()
            q = _subscribe()
            try:
                while True:
                    try:
                        msg = q.get(timeout=20)
                        self.wfile.write(msg.encode("utf-8"))
                        self.wfile.flush()
                    except queue.Empty:
                        self.wfile.write(b": heartbeat\n\n")
                        self.wfile.flush()
            except (BrokenPipeError, ConnectionResetError, OSError):
                pass
            finally:
                _unsubscribe(q)

        else:
            self.send_response(404)
            self.end_headers()

    def do_POST(self):
        if self.path == "/start":
            length = int(self.headers.get("Content-Length", 0))
            body = self.rfile.read(length)
            try:
                data = json.loads(body)
            except (json.JSONDecodeError, ValueError):
                data = {}
            _run_config.update(data)
            _run_event.set()
            resp = b'{"ok":true}'
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(resp)))
            self.end_headers()
            self.wfile.write(resp)
        else:
            self.send_response(404)
            self.end_headers()


# ---------------------------------------------------------------------------
# Worker
# ---------------------------------------------------------------------------
def _worker(url: str, timeout: float, stop: threading.Event, state: SharedState, token: str | None = None):
    headers = {}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    while not stop.is_set():
        start = time.perf_counter()
        ok = False
        try:
            req = urllib.request.Request(url, method="GET", headers=headers)
            with urllib.request.urlopen(req, timeout=timeout) as res:
                ok = 200 <= res.status < 400
        except urllib.error.HTTPError as e:
            ok = e.code < 500
        except Exception:
            ok = False
        latency_ms = (time.perf_counter() - start) * 1000
        state.record(ok=ok, latency_ms=latency_ms)


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------
def main():
    parser = argparse.ArgumentParser(
        description="Real-time traffic dashboard with live charts in browser",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python scripts/traffic_dashboard.py
  python scripts/traffic_dashboard.py --url http://localhost:8000/health --workers 8 --duration 60
  python scripts/traffic_dashboard.py --url http://localhost:8000/api/businesses?searchQuery=&city=Arizona --workers 24 --duration 180
""",
    )
    parser.add_argument("--url", default=DEFAULT_TARGET, help="Target URL to hammer")
    parser.add_argument("--workers", type=int, default=16, help="Concurrent workers (default 16)")
    parser.add_argument("--duration", type=int, default=90, help="Duration in seconds (default 90)")
    parser.add_argument("--timeout", type=float, default=5.0, help="Per-request timeout seconds")
    parser.add_argument("--port", type=int, default=DEFAULT_PORT, help="Dashboard port (default 9999)")
    parser.add_argument("--token", default=None, help="Bearer token to include in every request")
    parser.add_argument("--gen-token", action="store_true", help="Auto-generate a dev JWT (uses dev-secret-change-me)")
    parser.add_argument("--jwt-secret", default="dev-secret-change-me", help="JWT secret for --gen-token")
    args = parser.parse_args()

    token: str | None = args.token
    if args.gen_token and not token:
        token = generate_dev_token(secret=args.jwt_secret)
        print(f"Generated dev JWT (valid 2h): {token[:40]}…")

    state = SharedState()
    stop = threading.Event()

    # Start HTTP server in background
    server = ThreadingHTTPServer(("0.0.0.0", args.port), _Handler)
    server_thread = threading.Thread(target=server.serve_forever, daemon=True)
    server_thread.start()

    dashboard_url = f"http://localhost:{args.port}"
    print(f"Dashboard: {dashboard_url}")
    print(f"Target:    {args.url}")
    print(f"Auth:      {'Bearer token set' if token else 'none (no --gen-token)'}")
    print(f"Opening browser — select a preset and click Start Run.")
    webbrowser.open(dashboard_url)

    # ── Wait for user to select a preset and click Start in the browser ──
    _run_event.wait()

    run_workers  = _run_config.get("workers",  args.workers)
    run_duration = _run_config.get("duration", args.duration)
    run_timeout  = _run_config.get("timeout",  args.timeout)
    run_url      = _run_config.get("url",      args.url)
    run_service  = _run_config.get("service",  "custom-service")
    run_test     = _run_config.get("test",     "custom-test")
    run_preset   = _run_config.get("preset",   "custom")

    print(
      f"\nService '{run_service}' · Test '{run_test}' · Preset '{run_preset}' "
      f"→ {run_workers} workers · {run_duration}s · {run_url}"
    )

    # Start workers
    workers = [
        threading.Thread(target=_worker, args=(run_url, run_timeout, stop, state, token), daemon=True)
        for _ in range(run_workers)
    ]
    for w in workers:
        w.start()

    print(f"Traffic started. Dashboard live at {dashboard_url}")
    print(f"Press Ctrl+C to stop early.\n")

    t_start = time.time()
    for second in range(1, run_duration + 1):
        time.sleep(1)
        ok, errors, lats = state.flush_second()
        reqs = ok + errors
        avg_ms = sum(lats) / len(lats) if lats else 0.0
        p95_ms = _percentile(lats, 0.95) if lats else 0.0

        total_req, total_ok, total_errors, all_lats = state.snapshot()
        success_rate = (100.0 * total_ok / total_req) if total_req else 0.0

        payload = {
            "second": second,
            "rps": reqs,
            "ok": ok,
            "errors": errors,
            "avg_ms": round(avg_ms, 2),
            "p95_ms": round(p95_ms, 2),
            "total_requests": total_req,
            "total_ok": total_ok,
            "total_errors": total_errors,
            "success_rate": round(success_rate, 2),
            "duration_s": run_duration,
        }
        _broadcast(payload)

        print(
            f"[{second:>3}/{run_duration}] "
            f"rps={reqs:>4}  ok={ok:>4}  err={errors:>3}  "
            f"avg={avg_ms:>6.0f}ms  p95={p95_ms:>6.0f}ms  "
            f"total={total_req}"
        )

    stop.set()

    total_req, total_ok, total_errors, all_lats = state.snapshot()
    elapsed = max(0.001, time.time() - t_start)
    success_rate_total = (100.0 * total_ok / total_req) if total_req else 0.0
    avg_rps_total = total_req / elapsed
    p95_total = _percentile(all_lats, 0.95)
    p99_total = _percentile(all_lats, 0.99)

    _broadcast({
      "type": "done",
      "total_requests": total_req,
      "total_ok": total_ok,
      "total_errors": total_errors,
      "success_rate": round(success_rate_total, 2),
      "avg_rps": round(avg_rps_total, 2),
      "p95_latency_ms": round(p95_total, 2),
      "p99_latency_ms": round(p99_total, 2),
      "elapsed_s": round(elapsed, 3),
      "run_service": run_service,
      "run_test": run_test,
      "run_preset": run_preset,
      "run_workers": run_workers,
      "run_duration_s": run_duration,
      "run_timeout_s": run_timeout,
      "run_url": run_url,
    })

    print(f"\n{'='*60}")
    print(f"  Run complete")
    print(f"  Total requests : {total_req}  ok={total_ok}  err={total_errors}")
    print(f"  Success rate   : {100.0*total_ok/total_req:.1f}%" if total_req else "  No requests completed")
    print(f"  Avg RPS        : {avg_rps_total:.1f}")
    print(f"  P95 latency    : {p95_total:.0f}ms")
    print(f"  P99 latency    : {p99_total:.0f}ms")
    print(f"\nDashboard stays open at {dashboard_url} — press Ctrl+C to exit.")
    print(f"{'='*60}")

    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        pass
    finally:
        server.shutdown()


if __name__ == "__main__":
    main()
