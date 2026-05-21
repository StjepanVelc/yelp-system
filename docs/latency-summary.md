# Latency Summary

## Technical summary

We traced the high local API latency to Windows `localhost` name resolution on the development machine. Requests to `localhost` were taking roughly 2 seconds before reaching the app, while the same endpoints on `127.0.0.1` responded in about 10-20 ms.

This affected both direct service calls and Gateway-proxied requests, which made the whole stack look slow and initially suggested auth, cache, DB, or proxy overhead. After confirming the behavior with side-by-side measurements, the local development script was switched to loopback addresses.

## What was actually wrong

- `localhost` triggered an IPv6/IPv4 fallback delay on Windows.
- The delay applied to direct service requests and Gateway requests alike.
- The symptom masked the real cause and made the performance baseline misleading.
- The fix was to use `127.0.0.1` for local development URLs.

## Result

- Gateway endpoints dropped from about 3.2-3.5s to around 10-15 ms in local tests.
- Direct service endpoints dropped from about 2.0s to around 15-20 ms.
- The remaining architecture items in the plan are still valid, but the artificial hostname delay is resolved.

## LinkedIn-ready version

We found a very specific local performance bug in our API stack: on Windows, `localhost` was adding an unexpected 2-second delay before requests even reached the application. That made direct services and Gateway requests look slow, and it initially pointed us in the wrong direction toward auth, cache, DB, and proxy layers.

After comparing `localhost` with `127.0.0.1`, we confirmed the issue was hostname resolution/fallback behavior, not the application logic itself. Switching local development URLs to `127.0.0.1` brought request times down from seconds to milliseconds.

It was a good reminder that before optimizing the app, you should always verify the network path and the test setup itself.
