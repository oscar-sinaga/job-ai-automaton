# apps/mobile — Mobile Share Capture

Per ADR-019/020 ([../../docs/17_DECISION_LOG.md](../../docs/17_DECISION_LOG.md)), Milestone 1 mobile capture has two parts. Neither lives in this directory as code:

## 1. PWA Web Share Target (the real V1 client)

Implemented in `apps/web`, not here:
- `apps/web/static/manifest.webmanifest` — declares `share_target` (GET, `title`/`text`/`url` params)
- `apps/web/static/sw.js` — minimal service worker (installability only, no offline caching)
- `apps/web/src/routes/share-target/` — receives the share, calls `POST /jobs/capture` with `capture_method: "mobile_share"`, shows the result

**To install on a phone:** open the web app's URL in Chrome (Android) or Safari (iOS), then "Add to Home Screen" / the browser's install prompt. Once installed, "OSCAR Job Copilot" appears as a share target from any app's share sheet.

**Known limitation (Safari/iOS):** Web Share Target support is inconsistent — validate on your actual device per the M1 spike below before relying on it.

## 2. OS share shortcut (zero-build bridge, works everywhere)

No code — a share-sheet shortcut that POSTs directly to `/jobs/capture`. Useful immediately, and as the iOS fallback if the PWA share target proves unreliable there.

**Android (Tasker / HTTP Shortcuts app):**
1. Install an app like *HTTP Shortcuts* (or Tasker) that can register itself as a share target.
2. Create a shortcut: method `POST`, URL `http://<tailnet-hostname>:8000/api/v1/jobs/capture`, header `X-API-Key: <your key>`, body (JSON, using the app's share-intent variables for the shared URL/text):
   ```json
   { "url": "{{share_text}}", "capture_method": "mobile_share",
     "captured_at": "{{iso_timestamp}}" }
   ```
3. Enable "share into this shortcut" so it appears in the OS share sheet.

**iOS (Shortcuts app):**
1. Shortcuts app → new Shortcut → add action "Get Contents of URL".
2. Method `POST`, URL `http://<tailnet-hostname>:8000/api/v1/jobs/capture`, Headers: `X-API-Key: <your key>`, `Content-Type: application/json`.
3. Request body (JSON): `url` = Shortcut Input (the shared URL), `capture_method` = `"mobile_share"`, `captured_at` = Current Date (ISO 8601).
4. In the shortcut's settings, enable "Use with Share Sheet", restrict to URLs/text.

Both require the phone to be on the same Tailscale network as the laptop (ADR-019) — replace `<tailnet-hostname>` with the machine's Tailscale name, and `<your key>` with `OSCAR_API_KEY` from `.env`.

## Required behaviour either way

A shared payload is usually a URL and title only, with no job description text. It is saved immediately as `CAPTURED_PARTIAL` and flagged for enrichment — **never** presented as a complete capture. See [../../docs/09_MOBILE_CAPTURE_DESIGN.md](../../docs/09_MOBILE_CAPTURE_DESIGN.md) §4.

## M1 spike (per ADR-020)

1. Configure the iOS/Android share shortcut above; capture 5 real jobs from the LinkedIn app.
2. Install the PWA on the same phone; repeat the 5 captures via the OS share sheet.
3. Record what actually worked (especially iOS Safari's Web Share Target behaviour) as a note under ADR-020 in the decision log.
