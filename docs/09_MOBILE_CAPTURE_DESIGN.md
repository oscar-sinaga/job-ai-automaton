# 09 — Mobile Capture Design

Not implemented in Milestone 0 (`apps/mobile/` holds a README only). Reachability (§2) and client approach (§3) were open questions in this document; both are now decided (ADR-019, ADR-020 in [17_DECISION_LOG](17_DECISION_LOG.md)) and Milestone 1 mobile work can proceed directly.

Mobile capture is FR-002, a **P0 requirement** — the realistic usage pattern is collecting jobs on the phone during the day and applying from the laptop later ([02_USER_JOURNEYS](02_USER_JOURNEYS.md) Journey B).

---

## 1. Requirement

```text
LinkedIn / JobStreet app, or mobile browser
        │  Share
        ▼
OSCAR Job Copilot
        │
        ▼
Job saved (partial is fine and expected)
```

Required capabilities, and nothing more (master spec FR-002):

- receive a shared URL/text,
- create a job through the same `POST /api/v1/jobs/capture` endpoint desktop uses,
- return a simple, unambiguous success state,
- list saved jobs,
- optionally show CV-ready status.

Explicitly **not** required: mobile CV review, mobile PDF export, offline mode, or any feature parity with the web app.

## 2. The Reachability Problem — decided: Tailscale (ADR-019)

A phone cannot reach `http://localhost:8000` on the laptop. Every client-side approach in §3 fails without solving this first, so it is the prior decision.

| Option | Works on mobile data | Data leaves device | Laptop must be awake | Setup cost |
|---|---|---|---|---|
| **A.** LAN IP (`http://192.168.1.x:8000`) | ✗ | No | Yes | none |
| **B.** Tailscale / private mesh VPN | ✓ | No | Yes | ~15 min, free tier |
| **C.** Cloudflare Tunnel (public hostname) | ✓ | No (transits CF) | Yes | ~30 min + auth hardening |
| **D.** Host API + Postgres on a VPS | ✓ | **Yes** | No | ongoing $ + ops + privacy scope |

Option A fails precisely when capture matters most — browsing jobs on the train. Option D is the only one that removes the awake-laptop constraint, but it moves the career fact store and every raw JD off Oscar's machine, which materially expands [11_SECURITY_PRIVACY](11_SECURITY_PRIVACY.md)'s scope.

**Decided: B (Tailscale) for V1** (ADR-019). Real mobile capture, data stays on-device, no public attack surface, no recurring cost. The awake-laptop limitation is an accepted trade-off, measured during stabilization; if it turns out to actually cause missed captures, D gets revisited with eyes open.

A pragmatic mitigation if the laptop is asleep: the share sheet's failure must be *recoverable*, not silent — see §5.

## 3. Client Approach — decided: share-shortcut now, PWA share target for V1 (ADR-020)

| # | Approach | Effort | iOS | Android | Verdict |
|---|---|---|---|---|---|
| 1 | **OS share shortcut → HTTP POST** (iOS Shortcuts / Android intent-to-HTTP app) | ~1 hour, zero build pipeline | ✓ | ✓ | **Prototype first.** Proves the whole flow end-to-end before any app code exists |
| 2 | **PWA Web Share Target** (`share_target` in the SvelteKit manifest) | ~1 day | ⚠ limited/inconsistent in Safari | ✓ good | **Target for V1** on Android; validate iOS in a spike |
| 3 | **Capacitor wrapper + native share extension** | ~1 week + signing/TestFlight | ✓ reliable | ✓ | Fallback only if 2 proves unworkable on iOS |

**Recommended sequence:** ship #1 immediately (it is a configuration exercise, not software, and it makes mobile capture real in Milestone 1), add #2 as the proper V1 path, and treat #3 as contingency requiring explicit approval given its cost relative to a single-user tool.

This sequencing means mobile capture is never the thing blocking Milestone 1 — a deliberate choice given that master spec §41 rates "mobile capture unreliable" as the highest-impact product risk and instructs testing share flows early.

## 4. Partial Capture Handling (the core design constraint)

Mobile share payloads usually contain a URL and title, sometimes a short snippet, and almost never the full JD.

```text
Shared payload: { url, title, shared_text? }
        │
        ├─ build CaptureEnvelope, capture_method = "mobile_share"
        ├─ POST /api/v1/jobs/capture  (with Idempotency-Key)
        │
        ├─ server derives completeness:
        │     JD-length text present → CAPTURED_COMPLETE
        │     URL/title only         → CAPTURED_PARTIAL
        │
        ├─ job appears in the inbox, visibly flagged as needing enrichment
        │
        └─ later, desktop: paste full JD → new snapshot → CAPTURED_COMPLETE
```

**Never pretend extraction succeeded.** A partial capture honestly labelled is a success; a partial capture presented as complete silently degrades CV generation weeks later, when the cause is no longer obvious. The server derives completeness rather than trusting the client precisely so this cannot be gotten wrong by a client bug ([08_BROWSER_EXTENSION_DESIGN](08_BROWSER_EXTENSION_DESIGN.md) §2).

The inbox must make `CAPTURED_PARTIAL` visually obvious and offer a one-tap "paste JD" action, because an unenriched partial capture is exactly the kind of item that quietly rots in a backlog.

## 5. Failure and Retry (NFR-002)

"A mobile share failure must provide a retry" is a stated non-functional requirement, and with the laptop-hosted API of §2 option B, failure is a *normal* condition (laptop asleep), not an exception.

- Every capture attempt generates a client-side `Idempotency-Key`, so retrying can never create a duplicate job ([04_DATA_MODEL](04_DATA_MODEL.md) §8).
- On failure the payload is queued locally (PWA: IndexedDB) and retried when the app is next opened with connectivity — the URL is never lost just because the API was unreachable.
- The user sees an explicit "queued, not yet saved" state. Ambiguity here is worse than failure: a user who believes a job was saved stops trying to save it.

For approach #1 (share shortcut), no local queue is possible — the failure surfaces as an OS-level error, and the user re-shares. That limitation is one of the main reasons #2 is the real V1 target rather than the endpoint.

## 6. Milestone 1 Spike (timeboxed)

The approach is decided (ADR-019, ADR-020); this spike validates it against real behaviour rather than choosing among options from a standing start.

1. Configure approach #1 on Oscar's actual phone; capture 5 real jobs from the LinkedIn app over Tailscale. Record what fields each source app actually shares.
2. Add `share_target` to the web manifest; test the same 5 captures as an installed PWA on Android, then on iOS Safari.
3. Record the measured outcome as a note under ADR-020 in [17_DECISION_LOG](17_DECISION_LOG.md) — confirming the plan, or triggering the fallback in step 4 below.

Timebox: 1 day. If iOS PWA share proves unusable, record the finding and defer approach #3 (Capacitor) to a separate approved milestone rather than absorbing a week of native work into M1.
