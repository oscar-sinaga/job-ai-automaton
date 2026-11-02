# OSCAR Job Copilot — Design Pack

Produced before implementation per master spec §30/§40. These are living design
documents; see the current readiness status below and the first-usage guide.

Source specs: [`../OSCAR_Job_Copilot_AI_Agent_Master_Spec_v2.md`](../OSCAR_Job_Copilot_AI_Agent_Master_Spec_v2.md) (engineering) · [`../OSCAR_Job_Copilot_User_Plan_v2.md`](../OSCAR_Job_Copilot_User_Plan_v2.md) (product, Indonesian).

## Read in this order

| # | Document | Read it for |
|---|---|---|
| 01 | [PRD](01_PRD.md) | Requirements contract: FRs with acceptance tests, NFRs with targets, edge cases, V1 DoD |
| 02 | [User Journeys](02_USER_JOURNEYS.md) | The flows, with per-step **time budgets** tied to the north-star metric |
| 03 | [System Architecture](03_SYSTEM_ARCHITECTURE.md) | Components, module dependency rules, request flows, auth, failure handling |
| 04 | [Data Model](04_DATA_MODEL.md) | ERD, DDL, indexes, constraints, **status state machine**, dedupe, migrations |
| 05 | [API Design](05_API_DESIGN.md) | Endpoint contracts with real payloads, error taxonomy, idempotency |
| 06 | [AI / LLM Design](06_AI_LLM_DESIGN.md) | Provider port, structured output, prompt caching, **cost model** |
| 07 | [CV Grounding & Evals](07_CV_GROUNDING_AND_EVALS.md) | **The safety-critical document.** Verification rules V1–V6, eval metrics |
| 08 | [Browser Extension](08_BROWSER_EXTENSION_DESIGN.md) | Capture contract, extraction heuristic, minimal permissions |
| 09 | [Mobile Capture](09_MOBILE_CAPTURE_DESIGN.md) | Reachability problem (**open**), client options, partial captures |
| 10 | [Analytics Definitions](10_ANALYTICS_DEFINITIONS.md) | Every formula in SQL, with cohort and edge-case semantics |
| 11 | [Security & Privacy](11_SECURITY_PRIVACY.md) | Data inventory, secrets, log redaction, third-party disclosure |
| 12 | [Test Strategy](12_TEST_STRATEGY.md) | What must never break, and the tests that guard it |
| 13 | [Observability](13_OBSERVABILITY.md) | Log schema, failure taxonomy, the queries that matter |
| 14 | [Deployment Plan](14_DEPLOYMENT_PLAN.md) | Local topology, env vars, **backups**, runbook |
| 15 | [Roadmap & Milestones](15_ROADMAP_AND_MILESTONES.md) | M0–M6 with exit criteria and decision gates |
| 16 | [Risk Register](16_RISK_REGISTER.md) | Risks with **detection signals**, plus consciously accepted risks |
| 17 | [Decision Log](17_DECISION_LOG.md) | 26 ADRs, including the selection-only pilot (ADR-026), + **4 open decisions** |
| 18 | [First Real Usage](18_FIRST_REAL_USAGE.md) | Current fixes, profile setup, first 3–5 applications, and remaining verification |
| 19 | [Offline Simulation](19_OFFLINE_SIMULATION.md) | No-API test entry point, desktop/mobile browser checks, results and limitations |

## If you only read three

1. **[07 — CV Grounding](07_CV_GROUNDING_AND_EVALS.md)** — holds the product's one non-negotiable promise (zero fabricated claims).
2. **[17 — Decision Log](17_DECISION_LOG.md)** — ADR-019/020 settled how mobile reachability and the mobile client work (Tailscale + share-shortcut → PWA); §2 has the 4 decisions still open, none of which block Milestone 1.
3. **[15 — Roadmap](15_ROADMAP_AND_MILESTONES.md)** — what gets built when, and what each milestone must prove.

## Current state

**2026-11-02:** M0–M5 implementation exists. Review fixes cover CV grounding,
skills, edits, approval status and PDF export/download. The initial flow has been
tested with example data and a fake model. Real profile entry, model evaluation,
phone capture and M6 usage targets still require verification. Start at [18](18_FIRST_REAL_USAGE.md).

Docs are living documents — a changed decision is recorded in [17](17_DECISION_LOG.md) and reflected here *before* the code changes.
