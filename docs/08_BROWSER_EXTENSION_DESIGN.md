# 08 — Browser Extension Design

Not implemented in Milestone 0 (`apps/extension/` holds a README only). Design for Milestone 1.

**V1 is usable without this extension** — the manual-URL and paste-text fallbacks in the web app cover the same capture contract (§7). That is deliberate: the extension is an accelerator for the 5-second capture budget, not a dependency.

---

## 1. Principle: Generic First

Per master spec §8A and §14, and Decision Rule 15: the extension is **not** built around LinkedIn or JobStreet. It has one generic path that works on any page, and site-specific extractors are optional later refinements behind the same contract.

```text
GenericJobCapture
   ├── GenericExtractor        ← V1, the only one
   ├── LinkedInExtractor       ← optional later, quality only
   ├── JobStreetExtractor      ← optional later
   └── ATS extractors          ← P3
```

If an extractor is missing or throws, capture still succeeds with generic text. A site-specific extractor may never be a prerequisite for saving a job.

## 2. Capture Contract

Shared by extension, mobile share, and web fallbacks — this is the single entry point to the system ([05_API_DESIGN](05_API_DESIGN.md) §3):

```typescript
interface CaptureEnvelope {
  url: string;                  // required
  captured_at: string;          // required, ISO 8601 with offset
  source_hint?: string;         // hostname, e.g. "linkedin.com" — a hint, not a trusted classification
  page_title?: string;
  raw_text?: string;            // generic visible-text extraction
  selected_text?: string;       // user's text selection, when used as the fallback
  shared_text?: string;         // mobile share payload; unused on desktop
  capture_method: "extension" | "manual_url" | "paste_text" | "mobile_share";
  metadata?: Record<string, unknown>;   // extension_version, extractor used, truncation flag
}
```

`capture_completeness` is **not** in the envelope — the server derives it, so a buggy or malicious client cannot claim a partial capture is complete.

## 3. Flow

```text
User views a job posting
   │
   ├─ clicks the toolbar icon (or presses the configured shortcut)
   │
   ├─ background script → chrome.scripting.executeScript on the active tab
   │
   ├─ content script extracts: document.title, location.href, visible JD text
   │
   ├─ POST /api/v1/jobs/capture   with X-API-Key + Idempotency-Key
   │
   ├─ 201 → badge turns green, popup shows "Saved as J042" (+ duplicate note if any)
   └─ error → popup shows the reason + Retry (same Idempotency-Key, so retry is safe)
```

Target: **≤ 5 seconds of human time, one click, no navigation away from the page** (the step-2 budget in [02_USER_JOURNEYS](02_USER_JOURNEYS.md)).

## 4. Text Extraction Heuristic

The generic extractor, in order, taking the first that yields ≥ 400 characters:

1. A user text selection, if present (highest signal — the user pointed at the JD).
2. `<main>`, `[role="main"]`, or `<article>` `innerText`.
3. The densest text block: the DOM element with the highest text-length-to-link-density ratio (a Readability-style heuristic).
4. `document.body.innerText` as the last resort.

Post-processing: collapse runs of whitespace, strip obvious navigation/footer boilerplate by line heuristics, cap at **200 KB** (server also caps; over-cap sets `metadata.truncated = true` rather than failing).

Which branch produced the text is recorded in `metadata.extractor` — that is the data needed to know whether the heuristic is actually working across real sites, instead of guessing.

## 5. Permissions (minimal by design)

```json
{
  "manifest_version": 3,
  "name": "OSCAR Job Copilot",
  "permissions": ["activeTab", "storage", "scripting"],
  "host_permissions": ["http://127.0.0.1:8000/*"],
  "action": { "default_popup": "popup.html" },
  "background": { "service_worker": "background.js", "type": "module" }
}
```

- **`activeTab` + `scripting`, not `<all_urls>`** — the extension can only read a page after the user clicks it. It cannot read browsing history or scrape in the background.
- `host_permissions` is limited to the local API origin (adjusted if OPEN-1 resolves to a Tailscale/tunnel hostname — [03_SYSTEM_ARCHITECTURE](03_SYSTEM_ARCHITECTURE.md) §6).
- No `tabs` permission, no content script auto-injection, no automated browsing or search. Automated discovery is an explicit V1 non-goal (master spec §14, §24).
- Raw page capture is limited to pages the user explicitly saves, satisfying the "restrict capture to relevant job/application pages" requirement in user-plan §18.

## 6. Auth, Config, and CORS

- The API key is entered once in the extension options page and kept in `chrome.storage.local`; it is sent as `X-API-Key`. It is not a user credential and grants nothing beyond this local API.
- API base URL is also configurable (so switching from `localhost` to a Tailscale hostname needs no rebuild).
- The API allows the extension origin (`chrome-extension://<id>`) in its CORS allowlist for `POST /jobs/capture` only.
- The key is never logged, never included in telemetry, and never written to the page.

## 7. Fallbacks Available in the Web App (no extension needed)

| Fallback | `capture_method` | Resulting completeness |
|---|---|---|
| Paste a URL | `manual_url` | `NEEDS_ENRICHMENT` |
| Paste the JD text (with or without URL) | `paste_text` | `CAPTURED_COMPLETE` |

These exist from Milestone 1 and are what make the extension optional. They also serve the enrichment path for partial mobile captures ([05_API_DESIGN](05_API_DESIGN.md) §3).

## 8. Build and Distribution

TypeScript, bundled with **esbuild** (ADR-021 — not Vite as originally sketched here: `background.js` needs ES-module output while `content.js`, injected via `chrome.scripting.executeScript({files:[...]})`, must be a self-contained classic script (IIFE) — esbuild's per-call `format` option handles that directly; Vite's dev-server/HTML-multi-page model fights it without an extra plugin). Plain HTML/TS for the popup and options page — no framework; a two-element popup doesn't justify one. Loaded unpacked in Chrome/Edge developer mode; no store submission for a single-user tool.

The content script reports its extraction result via `chrome.runtime.sendMessage` rather than relying on `executeScript`'s "last statement completion value" mechanism — a bundled script's code ends up inside a function, and a function without an explicit `return` always completes as `undefined` regardless of its last expression. Messaging is robust to how the bundler wraps the code.

Tests: unit tests for the extraction heuristic against saved HTML fixtures from real job pages ([12_TEST_STRATEGY](12_TEST_STRATEGY.md) §Fixtures). The heuristic is the part that will break as sites change, so it is the part that must be testable offline.

## 9. Non-Goals

No autofill, no form interaction, no submission detection, no ATS logic, no background scraping, no reading pages the user did not explicitly save. The extension's entire API surface is one call: `POST /api/v1/jobs/capture`.
