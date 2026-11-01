# MASTER SPEC — OSCAR Job Copilot
## Instructions for Codex / Claude / AI Software Engineering Agent

---

# 0. Purpose of This Document

You are the principal:

- Product Manager
- Product Owner
- Software Architect
- Senior Full-Stack Engineer
- Browser Extension Engineer
- Mobile Engineer
- Backend Engineer
- Data Engineer
- AI/LLM Engineer
- Analytics Engineer
- QA Engineer
- Security Reviewer
- DevOps Engineer
- Technical Writer

for a project named **OSCAR Job Copilot**.

Your job is **not** to immediately produce code.

Your first responsibility is to inspect this specification and produce a complete, internally consistent product and engineering plan before implementation.

The product must become genuinely usable for real job applications within a few months.

The frontend should be simple during early phases. Functional completeness, reliability, data quality, maintainability, and iteration speed are more important than visual polish.

---

# 1. Product Mission

Build a personal job-search operating system that:

1. lets a user capture job opportunities from desktop and mobile with minimal friction;
2. stores the raw job description and source permanently;
3. creates grounded, job-specific CV versions using a verified master career profile;
4. tracks the exact CV version used for each application;
5. tracks application status and history;
6. provides an analytics dashboard for funnel, trends, backlog, role/source/skill distribution, and conversion;
7. progressively automates repetitive steps over time;
8. always preserves a human fallback for fragile or ambiguous workflows.

The product should evolve from:

```text
Human-in-the-loop assistant
        ↓
Application accelerator
        ↓
ATS-aware copilot
        ↓
Selective autonomous agent
```

---

# 2. Core Product Principle

> Automatic where automation is reliable, human-assisted where automation is fragile.

Do not make full autonomous job application the MVP.

Do not design the system around bypassing CAPTCHAs, anti-bot systems, device fingerprinting, access controls, or site protections.

When a workflow becomes blocked or uncertain:

```text
PAUSE
→ HUMAN_REQUIRED
→ user completes the blocked step
→ RESUME if applicable
```

Automation should increase only through stable, permitted, testable workflows.

---

# 3. Primary User Outcome

The user wants, within a few months, to:

- find jobs normally using LinkedIn, JobStreet, Glints, Dealls, Kalibrr, company career pages, etc.;
- save jobs almost instantly from desktop or mobile;
- avoid manually copying job descriptions;
- generate a tailored CV very quickly;
- avoid repeatedly rewriting the same CV;
- know which CV version was submitted to which job;
- apply faster;
- track how far each application has progressed;
- see trends in the types of jobs being targeted;
- understand sources, roles, and skills that generate better results;
- gradually reduce manual work.

---

# 4. North-Star Metric

**Human active time per application**

The engineering organization should optimize:

```text
Human Minutes / Application
```

while preserving:

- CV factual correctness;
- application quality;
- traceability;
- data integrity;
- user control;
- application conversion.

Target direction:

```text
Manual            ~20–40 min
V1                ~3–5 min
Later assisted    ~1–2 min
Selective auto    seconds of human intervention
```

Do not optimize application volume at the expense of quality or reliability.

---

# 5. MVP / V1 Product Scope

V1 must be a real, usable end-to-end product.

V1 must include:

1. Universal Job Capture
2. Job Inbox
3. Raw Job Storage
4. Master Career Profile
5. Grounded Tailored CV Generator
6. CV Review & Versioning
7. Application Tracker
8. Event History
9. Analytics Dashboard
10. Desktop + Mobile capture workflow

V1 must **not** be blocked by:

- perfect parser;
- autofill;
- ATS automation;
- automatic submission;
- mass scraping;
- full mobile feature parity;
- advanced ML ranking;
- visual polish.

---

# 6. V1 Functional Requirements

## FR-001 — Job Capture from Desktop

Support at least:

- browser extension;
- manual URL fallback;
- paste-text fallback.

Capture:

- source;
- URL;
- raw visible text / job description;
- captured_at;
- page title;
- company/title/location when easily available;
- optional page metadata.

Critical rule:

**Raw content must be stored before or independently of parsing.**

## FR-002 — Job Capture from Mobile

The system must support a share workflow.

Expected UX:

```text
LinkedIn / JobStreet / Browser App
        ↓
Share
        ↓
OSCAR Job Copilot
        ↓
Job saved
```

Mobile V1 may be lightweight.

Required capabilities:

- receive shared URL/text;
- create Job record;
- return simple success state;
- show saved jobs;
- optionally show CV-ready status.

Do not build a complex mobile UI unless necessary.

## FR-003 — Raw Job Snapshot

For every captured job store:

```text
job_id
source
url
raw_text
page_title
captured_at
capture_method
raw_metadata
```

Raw snapshots should be immutable or versioned.

Do not overwrite original captured content.

## FR-004 — Basic Job Parser

Parser is P1-quality inside V1, not a release blocker.

Extract where possible:

```text
title
company
location
work_mode
salary_min
salary_max
salary_currency
seniority
employment_type
experience_years
required_skills
preferred_skills
responsibilities
education
language
```

Requirements:

- structured output;
- confidence scores where useful;
- missing field allowed;
- correction UI;
- parser failure must not prevent CV generation.

CV generation can use raw JD directly.

## FR-005 — Master Career Profile

Create a structured, editable source of truth.

Required entities:

```text
ProfessionalProfile
Experience
Project
Achievement
Skill
Technology
Education
Certification
Link
ApplicationProfile
Preference
```

Each career fact should support:

```text
id
statement
context
source entity
skill tags
domain tags
technology tags
metrics if verified
date range
verification status
notes
```

## FR-006 — Grounded CV Generation

Input:

```text
Master Career Profile
+
Raw Job Description
+
optional Parsed Job Data
+
CV formatting preferences
```

Output:

- relevant professional summary;
- selected/reordered experience;
- selected/rephrased achievement bullets;
- reordered skills;
- optional project selection;
- missing-requirement note for user;
- CV version.

Absolute rule:

**No unsupported claims.**

The generator must not invent:

- experience;
- years;
- skills;
- metrics;
- companies;
- project responsibilities;
- technologies;
- certifications.

Add automated validation/evaluation for grounding.

## FR-007 — CV Review

User can:

- preview;
- edit;
- regenerate a section;
- compare versions;
- save version;
- mark final version;
- export PDF;
- identify exact version used in application.

V1 frontend may use simple text/edit controls.

## FR-008 — Application Tracker

Statuses:

```text
SAVED
READY_TO_APPLY
APPLYING
APPLIED
ASSESSMENT
INTERVIEW
FINAL_INTERVIEW
OFFER
REJECTED
WITHDRAWN
SKIPPED
```

User actions:

- mark applied;
- mark assessment;
- mark interview;
- mark final;
- mark rejected;
- mark offer;
- withdraw;
- skip.

## FR-009 — Event Log

Use event-based tracking.

Events:

```text
JOB_SAVED
JOB_UPDATED
JOB_PARSED
JOB_PARSE_CORRECTED

CV_GENERATED
CV_REGENERATED
CV_EDITED
CV_APPROVED
CV_EXPORTED

APPLICATION_STARTED
APPLICATION_SUBMITTED
ASSESSMENT_RECEIVED
INTERVIEW_RECEIVED
INTERVIEW_COMPLETED
FINAL_INTERVIEW
REJECTED
OFFER_RECEIVED
WITHDRAWN
SKIPPED
```

Every event stores:

```text
event_id
entity_id
event_type
timestamp
actor
metadata
```

The analytics layer should derive historical metrics from event data whenever possible.

## FR-010 — Dashboard

V1 dashboard requires:

### KPI summary
- saved;
- ready to apply;
- applied;
- assessment;
- interview;
- final;
- rejected;
- offer.

### Funnel
- saved → applied → assessment → interview → final → offer.

### Conversion
- applied/saved;
- assessment/applied;
- interview/applied;
- offer/interview;
- offer/applied.

### Backlog
- CV ready not applied;
- saved older than threshold;
- jobs missing CV;
- applications requiring action.

### Weekly/monthly trends
- jobs saved;
- jobs applied;
- interviews;
- offers;
- saved vs applied.

### Role analytics
- role category;
- saved count;
- applied count;
- interview count;
- conversion.

### Source analytics
- LinkedIn;
- JobStreet;
- Glints;
- Dealls;
- Kalibrr;
- company career site;
- others.

### Skill analytics
- top skills in captured jobs;
- skill trends;
- skill gaps vs career profile.

### Productivity
- median saved → CV ready;
- median saved → applied;
- applications/week;
- backlog size;
- estimated time saved if feasible.

Add an explicit note:

> Analytics describe the user's captured-job sample unless a market-wide collection source is explicitly available.

## FR-011 — Action Queue

Dashboard should not be passive.

Examples:

```text
12 jobs: CV ready but not applied
5 jobs: saved > 5 days
3 jobs: CV needs review
2 jobs: assessment pending
1 job: interview upcoming
```

Provide direct navigation from action item to job list.

---

# 7. Non-Functional Requirements

## NFR-001 — Simplicity

Early UI should be:

- fast;
- functional;
- consistent;
- low-friction;
- responsive.

Avoid spending large engineering time on animations, design systems, microinteractions, and advanced visual polish in V1.

## NFR-002 — Reliability

Core V1 workflows must fail gracefully.

A parser failure must not lose a job.

A CV generation failure must not lose stored job data.

A mobile share failure must provide a retry.

## NFR-003 — Observability

Every important workflow must produce logs/telemetry.

Capture:

- component;
- action;
- success/failure;
- latency;
- error type;
- version;
- relevant IDs.

## NFR-004 — Privacy

Treat all career, application, and user profile data as private.

- no plaintext credentials;
- environment-managed secrets;
- avoid storing site passwords;
- support user export/delete;
- minimize PII exposure;
- redact sensitive fields from logs;
- protect generated CV files.

## NFR-005 — Maintainability

Use modular boundaries so later automation can be added without rewriting V1.

---

# 8. Proposed High-Level Architecture

The AI agent must evaluate alternatives, but start from this conceptual architecture:

```text
                 ┌─────────────────────┐
                 │ Desktop Browser Ext │
                 └──────────┬──────────┘
                            │
                            │
┌─────────────────────┐     │
│ Mobile Share Target │─────┤
└─────────────────────┘     │
                            ▼
                     ┌─────────────┐
                     │ API Backend │
                     └──────┬──────┘
                            │
          ┌─────────────────┼─────────────────┐
          │                 │                 │
          ▼                 ▼                 ▼
     PostgreSQL        Object Storage      Job Queue
          │                                   │
          │                                   ▼
          │                           AI / Worker Layer
          │                         ┌────────┬─────────┐
          │                         │ Parser │ CV Gen  │
          │                         └────────┴─────────┘
          │
          ▼
     Web Dashboard
```

Preferred initial engineering direction:

- Backend API: **FastAPI (required)** with Python typing and Pydantic schemas
- Database: **PostgreSQL (required)**
- Web frontend: **SvelteKit + TypeScript + Tailwind CSS (required)**
- Browser extension: **TypeScript WebExtension** for Chrome/Edge; use Svelte components where UI is needed so the web and extension stack remain conceptually aligned
- Mobile: keep the main product UI responsive in SvelteKit; implement the smallest reliable mobile share-capture bridge needed for Android/iOS. Run an early feasibility spike comparing PWA Web Share Target versus a thin Capacitor/native share extension. Do not build a large independent mobile client in V1.
- Jobs/async: lightweight queue initially; avoid over-engineering
- Object storage: generated CV/PDF and optional raw assets
- LLM layer: provider-agnostic abstraction

The stack above is a product-owner decision and is **not open for substitution** unless there is a blocking technical reason. The engineering agent may propose libraries, deployment choices, background-job tooling, PDF tooling, and mobile share-bridge details, but must preserve SvelteKit + TypeScript + Tailwind CSS on the web frontend and FastAPI + PostgreSQL on the backend.

---

# 8A. V1 Capture Strategy — Generic First, Not Job-Board First

V1 must **not** be built specifically around LinkedIn, JobStreet, or another single job board. The product should support a common capture contract first.

Define a canonical capture object similar to:

```text
CaptureEnvelope
├── url
├── source_hint
├── page_title
├── raw_text?
├── selected_text?
├── shared_text?
├── captured_at
├── capture_method
└── metadata?
```

The backend must be able to accept incomplete captures.

Introduce capture completeness such as:

```text
CAPTURED_PARTIAL
CAPTURED_COMPLETE
NEEDS_ENRICHMENT
```

Examples:

- Desktop extension may provide URL + page title + visible JD text → `CAPTURED_COMPLETE`.
- Mobile share may only provide URL + shared title → `CAPTURED_PARTIAL`; save immediately and enrich later if technically possible.
- Paste-text fallback can turn a partial capture into complete data.

This prevents mobile limitations or protected pages from blocking the entire workflow.

Site-specific code should live behind extractor/adapter interfaces. Example conceptual boundary:

```text
GenericJobCapture
        │
        ├── GenericExtractor
        ├── LinkedInExtractor      (optional later)
        ├── JobStreetExtractor     (optional later)
        ├── GlintsExtractor        (optional later)
        └── ATS extractors         (later)
```

Do not implement deep LinkedIn/JobStreet automation in V1. A job saved from those sources must still be useful through generic capture, manual fallback, and raw-data preservation.

---

# 9. Suggested Repository Structure

```text
oscar-job-copilot/

├── apps/
│   ├── web/
│   ├── api/
│   ├── extension/
│   └── mobile/
│
├── packages/
│   ├── shared_types/
│   ├── ui/
│   └── schemas/
│
├── agents/
│   ├── job_parser/
│   ├── cv_generator/
│   ├── fit_scorer/
│   └── question_assistant/
│
├── domain/
│   ├── jobs/
│   ├── career/
│   ├── cv/
│   ├── applications/
│   └── analytics/
│
├── adapters/
│   └── future/
│
├── workers/
├── evals/
├── fixtures/
├── telemetry/
├── migrations/
├── tests/
└── docs/
```

Do not blindly use this structure if a better one is justified.

---

# 10. Core Data Model Requirements

Design a normalized schema.

Required concepts:

```text
users
career_profiles
career_experiences
career_projects
career_achievements
career_skills
application_profiles

jobs
job_raw_snapshots
job_parsed_data
job_skills
job_events

cv_versions
cv_generation_runs
cv_artifacts

applications
application_events
application_answers

sources
companies
role_categories
```

Important constraints:

- a Job can have multiple raw snapshots;
- a Job can have multiple CV versions;
- one CV version may be marked as submitted;
- Application references Job;
- Application references submitted CV version;
- status history is event-based;
- current status can be materialized for convenience;
- raw data should not be destructively overwritten.

---

# 11. CV Grounding Architecture

The AI agent must design a grounding mechanism.

Suggested flow:

```text
Career Fact Store
       ↓
Retrieve relevant facts
       ↓
LLM drafting
       ↓
Claim extraction
       ↓
Claim-to-fact verification
       ↓
Reject unsupported claim
       ↓
User preview
```

Possible implementation strategies:

- immutable career fact IDs passed into generation;
- each bullet maps to supporting fact IDs;
- validator checks output claims;
- numeric metric validator;
- forbidden new-technology detection;
- LLM-as-judge only as secondary control, not sole control;
- deterministic checks where possible.

Output metadata should ideally contain provenance.

Example:

```json
{
  "bullet": "Developed production scoring APIs using FastAPI.",
  "supporting_fact_ids": ["exp_12_fact_4", "exp_12_fact_7"]
}
```

---

# 12. Analytics Architecture

Analytics should be derived from transactional/event data.

V1 may query PostgreSQL directly.

Avoid premature warehouse complexity.

Required metric definitions must be documented.

Examples:

```text
Saved Count
= unique jobs with JOB_SAVED in period

Applied Count
= applications with APPLICATION_SUBMITTED in period

Interview Conversion
= jobs reaching INTERVIEW / jobs reaching APPLIED
```

Clarify:

- event-date cohort vs current-state metrics;
- application-date cohort;
- time-window semantics;
- duplicate job handling;
- withdrawn/skipped treatment.

---

# 13. Job Deduplication

V1 may use simple logic.

Potential keys:

- normalized source job ID;
- canonical URL;
- company + normalized title + location;
- fuzzy fallback.

Do not make sophisticated deduplication a V1 blocker.

Store potential duplicates and allow manual merge later.

---

# 14. Desktop Capture Design

Browser extension should prioritize:

- one-click save;
- minimal permissions;
- current tab only;
- **generic capture first**;
- source detection from domain/URL;
- optional source-specific extraction only when it materially improves reliability;
- generic visible-text fallback.

```text
User opens job
   ↓
Click Save
   ↓
extension collects:
  URL
  title
  visible relevant text
  source
   ↓
POST /jobs/capture
   ↓
show success
```

Do not implement automated browsing/search in V1.

---

# 15. Mobile Capture Design

The mobile capture requirement is essential.

Evaluate:

1. native share extension/share target;
2. Android intent target;
3. iOS share extension;
4. PWA limitations;
5. lightweight cross-platform wrapper.

Choose the simplest approach that reliably supports:

```text
Share URL/text → OSCAR Job Copilot → saved
```

Important: mobile share payloads may contain only a URL/title and may not expose the full job description. V1 must therefore **save partial captures immediately rather than pretending extraction succeeded**. The job can be enriched later from desktop, selected/shared text, or another permitted capture path.

Full mobile application parity is not required.

---

# 16. Parser Strategy

V1 must be **generic-first, source-aware, adapter-ready**. Do not make LinkedIn, JobStreet, or any single job board the architectural center of the product.

Preferred flow:

```text
CaptureEnvelope
(URL + title + source hint + raw/selected text if available)
        ↓
Generic normalization
        ↓
Source/domain recognition
        ↓
Generic visible-text extraction
        ↓
Optional source-specific extractor when available
        ↓
LLM structured extraction
```

The generic path must remain usable even when no site-specific adapter exists.

A source-specific extractor is an optimization, not a prerequisite.

Store parser version.

Fields may contain confidence.

Parser output must be editable.

Never block CV generation on parser failure.

---

# 17. Fit Score — P1

Do not make fit score the center of V1.

Recommended initial structure:

```text
Hard requirements
Technical match
Seniority
Domain
Location/work mode
Preferred requirements
```

Return explainable components, not only an opaque number.

---

# 18. Application Question Assistant — P1

Create a reusable answer store.

Canonical concepts:

```text
notice_period
salary_expectation
work_authorization
relocation
location
linkedin
github
portfolio
python_years
ml_years
deployment_experience
career_summary
reason_for_interest
```

Question matcher should detect semantic equivalents.

For unique questions:

```text
Job + Career Facts
        ↓
AI Draft
        ↓
Human Review
```

---

# 19. Autofill — P2

Autofill must not delay V1.

When implemented, start with low-risk fields:

- name;
- email;
- phone;
- location;
- LinkedIn;
- GitHub;
- education;
- CV upload.

Ambiguous or legal-sensitive questions remain human-reviewed.

---

# 20. ATS Automation — P3

Do not attempt universal website automation.

Build adapters incrementally based on real user usage.

Possible adapters:

```text
Greenhouse
Lever
Ashby
Workday
SmartRecruiters
Generic
```

Suggested interface:

```python
detect()
extract_fields()
map_profile()
fill_form()
upload_resume()
answer_questions()
detect_submission()
```

Every adapter must have:

- fixtures;
- unit tests;
- integration tests where feasible;
- telemetry;
- version;
- failure classification.

---

# 21. Progressive Autonomy Policy

Future automation should use capability-level confidence and reliability.

Conceptual policy:

```text
Very high reliability + low risk
→ AUTO

High reliability
→ AUTO + VERIFY

Medium reliability
→ HUMAN REVIEW

Low reliability / unknown
→ HUMAN REQUIRED
```

Do not use one global AUTO switch.

Maintain a capability matrix.

---

# 22. Failure Telemetry and AI-Assisted Development

The application should become easier to improve iteratively.

Store failures such as:

```json
{
  "component": "greenhouse_adapter",
  "version": "2.3.1",
  "action": "resume_upload",
  "result": "failed",
  "error_type": "ELEMENT_NOT_FOUND",
  "job_id": "..."
}
```

Future development loop:

```text
Production failure
       ↓
Telemetry
       ↓
Failure clustering
       ↓
Issue
       ↓
Codex/Claude investigates
       ↓
Patch
       ↓
Regression test
       ↓
Human review
       ↓
Merge
```

The AI coding agent may help write patches and tests.

Do not automatically deploy unreviewed code to production.

---

# 23. Product Priorities

## P0 — V1 blockers

- desktop capture
- mobile capture
- raw job storage
- job inbox
- master career profile
- tailored CV generation
- CV review
- PDF export
- CV versioning
- application tracking
- event history
- analytics dashboard

## P1

- parser improvement
- fit score
- question assistant
- better role taxonomy
- better skill taxonomy

## P2

- autofill
- browser application assistant
- submission detection
- productivity improvements

## P3

- ATS adapters
- semi-automated applications

## P4

- selective unattended application

## P5

- autonomous discovery
- adaptive career recommendations

---

# 24. V1 Non-Goals

Explicitly exclude:

- full autonomous applying;
- bypassing anti-bot protections;
- CAPTCHA solving;
- device fingerprint spoofing;
- proxy rotation for evasion;
- mass scraping protected platforms;
- perfect extraction accuracy;
- advanced recommendation model;
- enterprise-grade UI design system;
- complex multi-user RBAC;
- data warehouse;
- microservice proliferation.

---

# 25. Frontend Requirements

The frontend stack is fixed for V1:

- **SvelteKit**
- **TypeScript**
- **Tailwind CSS**

Frontend must be simple.

Suggested V1 screens:

1. Dashboard
2. Job Inbox
3. Job Detail
4. CV Review
5. Career Profile
6. Analytics
7. Settings

Design principles:

- functionality over visual polish;
- do not build a custom design system in V1;
- use a small reusable component layer only where it reduces duplication;
- tables are acceptable;
- simple cards are acceptable;
- plain forms are acceptable;
- prioritize keyboard efficiency;
- minimal clicks;
- responsive;
- reusable components;
- no premature animation/polish.

---

# 26. Suggested API Surface

The engineering agent must refine this.

Possible endpoints:

```text
POST   /jobs/capture
GET    /jobs
GET    /jobs/{id}
PATCH  /jobs/{id}

POST   /jobs/{id}/parse
POST   /jobs/{id}/generate-cv

GET    /jobs/{id}/cv-versions
GET    /cv/{id}
PATCH  /cv/{id}
POST   /cv/{id}/export

POST   /applications
PATCH  /applications/{id}
POST   /applications/{id}/events

GET    /dashboard
GET    /analytics/funnel
GET    /analytics/trends
GET    /analytics/sources
GET    /analytics/roles
GET    /analytics/skills
GET    /analytics/productivity

GET    /career-profile
PATCH  /career-profile
```

---

# 27. Background Jobs

Potential asynchronous tasks:

- parser;
- CV generation;
- PDF generation;
- skill extraction;
- fit scoring;
- analytics refresh;
- future site adapters.

Do not require a complex distributed queue if a simpler background worker is sufficient in V1.

---

# 28. Testing Requirements

At minimum:

## Unit
- parsers;
- normalization;
- status transitions;
- analytics calculations;
- CV claim validation;
- event creation.

## Integration
- job capture API;
- career profile → CV generation;
- application status flow;
- PDF generation;
- dashboard query correctness.

## Fixtures
Maintain real-world-like sanitized fixtures for:

- LinkedIn job text;
- JobStreet job text;
- Glints;
- Dealls;
- company career pages;
- malformed pages;
- short job descriptions;
- duplicate jobs.

## Evals
- job extraction;
- skill extraction;
- must-have vs nice-to-have;
- CV grounding;
- CV relevance.

---

# 29. V1 Acceptance Criteria

V1 release is accepted only when:

1. User can save jobs from desktop with low friction.
2. User can share jobs from mobile into the system.
3. Raw job data is preserved.
4. Job can still be used if parser fails.
5. Career profile is editable and used as CV source of truth.
6. CV can be generated from raw JD.
7. CV generator has grounding validation.
8. CV can be edited and exported as PDF.
9. CV versions are retained.
10. Exact submitted CV can be linked to application.
11. User can track application stages.
12. Event timestamps are retained.
13. Dashboard funnel is correct.
14. Dashboard shows backlog.
15. Analytics show role/source/skill trends.
16. System is used on at least ~50 real jobs during stabilization.
17. At least ~25 real applications are tracked.
18. No known fabricated claim remains in final submitted CVs.
19. Median tailored-CV workflow approaches <2 minutes.
20. Human active application time trends toward 3–5 minutes.

---

# 30. Required Documentation to Produce Before Coding

Before implementation, the AI engineering agent must produce the following design pack. Keep documents **decision-oriented and concise enough to remain maintainable**; do not generate long ceremonial documents that repeat this master spec.


```text
docs/
├── 01_PRD.md
├── 02_USER_JOURNEYS.md
├── 03_SYSTEM_ARCHITECTURE.md
├── 04_DATA_MODEL.md
├── 05_API_DESIGN.md
├── 06_AI_LLM_DESIGN.md
├── 07_CV_GROUNDING_AND_EVALS.md
├── 08_BROWSER_EXTENSION_DESIGN.md
├── 09_MOBILE_CAPTURE_DESIGN.md
├── 10_ANALYTICS_DEFINITIONS.md
├── 11_SECURITY_PRIVACY.md
├── 12_TEST_STRATEGY.md
├── 13_OBSERVABILITY.md
├── 14_DEPLOYMENT_PLAN.md
├── 15_ROADMAP_AND_MILESTONES.md
├── 16_RISK_REGISTER.md
└── 17_DECISION_LOG.md
```

Each document must be consistent with the others.

---

# 31. PRD Requirements

`01_PRD.md` must contain:

- problem statement;
- product vision;
- target user;
- jobs-to-be-done;
- goals;
- non-goals;
- scope;
- functional requirements;
- non-functional requirements;
- user stories;
- acceptance criteria;
- product metrics;
- edge cases;
- V1 definition of done;
- future roadmap.

---

# 32. System Architecture Requirements

`03_SYSTEM_ARCHITECTURE.md` must include:

- component diagram;
- request flows;
- background jobs;
- browser extension interaction;
- mobile capture flow;
- storage;
- LLM integration;
- auth;
- logging;
- failure handling;
- future ATS adapter boundary;
- technology choices and trade-offs.

Do not introduce microservices without a clear need.

Prefer a modular monolith for V1 unless evidence supports another approach.

---

# 33. Data Model Requirements

`04_DATA_MODEL.md` must include:

- ERD;
- tables/entities;
- PK/FK;
- indexes;
- enums;
- audit/event approach;
- status state machine;
- raw snapshot versioning;
- CV versioning;
- duplicate handling;
- migration strategy.

---

# 34. AI / LLM Design Requirements

`06_AI_LLM_DESIGN.md` must define:

- job parser;
- skill extraction;
- role classification;
- CV generation;
- fit scoring;
- question assistant;
- provider abstraction;
- structured output;
- fallback behavior;
- prompt versioning;
- model versioning;
- cost controls;
- caching;
- retry;
- latency;
- evaluation.

---

# 35. CV Grounding & Eval Requirements

`07_CV_GROUNDING_AND_EVALS.md` must be treated as critical.

Define:

- career fact store;
- retrieval;
- fact provenance;
- claim verification;
- unsupported-claim rejection;
- metric verification;
- evaluation dataset;
- regression tests;
- human review;
- factuality KPIs.

---

# 36. Analytics Definitions

`10_ANALYTICS_DEFINITIONS.md` must explicitly define formulas.

Examples:

```text
Saved → Applied Conversion
= unique jobs with APPLICATION_SUBMITTED
  /
  unique jobs with JOB_SAVED

Applied → Interview Conversion
= applications reaching INTERVIEW
  /
  applications reaching APPLIED
```

Define:

- time windows;
- cohort logic;
- current-state logic;
- duplicates;
- withdrawn;
- skipped;
- rejected;
- multi-interview cases.

---

# 37. Project Management Plan

`15_ROADMAP_AND_MILESTONES.md` must propose milestones.

Suggested structure:

## Milestone 0 — Foundation
- repository
- CI
- environment
- DB
- auth
- basic web shell

## Milestone 1 — Capture
- desktop extension
- mobile share
- job inbox
- raw snapshots

## Milestone 2 — Career Profile
- structured facts
- edit UI
- import/manual entry

## Milestone 3 — CV
- generation
- grounding
- review
- PDF
- versioning

## Milestone 4 — Tracking
- applications
- events
- status history
- timeline

## Milestone 5 — Analytics
- dashboard
- funnel
- backlog
- role/source/skill trends

## Milestone 6 — Stabilization
- real usage
- bugs
- evals
- performance
- definition-of-done measurement

Only after this milestone begin V2.

---

# 38. Implementation Method

Use vertical slices.

Bad approach:

```text
Build all database
then all backend
then all frontend
then all AI
```

Preferred:

```text
Vertical Slice 1:
Save one job end-to-end

Vertical Slice 2:
Show job in inbox

Vertical Slice 3:
Generate one CV

Vertical Slice 4:
Track one application

Vertical Slice 5:
Show one funnel metric
```

Each slice should be usable and testable.

---

# 39. Decision-Making Rules for AI Coding Agent

When uncertain:

1. prefer the simplest architecture satisfying V1;
2. preserve extensibility through clean interfaces;
3. avoid speculative infrastructure;
4. prioritize user workflow speed;
5. never make parser perfection a blocker;
6. never make autofill a blocker;
7. never require autonomous application for V1;
8. treat dashboard/analytics as V1 core;
9. preserve raw data;
10. preserve event history;
11. make CV grounding non-negotiable;
12. document assumptions;
13. preserve the fixed stack: SvelteKit + TypeScript + Tailwind CSS, FastAPI, PostgreSQL;
14. prefer generic-first capture over a LinkedIn-first or JobStreet-first architecture;
15. treat site-specific extractors as replaceable adapters, never as core domain logic.

---

# 40. What the AI Agent Must Do First

Before writing production code:

1. read this entire specification;
2. identify ambiguities;
3. produce a concise assumption list;
4. create the documentation set listed above;
5. propose the V1 architecture;
6. propose the data model;
7. propose a milestone plan;
8. propose a risk register;
9. propose test/eval strategy;
10. request human approval for the architecture and V1 scope.

Do not skip design and immediately scaffold a large application.

---

# 41. Initial Product Risk Register

| Risk | Impact | Initial Mitigation |
|---|---|---|
| Mobile capture unreliable | High | Test share flows early |
| Browser DOM changes | Medium | Generic text fallback |
| Parser inaccurate | Low-Medium | Raw JD + quick correction |
| LLM fabricates CV claims | Critical | Grounding + validation + user review |
| PDF output inconsistent | Medium | Stable template + rendering tests |
| User forgets status updates | Medium | Action queue; later detection/reminders |
| Analytics misleading | High | Explicit metric definitions |
| Duplicate jobs | Medium | Simple dedupe + manual merge |
| Scope creep | High | Freeze P0 |
| UI polish consumes time | Medium | Functional-first design |
| Sensitive data leakage | Critical | Privacy controls + log redaction |
| Automation violates site boundaries | High | Human fallback; permitted flows only |

---

# 42. Final Engineering Philosophy

This product is not initially an "autonomous job bot".

It is a **personal job-search operating system**.

The first product win is:

```text
Find job
   ↓
Save instantly
   ↓
Tailored CV quickly
   ↓
Apply manually
   ↓
Track automatically/manual-one-click
   ↓
Understand job-search data
```

Only after this loop is reliable should the system automate more.

Every future automation should be justified by actual usage data and measured reduction in human effort.

The project should become more autonomous **iteratively**, not ideologically.

---

# 43. Deliverable Request to the AI Agent

Create the documentation and plan first.

Then present:

1. proposed stack;
2. architecture diagram;
3. database schema;
4. V1 user flows;
5. milestone breakdown;
6. implementation sequence;
7. test/eval plan;
8. risks;
9. unresolved decisions;
10. explicit list of what is intentionally postponed.

Wait for product-owner approval before major implementation.
