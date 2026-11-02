# 01 — PRD: OSCAR Job Copilot

**Status:** draft, awaiting product-owner approval · **Owner:** Oscar (product owner *and* sole user) · **Updated:** 2026-08-28

Source specs: [`../OSCAR_Job_Copilot_AI_Agent_Master_Spec_v2.md`](../OSCAR_Job_Copilot_AI_Agent_Master_Spec_v2.md), [`../OSCAR_Job_Copilot_User_Plan_v2.md`](../OSCAR_Job_Copilot_User_Plan_v2.md). This PRD is the requirements contract; the specs hold the product rationale.

---

## 1. Problem

One job application costs 20–40 minutes of human attention, and most of it is not spent deciding whether to apply:

| Activity | Typical cost | Nature |
|---|---|---|
| Find & open the posting | 2–5 min | Irreducible (human judgement) |
| Save the link somewhere findable | 1–2 min | **Pure overhead** |
| Copy the job description into notes | 2–4 min | **Pure overhead** |
| Re-read own CV, decide what to emphasise | 5–10 min | Compressible with a fact store |
| Rewrite CV bullets/summary for this job | 8–15 min | Compressible with grounded generation |
| Rename/organise the CV file, remember which version | 1–3 min | **Pure overhead** |
| Fill the application form | 3–8 min | Compressible later (P2 autofill) |
| Record that it was applied, and later statuses | 1–3 min | **Pure overhead** |

Roughly **8–13 minutes per application is pure bookkeeping overhead**, and it is the part that silently degrades: links get lost, JDs are never saved, CV versions become `CV_final_v3_REAL.pdf`, and status tracking stops after week two — which destroys the data needed to tell whether the job search strategy is working at all.

## 2. Vision

A personal job-search operating system: capture any job in seconds, keep its raw text forever, generate a tailored CV that is provably built only from verified career facts, know exactly which CV went to which application, and see the funnel truthfully. Automate more over time — but only where automation is measurably reliable.

## 3. Target User

Single user: Oscar Michael Sinaga, MLOps/ML engineer. Searching across LinkedIn, JobStreet, Glints, Dealls, Kalibrr, and company career pages, from both a Windows laptop and an Android/iOS phone. Technically capable (can run `docker compose`, edit `.env`), so V1 may be locally hosted and rough-edged, but it must be *reliable* — this is a tool used under time pressure while actually job hunting.

Not a target user (V1): anyone else. No multi-tenancy, no signup flow, no sharing. See [17_DECISION_LOG](17_DECISION_LOG.md) ADR-002.

## 4. Jobs To Be Done

1. When I find a job I might want, **save it in under 10 seconds** without leaving the page or copy-pasting.
2. When I'm on my phone and can't apply now, **capture it for later** without losing the posting.
3. When I sit down to apply, **get a tailored CV draft in under 2 minutes** that I trust enough to send.
4. When I send it, **record which exact CV version went out**, permanently.
5. When something happens (assessment, interview, rejection, offer), **log it in one click**.
6. When I plan next week, **see which sources, roles, and skills are actually converting**.

## 5. Goals

| Goal | Measure | V1 target |
|---|---|---|
| G1 Cut human active time per application | median minutes from opening job → applied+tracked | 3–5 min (from 20–40) |
| G2 Cut tailored-CV preparation time | median minutes from "generate" → export-ready | < 2 min |
| G3 Never fabricate a career claim | fabricated claims in exported CVs | **0** (hard gate) |
| G4 Never lose captured data | jobs lost to parser/LLM/UI failure | **0** |
| G5 Make the funnel visible | dashboard reflects real captured/applied state | correct on ≥50 jobs, ≥25 applications |

G3 is non-negotiable and outranks every other goal, including speed: a fast generator that invents experience is a product failure, not a tradeoff. See [07_CV_GROUNDING_AND_EVALS](07_CV_GROUNDING_AND_EVALS.md).

## 6. Non-Goals (V1)

Full autonomous applying · CAPTCHA solving or anti-bot circumvention · device-fingerprint spoofing · proxy rotation for evasion · mass scraping of protected platforms · perfect parser accuracy · ML-based job recommendation · a design system or polished UI · multi-user RBAC · a data warehouse · microservices · form autofill · ATS-specific automation · full mobile feature parity.

Each of these is deliberately excluded, not merely unscheduled. Anything on this list appearing in a V1 PR is scope creep (master spec §24, Decision Rules 5–7).

## 7. Scope

**In V1 (P0):** universal job capture (desktop extension + manual URL + paste text + mobile share) · immutable raw job storage · job inbox · master career profile · grounded tailored CV generation · CV review/edit/regenerate/version · PDF export · application tracker with 11 statuses · append-only event history · analytics dashboard (KPIs, funnel, conversion, backlog, trends, role/source/skill) · action queue.

**P1 (post-V1, must not block V1):** parser quality, fit score, application-question assistant, role/skill taxonomy.
**P2+:** autofill, browser application assistant, ATS adapters, selective autonomy, autonomous discovery.

## 8. Functional Requirements

Each FR carries the acceptance test that proves it. `M` = milestone that delivers it ([15_ROADMAP_AND_MILESTONES](15_ROADMAP_AND_MILESTONES.md)).

| ID | Requirement | M | Acceptance test |
|---|---|---|---|
| FR-001 | Capture a job from desktop via extension, manual URL, or pasted text. Store source, URL, raw text, page title, `captured_at`, capture method, metadata. | M1 | One click on a live posting yields a job row + raw snapshot; API returns 201 in < 1s |
| FR-002 | Capture a job from mobile via the OS share sheet. Partial payloads (URL/title only) must save successfully. | M1 | Sharing from the LinkedIn Android app creates a job with `capture_completeness=CAPTURED_PARTIAL` |
| FR-003 | Raw snapshots are append-only and never overwritten; a job may hold many. | M1 | Enriching a partial capture adds a 2nd snapshot; the 1st is byte-identical afterwards |
| FR-004 | Parse JD into structured fields with per-field confidence. Parser failure must never block anything. | M3 | With the parser stubbed to raise, capture still succeeds and CV generation still runs from raw text |
| FR-005 | Editable master career profile as the single source of truth, with tagged, individually-addressable career facts. | M2 | Every achievement has a stable ID, skill/domain/tech tags, and an optional *verified* metric |
| FR-006 | Generate a tailored CV from career facts + raw JD. **No unsupported claims.** Every bullet cites supporting fact IDs. | M3 | Eval set: 0 fabricated claims survive verification; each output bullet maps to ≥1 valid fact ID |
| FR-007 | Review CV: preview, edit, regenerate a section, compare versions, save, mark final, export PDF. | M3 | A CV can be edited and exported; both v1 and v2 remain retrievable |
| FR-008 | Track application status across the 11 defined statuses via one-click actions. | M4 | "Mark as Applied" transitions status and links the submitted CV version |
| FR-009 | Append-only event log with `event_id`, entity, type, timestamp, actor, metadata. | M4 | Every status change writes exactly one event; events are never updated or deleted |
| FR-010 | Analytics dashboard: KPIs, funnel, conversion, backlog, weekly/monthly trends, role/source/skill analytics, productivity. | M5 | Funnel numbers reconcile with hand-counted fixture data |
| FR-011 | Action queue: actionable backlog items that navigate directly to a filtered job list. | M5 | "12 jobs: CV ready but not applied" links to the inbox pre-filtered to exactly those 12 |

## 9. Non-Functional Requirements

| ID | Requirement | Measurable target / verification |
|---|---|---|
| NFR-001 Simplicity | Functional UI, no custom design system, keyboard-efficient | No animation/design-system work in V1; inbox reachable in ≤1 click from anywhere |
| NFR-002 Reliability | Core flows degrade gracefully; no data loss on component failure | Fault-injection tests: parser raises, LLM times out, PDF render fails → job + raw JD intact in all three |
| NFR-003 Observability | Every important workflow logs component, action, result, latency, error type, version, IDs | Structured JSON logs; a failed CV generation is diagnosable from logs alone ([13_OBSERVABILITY](13_OBSERVABILITY.md)) |
| NFR-004 Privacy | Career/application data treated as private; no plaintext credentials; secrets from env; export/delete; log redaction | No secret in git (CI check); logs contain no raw JD text or PII beyond IDs ([11_SECURITY_PRIVACY](11_SECURITY_PRIVACY.md)) |
| NFR-005 Maintainability | Modular boundaries so later automation slots in without rewriting V1 | Domain modules have no circular imports; site-specific extractors live behind an adapter interface |
| NFR-006 Latency | Interactive operations feel immediate | Capture < 1s p95; dashboard < 2s p95; CV generation < 60s p95 (async with progress) |

NFR-006 is added here (not in the master spec) because "human minutes per application" is the north-star metric — capture latency is directly part of it.

## 10. User Stories

**US-1 — One-click desktop capture**
Given I am viewing a job posting and the extension is installed, when I click Save, then the job is stored with its raw text and I see a success confirmation without leaving the page.

**US-2 — Mobile capture with partial data**
Given I am in the LinkedIn mobile app, when I share a posting to OSCAR Job Copilot, then a job is created even if only a URL and title were shared, and it is visibly marked as needing enrichment.

**US-3 — Grounded CV generation**
Given a saved job with raw JD text and a populated career profile, when I request a CV, then I receive a draft where every bullet is traceable to a career fact ID, and any JD requirement I cannot substantiate appears in a "missing requirements" note rather than being invented.

**US-4 — Version traceability**
Given I exported CV v2 for a job and applied with it, when I later open the application, then it shows that v2 (not v1) was submitted, and v2's exact content is still retrievable.

**US-5 — One-click status update**
Given an applied job, when I click "Interview Received", then the status advances and a timestamped `INTERVIEW_RECEIVED` event is recorded.

**US-6 — Honest funnel**
Given 50 saved and 25 applied jobs, when I open the dashboard, then saved→applied conversion equals 25/50 by the documented formula, and the metric's cohort semantics are stated on screen.

**US-7 — Backlog rescue**
Given jobs with a CV ready but no application, when I open the dashboard, then the action queue tells me how many and one click takes me to exactly those jobs.

## 11. Edge Cases

| Case | Required behaviour |
|---|---|
| Mobile share gives URL only, no JD | Save as `CAPTURED_PARTIAL`; never fake extraction; allow later paste-text enrichment |
| Same job saved twice | Save both; mark the newer one `duplicate_of_job_id`; never block the save (master spec §13) |
| Parser returns garbage or fails | Job unaffected; CV generation reads raw JD; user can correct fields manually |
| JD text is very short (< ~200 chars) | Allow generation but warn that tailoring quality will be low |
| JD requires a skill Oscar lacks | Surface in "missing requirements"; never add the skill to the CV |
| A career fact has an unverified metric | Generator may use the statement but not the number ([07_CV_GROUNDING_AND_EVALS](07_CV_GROUNDING_AND_EVALS.md)) |
| LLM refuses or times out | No partial CV version is persisted; user can retry; failure is logged with `error_type` |
| PDF render fails | CV version survives; export can be retried independently |
| Job withdrawn or skipped | Excluded from conversion denominators per [10_ANALYTICS_DEFINITIONS](10_ANALYTICS_DEFINITIONS.md) |
| Applying twice to the same job | Modelled as a second application row on the same job; funnel counts jobs, not attempts |
| Career profile edited after a CV was generated | Existing CV versions are immutable snapshots; provenance fact IDs may point to since-edited facts (record `generated_at`) |

## 12. Product Metrics

Primary: **human active minutes per application** (G1). Supporting KPIs and their exact formulas — including cohort and time-window semantics — are defined once in [10_ANALYTICS_DEFINITIONS](10_ANALYTICS_DEFINITIONS.md) and must not be re-derived elsewhere. Quality metrics: fabricated-claim count (target 0), user CV edit rate, parser correction rate.

Instrumentation caveat that must appear in the UI: **V1 analytics describe the jobs Oscar captured, not the job market.**

## 13. V1 Definition of Done

All of FR-001…FR-011 accepted, plus the real-usage bar from master spec §29 / user-plan §15:

- ≥ 50 real jobs captured · ≥ 25 real applications tracked
- median tailored-CV preparation < 2 min · human active time per application 3–5 min
- **0** known fabricated claims in any exported/submitted CV
- dashboard funnel and backlog verified correct against manual counts

This bar is measured in **Milestone 6 (Stabilization)**. Implementation now covers
M0–M5 with further regression fixes. Current technical and real-usage readiness
are recorded in the README and [20_MVP_PILOT.md](20_MVP_PILOT.md).

## 14. Future Roadmap

P1 → P5 as listed in §7 and detailed in master spec §23 / user-plan §7–§11. Deliberately not designed further: post-V1 priorities must be chosen from real usage data (which bottleneck actually costs the most minutes), not from today's guesses — see [15_ROADMAP_AND_MILESTONES](15_ROADMAP_AND_MILESTONES.md) §"Choosing V2".
