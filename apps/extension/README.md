# apps/extension — Browser Extension

Chrome/Edge MV3, TypeScript, bundled with **esbuild** (not Vite — see `build.mjs` for why: content scripts and the service worker need different output formats). Design: [../../docs/08_BROWSER_EXTENSION_DESIGN.md](../../docs/08_BROWSER_EXTENSION_DESIGN.md).

Its entire API surface is one call: `POST /api/v1/jobs/capture`. No autofill, no automated browsing, no background scraping.

**V1 does not depend on this extension** — the web app's manual-URL and paste-text fallbacks (Job Inbox page) cover the same capture contract. The extension exists to hit the 5-second capture budget, not to enable capture.

## Build

```bash
npm install
npm run build      # -> dist/
npm run check      # tsc --noEmit
```

## Load unpacked

1. `chrome://extensions` (or `edge://extensions`) → enable Developer mode.
2. "Load unpacked" → select `apps/extension/dist/`.
3. Click the extension icon → Settings → set API base URL (default `http://127.0.0.1:8000/api/v1`) and the `OSCAR_API_KEY` from your `.env`.
4. Open any job posting, click the extension icon, click "Save this job".

## How it works

```text
popup click
  → background.ts: chrome.tabs.query (active tab)
  → chrome.scripting.executeScript(content.js)   [activeTab permission, on click only]
  → content.ts extracts text (selection → main/article → densest block → body)
  → content.ts sends the result back via chrome.runtime.sendMessage
  → background.ts builds a CaptureEnvelope and POSTs to /jobs/capture
  → popup shows "Saved as J042 (CAPTURED_COMPLETE)"
```

The API key lives only in `chrome.storage.local` and is only read by `background.ts` — the popup and content script never see it.

## Permissions

`activeTab` + `scripting` + `storage` only. No `<all_urls>`, no background scraping, no automated browsing (docs/08 §5).
