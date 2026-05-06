# Live Traffic Testing

This page explains both traffic tools used in this repo:

- `scripts/traffic_dashboard.py` (interactive browser dashboard, manual start)
- `scripts/traffic_live_monitor.py` (terminal-first monitor with static report)

## 1) Interactive Browser Dashboard

Use this when you want live charts and manual control before traffic starts.

### Start

```powershell
python scripts/traffic_dashboard.py --gen-token
```

### Flow

1. Open `http://localhost:9999`.
2. Choose stress preset: `Low`, `Medium`, or `Heavy`.
3. Choose `Service` and `Test` endpoint.
4. Click `Start Run` (traffic does not auto-start).

### What It Shows

- Live KPI cards: total requests, success rate, current RPS, p95, errors
- Live charts: RPS, latency (avg/p95), OK vs errors
- Final run summary via SSE `/events` + `/snapshot`

### Export Files

- Per-chart PNG export
- Full HTML report export
- Filenames include selected service/test/preset and run parameters
  - example: `business - business-health - medium - 12 workers - 90 sec - timeout 5s.html`

### HTTP Status Mode

- Default is strict success classification:
  - success: `2xx` and `3xx`
  - error: `4xx` and `5xx`
- Old behavior is still available:

```powershell
python scripts/traffic_dashboard.py --gen-token --loose-status
```

`--loose-status` treats `4xx` as non-error and only `5xx` as errors.

### JWT Notes

- `--gen-token` creates a dev token for protected routes.
- Gateway bypass requires all conditions:
  - `APP_ENV=development`
  - `ENABLE_DEV_LOAD_TEST_BYPASS=true`
  - token claim `dev_load_test=true`

## 2) Terminal Live Monitor

Use this when you want a simple terminal stream plus generated artifacts.

### Start

```powershell
python scripts/traffic_live_monitor.py --open-report
```

### Useful Variants

Health endpoint quick check:

```powershell
python scripts/traffic_live_monitor.py --url http://localhost:8000/health --duration 30 --workers 8 --open-report
```

Heavier run:

```powershell
python scripts/traffic_live_monitor.py --duration 90 --workers 24 --timeout 5 --open-report
```

### Artifacts

Each run creates:

- `test-results/traffic-monitor-YYYYMMDD-HHMMSS/summary.json`
- `test-results/traffic-monitor-YYYYMMDD-HHMMSS/timeline.csv`
- `test-results/traffic-monitor-YYYYMMDD-HHMMSS/events.log`
- `test-results/traffic-monitor-YYYYMMDD-HHMMSS/report.html`

## Notes

- Both scripts generate traffic and measure the same run they produce.
- For broader end-to-end/regression checks, use `scripts/test-all.ps1`.
