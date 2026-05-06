# LAN Testing Guide (2 Laptops)

This guide verifies that the app works when the backend/frontend run on one laptop and are opened from another laptop on the same network.

## Goal

- Host laptop runs the stack.
- Client laptop opens the app over LAN.
- Pages, API calls, and Business map render correctly.

## Prerequisites

- Both laptops are on the same LAN (Wi-Fi or cable).
- Host laptop has project dependencies installed.
- Windows firewall allows inbound TCP on needed ports.

## Host Setup

1. Start services on host:

```powershell
powershell -ExecutionPolicy Bypass -File local-dev.ps1 -Action start
```

2. Find host IPv4:

```powershell
ipconfig
```

3. Optional: allow extra origins for Next dev (if needed):

```powershell
$env:NEXT_ALLOWED_DEV_ORIGINS = "192.168.2.50,192.168.2.60"
```

Notes:
- Frontend auto-allows `localhost`, `127.0.0.1`, and all host LAN IPv4 addresses.
- `NEXT_ALLOWED_DEV_ORIGINS` is only for additional explicit hosts.

## Client Validation

Open from client laptop:

- Frontend: `http://<HOST_IP>:3000`
- API health: `http://<HOST_IP>:8000/health`
- Business API sample: `http://<HOST_IP>:8000/api/businesses?searchQuery=&city=Arizona&minStars=&searchPath=auto`

## Map-Specific Check

1. Open any business details page from client laptop.
2. Confirm map tiles load and marker is visible.
3. Hard refresh (`Ctrl+F5`) if tiles look partial after first load.

## Firewall Command (Host)

Run as Administrator on host:

```powershell
New-NetFirewallRule -DisplayName "Yelp LAN Dev" -Direction Inbound -Protocol TCP -LocalPort 3000,8000,50051,50052,5432,6379 -Action Allow
```

## Troubleshooting

- Symptom: "Blocked cross-origin request to Next.js dev resource"
  - Fix: restart frontend after ensuring host IP is detected.
  - Add client/host values to `NEXT_ALLOWED_DEV_ORIGINS` and restart.

- Symptom: Frontend works, API fails
  - Check gateway service status and host firewall.

- Symptom: Map container visible but tiles broken
  - Hard refresh on client (`Ctrl+F5`).
  - Verify Leaflet CSS is loaded in root layout.

## Optional Regression Script

To run local automated checks on host:

```powershell
powershell -ExecutionPolicy Bypass -File scripts/test-all.ps1 -Profile quick -SkipCacheLoad
```

Results are written under `test-results/<run-id>/`.
