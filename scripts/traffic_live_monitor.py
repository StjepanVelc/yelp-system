"""
Live traffic monitor for test runs.

What it does:
- Generates concurrent HTTP traffic to a target URL.
- Prints live phase/status lines in the terminal.
- Writes timeline metrics and summary artifacts.
- Generates a static HTML report with charts.

Usage examples:
  python scripts/traffic_live_monitor.py
  python scripts/traffic_live_monitor.py --url http://localhost:8000/health --duration 45 --workers 10
  python scripts/traffic_live_monitor.py --open-report
"""

from __future__ import annotations

import argparse
import csv
import json
import math
import random
import statistics
import threading
import time
import urllib.error
import urllib.request
import webbrowser
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import List


DEFAULT_URL = "http://localhost:8000/api/businesses?searchQuery=&city=Arizona&minStars=&searchPath=auto"


@dataclass
class Event:
    ts: float
    phase: str
    message: str


@dataclass
class TimelinePoint:
    second: int
    rps: float
    ok: int
    errors: int
    avg_ms: float
    p95_ms: float


@dataclass
class SharedState:
    lock: threading.Lock = field(default_factory=threading.Lock)
    total_requests: int = 0
    total_ok: int = 0
    total_errors: int = 0
    total_latency_ms: float = 0.0
    latencies_ms: List[float] = field(default_factory=list)
    second_ok: int = 0
    second_errors: int = 0
    second_latencies_ms: List[float] = field(default_factory=list)

    def record(self, ok: bool, latency_ms: float) -> None:
        with self.lock:
            self.total_requests += 1
            self.total_latency_ms += latency_ms
            self.latencies_ms.append(latency_ms)

            if ok:
                self.total_ok += 1
                self.second_ok += 1
            else:
                self.total_errors += 1
                self.second_errors += 1

            self.second_latencies_ms.append(latency_ms)

    def flush_second(self) -> tuple[int, int, List[float]]:
        with self.lock:
            ok = self.second_ok
            errors = self.second_errors
            lats = self.second_latencies_ms[:]
            self.second_ok = 0
            self.second_errors = 0
            self.second_latencies_ms.clear()
            return ok, errors, lats


def percentile(values: List[float], p: float) -> float:
    if not values:
        return 0.0
    if len(values) == 1:
        return values[0]

    ordered = sorted(values)
    pos = (len(ordered) - 1) * p
    lo = math.floor(pos)
    hi = math.ceil(pos)
    if lo == hi:
        return ordered[int(pos)]

    return ordered[lo] + (ordered[hi] - ordered[lo]) * (pos - lo)


def make_request(url: str, timeout: float) -> tuple[bool, float, int]:
    start = time.perf_counter()
    status = 0
    ok = False

    try:
        req = urllib.request.Request(url, method="GET")
        with urllib.request.urlopen(req, timeout=timeout) as res:
            status = getattr(res, "status", 0) or 0
            ok = 200 <= status < 400
    except urllib.error.HTTPError as err:
        status = err.code
        ok = False
    except Exception:
        ok = False

    latency_ms = (time.perf_counter() - start) * 1000
    return ok, latency_ms, status


def worker_loop(
    worker_id: int,
    url: str,
    timeout: float,
    think_ms: int,
    stop_event: threading.Event,
    state: SharedState,
    events: List[Event],
) -> None:
    random.seed(worker_id + int(time.time()))

    while not stop_event.is_set():
        ok, latency_ms, status = make_request(url=url, timeout=timeout)
        state.record(ok=ok, latency_ms=latency_ms)

        if not ok and status >= 500:
            events.append(Event(ts=time.time(), phase="RUN", message=f"Worker {worker_id}: upstream {status}"))

        if think_ms > 0:
            jitter = random.randint(0, max(1, think_ms // 3))
            time.sleep((think_ms + jitter) / 1000.0)


def log_event(events: List[Event], phase: str, message: str) -> None:
    ts = time.time()
    events.append(Event(ts=ts, phase=phase, message=message))
    stamp = datetime.fromtimestamp(ts).strftime("%H:%M:%S")
    print(f"[{stamp}] [{phase}] {message}")


def points_to_polyline(values: List[float], width: int = 900, height: int = 280, pad: int = 28) -> str:
    if not values:
        return ""

    vmin = min(values)
    vmax = max(values)
    if abs(vmax - vmin) < 1e-9:
        vmax = vmin + 1.0

    count = len(values)
    coords = []
    for idx, val in enumerate(values):
        x = pad + ((width - 2 * pad) * idx / max(1, count - 1))
        y = height - pad - ((height - 2 * pad) * ((val - vmin) / (vmax - vmin)))
        coords.append(f"{x:.2f},{y:.2f}")

    return " ".join(coords)


def build_report_html(summary: dict, timeline: List[TimelinePoint], events: List[Event]) -> str:
    rps_values = [p.rps for p in timeline]
    avg_values = [p.avg_ms for p in timeline]
    p95_values = [p.p95_ms for p in timeline]

    rps_poly = points_to_polyline(rps_values)
    avg_poly = points_to_polyline(avg_values)
    p95_poly = points_to_polyline(p95_values)

    rows = "\n".join(
        f"<tr><td>{p.second}</td><td>{p.rps:.1f}</td><td>{p.ok}</td><td>{p.errors}</td><td>{p.avg_ms:.1f}</td><td>{p.p95_ms:.1f}</td></tr>"
        for p in timeline
    )

    event_rows = "\n".join(
        f"<tr><td>{datetime.fromtimestamp(e.ts).strftime('%H:%M:%S')}</td><td>{e.phase}</td><td>{e.message}</td></tr>"
        for e in events
    )

    return f"""<!doctype html>
<html>
<head>
  <meta charset=\"utf-8\" />
  <meta name=\"viewport\" content=\"width=device-width, initial-scale=1\" />
  <title>Traffic Monitor Report</title>
  <style>
    :root {{
      --bg: #0f172a;
      --panel: #111827;
      --ink: #e5e7eb;
      --muted: #9ca3af;
      --line1: #22d3ee;
      --line2: #f59e0b;
      --line3: #ef4444;
      --ok: #10b981;
      --err: #ef4444;
      --grid: #243244;
    }}
    body {{
      margin: 0;
      font-family: Segoe UI, Tahoma, sans-serif;
      background: radial-gradient(circle at top, #1e293b 0%, #0f172a 55%);
      color: var(--ink);
    }}
    .wrap {{ max-width: 1160px; margin: 24px auto; padding: 0 16px 40px; }}
    .title {{ font-size: 28px; margin: 4px 0 16px; }}
    .meta {{ color: var(--muted); margin-bottom: 20px; }}
    .grid {{ display: grid; grid-template-columns: repeat(4, minmax(0, 1fr)); gap: 12px; }}
    .card {{ background: rgba(17,24,39,.85); border: 1px solid #1f2937; border-radius: 12px; padding: 14px; }}
    .k {{ color: var(--muted); font-size: 12px; text-transform: uppercase; letter-spacing: .06em; }}
    .v {{ font-size: 28px; margin-top: 8px; }}
    .panel {{ background: rgba(17,24,39,.85); border: 1px solid #1f2937; border-radius: 12px; padding: 14px; margin-top: 14px; }}
    h3 {{ margin: 0 0 8px; }}
    svg {{ width: 100%; height: auto; background: #0b1220; border-radius: 10px; border: 1px solid #1f2937; }}
    .legend {{ color: var(--muted); font-size: 13px; margin: 8px 0 0; }}
    table {{ width: 100%; border-collapse: collapse; font-size: 13px; }}
    th, td {{ padding: 8px; border-bottom: 1px solid #1f2937; text-align: left; }}
    th {{ color: var(--muted); font-weight: 600; }}
    .ok {{ color: var(--ok); }}
    .err {{ color: var(--err); }}
    @media (max-width: 900px) {{ .grid {{ grid-template-columns: repeat(2, minmax(0, 1fr)); }} }}
  </style>
</head>
<body>
  <div class=\"wrap\">
    <div class=\"title\">Traffic Monitor Report</div>
    <div class=\"meta\">Generated: {summary['generated_at']} | Target: {summary['target_url']}</div>

    <div class=\"grid\">
      <div class=\"card\"><div class=\"k\">Total Requests</div><div class=\"v\">{summary['total_requests']}</div></div>
      <div class=\"card\"><div class=\"k\">Success Rate</div><div class=\"v\">{summary['success_rate']:.1f}%</div></div>
      <div class=\"card\"><div class=\"k\">Average RPS</div><div class=\"v\">{summary['avg_rps']:.1f}</div></div>
      <div class=\"card\"><div class=\"k\">P95 Latency</div><div class=\"v\">{summary['p95_ms']:.1f} ms</div></div>
    </div>

    <div class=\"panel\">
      <h3>RPS Over Time</h3>
      <svg viewBox=\"0 0 900 280\" preserveAspectRatio=\"none\">
        <polyline fill=\"none\" stroke=\"var(--line1)\" stroke-width=\"3\" points=\"{rps_poly}\"></polyline>
      </svg>
      <div class=\"legend\">Line: requests per second</div>
    </div>

    <div class=\"panel\">
      <h3>Latency Over Time</h3>
      <svg viewBox=\"0 0 900 280\" preserveAspectRatio=\"none\">
        <polyline fill=\"none\" stroke=\"var(--line2)\" stroke-width=\"3\" points=\"{avg_poly}\"></polyline>
        <polyline fill=\"none\" stroke=\"var(--line3)\" stroke-width=\"2\" points=\"{p95_poly}\"></polyline>
      </svg>
      <div class=\"legend\">Orange: avg latency, Red: p95 latency (ms)</div>
    </div>

    <div class=\"panel\">
      <h3>Second-by-Second Timeline</h3>
      <table>
        <thead><tr><th>Second</th><th>RPS</th><th>OK</th><th>Errors</th><th>Avg ms</th><th>P95 ms</th></tr></thead>
        <tbody>{rows}</tbody>
      </table>
    </div>

    <div class=\"panel\">
      <h3>Run Dialogue / Phases</h3>
      <table>
        <thead><tr><th>Time</th><th>Phase</th><th>Message</th></tr></thead>
        <tbody>{event_rows}</tbody>
      </table>
    </div>
  </div>
</body>
</html>
"""


def run_monitor(url: str, duration: int, workers: int, timeout: float, think_ms: int, output_base: Path, open_report: bool) -> Path:
    state = SharedState()
    stop_event = threading.Event()
    events: List[Event] = []
    timeline: List[TimelinePoint] = []

    run_id = datetime.now().strftime("traffic-monitor-%Y%m%d-%H%M%S")
    out_dir = output_base / run_id
    out_dir.mkdir(parents=True, exist_ok=True)

    log_event(events, "PREPARE", "Creating worker pool and output folders")
    log_event(events, "PREPARE", f"Target URL: {url}")
    log_event(events, "PREPARE", f"Workers={workers}, Duration={duration}s, Timeout={timeout:.1f}s")

    threads = [
        threading.Thread(
            target=worker_loop,
            kwargs={
                "worker_id": i + 1,
                "url": url,
                "timeout": timeout,
                "think_ms": think_ms,
                "stop_event": stop_event,
                "state": state,
                "events": events,
            },
            daemon=True,
        )
        for i in range(workers)
    ]

    log_event(events, "RUN", "Starting traffic generation")
    for thread in threads:
        thread.start()

    start = time.time()
    for second in range(1, duration + 1):
        time.sleep(1)
        ok, errors, lats = state.flush_second()
        reqs = ok + errors
        avg_ms = statistics.fmean(lats) if lats else 0.0
        p95_ms = percentile(lats, 0.95) if lats else 0.0

        timeline.append(
            TimelinePoint(
                second=second,
                rps=float(reqs),
                ok=ok,
                errors=errors,
                avg_ms=avg_ms,
                p95_ms=p95_ms,
            )
        )

        print(
            f"[LIVE] sec={second:>3}/{duration} | rps={reqs:>4} | ok={ok:>4} | err={errors:>3} | avg={avg_ms:>7.1f}ms | p95={p95_ms:>7.1f}ms"
        )

        if second == 1:
            log_event(events, "RUN", "Warm phase complete, full measurement active")
        elif second == duration // 2:
            log_event(events, "RUN", "Halfway point reached, continuing collection")

    stop_event.set()
    for thread in threads:
        thread.join(timeout=2)

    elapsed = max(0.001, time.time() - start)
    total_requests = state.total_requests
    total_ok = state.total_ok
    total_errors = state.total_errors
    success_rate = (100.0 * total_ok / total_requests) if total_requests else 0.0
    avg_rps = total_requests / elapsed
    avg_ms_total = (state.total_latency_ms / total_requests) if total_requests else 0.0
    p95_total = percentile(state.latencies_ms, 0.95) if state.latencies_ms else 0.0
    p99_total = percentile(state.latencies_ms, 0.99) if state.latencies_ms else 0.0

    summary = {
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "target_url": url,
        "duration_s": duration,
        "workers": workers,
        "timeout_s": timeout,
        "think_ms": think_ms,
        "total_requests": total_requests,
        "total_ok": total_ok,
        "total_errors": total_errors,
        "success_rate": success_rate,
        "avg_rps": avg_rps,
        "avg_ms": avg_ms_total,
        "p95_ms": p95_total,
        "p99_ms": p99_total,
    }

    log_event(events, "FINALIZE", "Writing summary.json, timeline.csv, events.log and report.html")

    (out_dir / "summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")

    with (out_dir / "timeline.csv").open("w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["second", "rps", "ok", "errors", "avg_ms", "p95_ms"])
        for p in timeline:
            writer.writerow([p.second, f"{p.rps:.2f}", p.ok, p.errors, f"{p.avg_ms:.3f}", f"{p.p95_ms:.3f}"])

    with (out_dir / "events.log").open("w", encoding="utf-8") as f:
        for e in events:
            stamp = datetime.fromtimestamp(e.ts).isoformat(timespec="seconds")
            f.write(f"{stamp} [{e.phase}] {e.message}\n")

    report_html = build_report_html(summary=summary, timeline=timeline, events=events)
    report_path = out_dir / "report.html"
    report_path.write_text(report_html, encoding="utf-8")

    log_event(events, "DONE", f"Report generated: {report_path}")

    if open_report:
        try:
            webbrowser.open(report_path.resolve().as_uri())
            log_event(events, "DONE", "Opened report in default browser")
        except Exception:
            log_event(events, "DONE", "Could not open browser automatically")

    return out_dir


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Live traffic monitor with timeline report")
    parser.add_argument("--url", default=DEFAULT_URL, help="Target URL to hit")
    parser.add_argument("--duration", type=int, default=60, help="Duration in seconds")
    parser.add_argument("--workers", type=int, default=16, help="Concurrent workers")
    parser.add_argument("--timeout", type=float, default=4.0, help="Per-request timeout (seconds)")
    parser.add_argument("--think-ms", type=int, default=0, help="Sleep between requests per worker (ms)")
    parser.add_argument("--output-dir", default="test-results", help="Output root directory")
    parser.add_argument("--open-report", action="store_true", help="Open HTML report after run")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    if args.duration < 1:
        raise SystemExit("--duration must be >= 1")
    if args.workers < 1:
        raise SystemExit("--workers must be >= 1")

    output_root = Path(args.output_dir)
    out_dir = run_monitor(
        url=args.url,
        duration=args.duration,
        workers=args.workers,
        timeout=args.timeout,
        think_ms=args.think_ms,
        output_base=output_root,
        open_report=args.open_report,
    )

    print("\n[SUMMARY]")
    print(f"Artifacts: {out_dir}")
    print(f"- {(out_dir / 'summary.json')} ")
    print(f"- {(out_dir / 'timeline.csv')} ")
    print(f"- {(out_dir / 'events.log')} ")
    print(f"- {(out_dir / 'report.html')} ")


if __name__ == "__main__":
    main()
