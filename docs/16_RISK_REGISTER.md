# 16 — Risk Register

Master spec §41's initial register, reviewed and extended with **detection signals** (how we find out) and **triggers** (what forces action). A risk with no detection signal is a hope.

Severity = impact × likelihood, judged for this specific single-user product.

---

## Critical

| ID | Risk | Mitigation | Detection signal | Trigger for action |
|---|---|---|---|---|
| **R-01** | **LLM fabricates CV claims** — a fluent, plausible bullet describing something Oscar never did, sent to a real employer | Deterministic verifier V1–V6 built and tested before the generator is trusted; fact-ID provenance; verified-metric rule; secondary judge; human review as final gate; adversarial eval suite ([07_CV_GROUNDING_AND_EVALS](07_CV_GROUNDING_AND_EVALS.md)) | `grounding_report.claims_rejected` per run; eval `fabrication_rate` and `verifier_recall` | **Any** fabrication surviving into an exported CV halts feature work until fixed. Verifier recall < 100% blocks adopting a prompt/model change |
| **R-02** | **Sensitive data leakage** — career dossier, salary expectations, or API keys exposed | Secrets only in git-ignored `.env`; gitleaks in CI; structural log redaction with a test; constant-time key comparison; Postgres bound to loopback; explicit no-plaintext-site-credentials rule ([11_SECURITY_PRIVACY](11_SECURITY_PRIVACY.md)) | gitleaks CI result; redaction unit test; manual review of `var/logs` during M6 | Any secret committed → rotate immediately (revert is insufficient). Any PII found in logs → fix the filter before shipping |
| **R-13** | **Loss of the career fact store** *(new — absent from the master spec)* — hand-curated over hours, irreplaceable; a disk failure or bad migration destroys the product's foundation | Nightly `pg_dump` + storage mirror off-machine; 14 daily/8 weekly retention; **quarterly tested restore**; `GET /export` as a format-independent second copy; migrations tested up *and* down in CI ([14_DEPLOYMENT_PLAN](14_DEPLOYMENT_PLAN.md) §5) | Backup job success/failure; the quarterly restore drill | A failed or untested restore is treated as "no backup exists" |

R-13 is added because the master spec's register covers correctness and privacy but never data durability — and for a personal tool on one laptop, that is the likeliest catastrophic loss.

## High

| ID | Risk | Mitigation | Detection signal | Trigger |
|---|---|---|---|---|
| **R-03** | **Mobile capture unreliable or unreachable** — P0 requirement; a laptop-hosted API is not reachable from mobile data at all ([09_MOBILE_CAPTURE_DESIGN](09_MOBILE_CAPTURE_DESIGN.md) §2) | Timeboxed M1 spike on the real phone before committing; share-shortcut path as zero-build fallback; local retry queue with idempotency keys; honest "queued, not saved" state | Captures attempted vs. saved during M1/M6; user reports of "I shared it but it's not there" | If the spike shows no reliable path, escalate OPEN-1 to hosting (option D) with its privacy consequences accepted explicitly |
| **R-04** | **Analytics misleading** — a wrong funnel silently misdirects the whole job-search strategy | Every formula defined once in [10_ANALYTICS_DEFINITIONS](10_ANALYTICS_DEFINITIONS.md) with explicit cohort/duplicate/skipped/withdrawn semantics; single implementation module; hand-counted fixture dataset covering awkward cases; sample-not-market disclosure in the UI | Fixture reconciliation test; action-queue count == linked-list length test | Any mismatch between a displayed count and the set it links to is a release blocker |
| **R-05** | **Scope creep** — a full autonomous job bot is a far more attractive project than a reliable capture-and-track tool | P0 frozen in [01_PRD](01_PRD.md) §7; non-goals enumerated as *deliberate exclusions*; V2 chosen only from M6 data; Decision Rules 5–7 | Any PR touching autofill/ATS/autonomy before M6 | Reject and defer; record the idea, not the code |
| **R-14** | **Career profile data entry never happens properly** *(new)* — M2's real cost is 1–2 hours of careful tagging; a rushed profile silently caps grounding, retrieval, and skill-gap quality forever | M2 exit criteria requires ≥ 20 tagged achievements with explicit metric verification; called out as critical-path in [15_ROADMAP_AND_MILESTONES](15_ROADMAP_AND_MILESTONES.md) | `fact_recall` in the eval suite; count of achievements with empty tag arrays | Low fact recall is treated as a *data* problem first, not a retrieval-algorithm problem |

R-14 is added because it is the most likely quiet failure: everything downstream will appear to work while producing mediocre CVs, and the cause will look like a model problem.

## Medium

| ID | Risk | Mitigation | Detection signal |
|---|---|---|---|
| **R-06** | Browser DOM changes break extraction | Generic-first extraction with a 4-branch fallback chain; `metadata.extractor` records which branch fired; HTML fixtures in tests; site-specific extractors are optional add-ons, never load-bearing ([08_BROWSER_EXTENSION_DESIGN](08_BROWSER_EXTENSION_DESIGN.md) §4) | Distribution of `metadata.extractor` values; `raw_text_length` trending down |
| **R-07** | PDF output inconsistent | One stable template; rendering test asserting a byte-stable PDF for a fixture CV; export decoupled from generation so failures are retryable | `pdf_export` failure rate in logs |
| **R-08** | User forgets status updates, breaking the funnel | Action queue surfaces stale applications (`applications_needing_action`, no event in 7 days) with direct links; one-click updates; `occurred_at` is client-settable so late entry doesn't distort the timeline | Count of applications with no event in > 14 days |
| **R-09** | Duplicate jobs pollute counts | Simple dedupe key; duplicates flagged not blocked; every analytics query excludes `duplicate_of_job_id IS NOT NULL` | Ratio of flagged duplicates; manual spot-check |
| **R-10** | UI polish consumes time | Functional-first mandate (NFR-001); no design system; tables and plain forms explicitly acceptable | Time spent on styling vs. features |
| **R-15** | *(new)* Prompt caching silently breaks, quietly tripling LLM cost | Deterministic fact serialisation (`sort_keys`); no timestamps/UUIDs in system blocks; acceptance test asserting `cache_read_tokens > 0` on the 2nd generation of a session | `cache_read_tokens` in logs ([13_OBSERVABILITY](13_OBSERVABILITY.md) §5) |
| **R-16** | *(new)* Background tasks lost on restart — in-process `BackgroundTasks` have no durability or retry history | All tasks idempotent and re-runnable from the UI; parse and generation are both explicitly retryable; queue decision deferred but tracked (OPEN-3) | User-visible "still not parsed" states; CV generation p95 |

## Low–Medium

| ID | Risk | Mitigation | Detection signal |
|---|---|---|---|
| **R-11** | Parser inaccurate | Raw JD always preserved and always sufficient for CV generation; correction UI; `parser_version` stored per run; parser explicitly P1 and non-blocking | Parser correction rate (`JOB_PARSE_CORRECTED` events / parses) |
| **R-12** | Automation violates site boundaries | No autofill, no automated browsing, no anti-bot circumvention in V1; `activeTab`-only permissions; human fallback preserved by design; P3 adapters require explicit review before existing | Code review; permissions manifest diff |
| **R-17** | *(new)* Laptop-asleep dependency makes mobile capture unavailable exactly when useful (commuting) | Accepted limitation of OPEN-1 option B; local retry queue so nothing is lost; measured during M6 | Count of queued-but-unsent captures |

---

## Risks Consciously Accepted

| Accepted risk | Why | Revisit when |
|---|---|---|
| Single machine, single user, no HA | Personal tool; downtime costs minutes, not money | never, unless hosted |
| Career facts and JD text sent to a third-party LLM provider | Unavoidable for the product's core value; scoped by a tested field projection that excludes contact details, salary, and private answers ([11_SECURITY_PRIVACY](11_SECURITY_PRIVACY.md) §4) | if provider retention terms change |
| Keyword/tag retrieval misses semantic matches | Explainable, no extra infrastructure, adequate for a small corpus | if eval `fact_recall` < 80% (OPEN-4) |
| No end-to-end browser tests | Simple, fast-changing UI; API integration tests cover the failures that matter | if UI regressions start reaching real use |
| Static shared API key rather than real auth | Loopback/private-mesh only; not a user-identity system | immediately, if OPEN-1 resolves to public exposure |

## Review Cadence

Reviewed at each milestone gate and weekly during M6. New risks are added with a detection signal, or they are not added — a risk nobody can observe cannot be managed.
