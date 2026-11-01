# 02 — User Journeys

The north-star metric is *human active minutes per application*, so every journey below is annotated with a **time budget per step**. The budget is the design constraint: if a step exceeds it, that step is the next thing to fix.

---

## Journey A — Desktop: find → save → tailor → apply → track

**Baseline today: 20–40 min. V1 budget: 3–5 min of human active time.**

| # | Step | Actor | Budget | Notes |
|---|---|---|---|---|
| 1 | Open a job posting | Human | — | Not counted; irreducible browsing |
| 2 | Click extension "Save" | Human | **5 s** | One click, no dialog, no leaving the page |
| 3 | Store job + raw snapshot | System | < 1 s | `POST /jobs/capture`; 201 before any parsing |
| 4 | Parse JD (best-effort) | System | async | Failure is invisible to the user and harmless |
| 5 | Open Job Detail, click "Generate CV" | Human | **10 s** | From inbox; keyboard-reachable |
| 6 | Generate grounded CV draft | System | < 60 s | Async with progress; user can do something else |
| 7 | Review draft, spot-check provenance | Human | **60–90 s** | The step V1 exists to make short and trustworthy |
| 8 | Edit or regenerate a section (optional) | Human | **0–60 s** | Should be rare if grounding + retrieval work |
| 9 | Save version + export PDF | Human | **10 s** | Version ID assigned automatically (`CV_J001_v2`) |
| 10 | Apply on the source site | Human | **60–180 s** | Manual in V1; the P2 autofill target |
| 11 | Click "I Applied" | Human | **5 s** | Links the exported CV version to the application |
| 12 | Later: click Assessment / Interview / Rejected / Offer | Human | **5 s each** | One click, timestamped event |

**Human total (steps 2–11): ~2.5–6 min.** The two steps that dominate are CV review (7) and the actual form (10) — which is exactly why P1 is parser/grounding quality and P2 is autofill, in that order.

### Alternate paths

- **No extension installed** → paste the URL into the web app (`manual_url`, no raw text → `NEEDS_ENRICHMENT`), or paste the JD text (`paste_text` → `CAPTURED_COMPLETE`). V1 is fully usable without the extension.
- **Page blocks text extraction** → user selects the JD text and saves the selection (`selected_text`).
- **Job not worth applying to** → mark `SKIPPED`; it leaves the backlog but stays in the captured-sample analytics.

### Failure paths

| Failure | User sees | Data outcome |
|---|---|---|
| Capture request fails (network/API down) | Error in extension popup with Retry | Nothing saved; retry is safe |
| Parser fails | "Not parsed — using raw JD" | Job + raw text intact |
| CV generation fails or LLM refuses | Error with Retry on Job Detail | No partial CV version persisted |
| Grounding rejects bullets | Bullets flagged/dropped, "missing requirements" note | CV version saved with a grounding report |
| PDF export fails | Error with Retry on CV Review | CV version intact; export is independently retryable |

---

## Journey B — Mobile: collect now, apply later

The realistic mobile pattern is **batch collection**: capture opportunistically during the day on the phone, then apply from the laptop in one sitting.

| # | Step | Actor | Budget | Notes |
|---|---|---|---|---|
| 1 | Browsing a posting in the LinkedIn/JobStreet app | Human | — | |
| 2 | Share → OSCAR Job Copilot | Human | **5 s** | OS share sheet |
| 3 | Receive payload (`url`, `title`, maybe `shared_text`) | System | < 1 s | Often URL + title **only** |
| 4 | Save immediately, set completeness honestly | System | < 1 s | `CAPTURED_PARTIAL` when no JD text |
| 5 | Show simple success state | System | — | Must be unambiguous; this is the whole mobile UX |
| 6 | Later, on desktop: open the job, paste JD text | Human | **20 s** | Adds a 2nd raw snapshot; upgrades to `CAPTURED_COMPLETE` |
| 7 | Continue from Journey A step 5 | | | |

**Design rule:** never pretend extraction succeeded. A partial capture that is honestly labelled is a success; a partial capture presented as complete silently poisons CV generation later. See [09_MOBILE_CAPTURE_DESIGN](09_MOBILE_CAPTURE_DESIGN.md).

**Resolved before M1:** a laptop-local API doesn't work off-LAN by default, so reachability is solved via Tailscale (ADR-019 in [17_DECISION_LOG](17_DECISION_LOG.md); detail in [09_MOBILE_CAPTURE_DESIGN](09_MOBILE_CAPTURE_DESIGN.md) §2). Still the single largest V1 architectural risk to watch during M1, because mobile capture is a P0 requirement and the awake-laptop trade-off is accepted, not eliminated.

---

## Journey C — Weekly review

| # | Step | Actor | Budget |
|---|---|---|---|
| 1 | Open Dashboard | Human | — |
| 2 | Read KPIs + funnel + conversion | Human | 30 s |
| 3 | Read action queue ("12 CV-ready not applied", "5 saved > 5 days", "2 assessments pending") | Human | 20 s |
| 4 | Click an action item → pre-filtered inbox | Human | 5 s |
| 5 | Work the backlog (Journey A from step 5) | Human | per job |
| 6 | Check role/source/skill trends to steer next week's search | Human | 60 s |

The dashboard must be **actionable, not passive** (FR-011): every backlog number is a link to the exact jobs it counts.

---

## Journey D — Career profile maintenance (occasional)

| # | Step | Budget | Notes |
|---|---|---|---|
| 1 | Initial population of experiences/projects/skills/achievements | 60–120 min, **one time** | The quality ceiling for every future CV — worth doing carefully |
| 2 | Add a new achievement after finishing something notable | 2–3 min, occasional | Statement + tags + whether the metric is *verified* |
| 3 | Correct or retire a fact | 1 min, rare | Existing CV versions stay immutable |

Step 1 is the real onboarding cost of the product and it happens in Milestone 2. Nothing downstream — grounding, tailoring quality, fit score — can be better than this data.
