# Live Traffic Testing with Graphs

This page explains how to run a live traffic test and get instant terminal status plus HTML charts.

## What You Get

- Live console output every second:
  - current RPS
  - OK vs error counts
  - avg and p95 latency
- Phase dialogue during run:
  - PREPARE
  - RUN
  - FINALIZE
  - DONE
- Artifacts after run:
  - summary.json
  - timeline.csv
  - events.log
  - report.html with charts

## Command

Run from project root:

```powershell
python scripts/traffic_live_monitor.py --open-report
```

## Useful Variants

Hit health endpoint for quick check:

```powershell
python scripts/traffic_live_monitor.py --url http://localhost:8000/health --duration 30 --workers 8 --open-report
```

Heavier run:

```powershell
python scripts/traffic_live_monitor.py --duration 90 --workers 24 --timeout 5 --open-report
```

## Output Location

Each run creates:

- test-results/traffic-monitor-YYYYMMDD-HHMMSS/summary.json
- test-results/traffic-monitor-YYYYMMDD-HHMMSS/timeline.csv
- test-results/traffic-monitor-YYYYMMDD-HHMMSS/events.log
- test-results/traffic-monitor-YYYYMMDD-HHMMSS/report.html

## Notes

- This script measures traffic it generates itself.
- It is a fast test dashboard for local and LAN testing workflows.
- For broader suite checks, keep using scripts/test-all.ps1.
