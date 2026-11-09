# MVP bug audit — 4 November 2026

Scope: local working tree, extension build 0.1.6. The original audit below is
retained as historical reproduction evidence. All 13 findings have now been
repaired and checked with permanent regressions. The updated pilot was rebuilt
and restarted on Windows; the API reports local/ok with a healthy database, and
the production dashboard responds on port 5173. This is bounded verification,
not a guarantee that future inputs or provider changes cannot reveal another bug.

Tests use synthetic data, disposable PostgreSQL databases and fake model
providers. No paid model calls were made during this repair pass. Existing
pilot data and documents were preserved; private configuration, profile records,
browser captures, PDFs and backups remain excluded from version control.

## Repairs and final verification

| Finding | Repair | Permanent coverage |
| --- | --- | --- |
| 1. Configuration precedence | Every Compose subprocess receives the validated file-owned environment; unrelated system/proxy variables remain available. | `test_pilot_configuration.py` |
| 2. Submitted CV disagreement | Recorded application CV is authoritative; incompatible marker changes return 409, repeated matching changes are idempotent. | `test_workflow_api.py`, `test_workflow_concurrency.py` |
| 3. Approval rewinds applied state | Lock and refresh the job before applying state transitions. | `test_workflow_concurrency.py` |
| 4. Partial generation commit | Successful CV, run and event commit together; event failure rolls back all three. | `test_workflow_concurrency.py` |
| 5. Empty/wrong effective JD | Select snapshots by server ingestion ID; reject empty/short corrections; generation reads the corrected snapshot. | `test_jobs_mvp_regressions.py` |
| 6. Complete JD cannot be corrected | Job Detail accepts an append-only correction and retains earlier descriptions. | `scripts/web/test-job-workflow.mjs` |
| 7. Dashboard filters lost | Forward every supported queue filter, including incomplete descriptions and duplicate exclusion. | API queue/link regressions and web HTTP checks |
| 8. Pagination loses filters | Preserve filters in next-page links and GET forms; reset cursor when filters change. | Web HTTP checks |
| 9. Missing application timeline | Authenticated merged timeline includes every historical application's events with deterministic ordering. | Workflow API and web HTTP checks |
| 10. Duplicate concurrent applications | Serialize the state transition; one succeeds and the competing request returns typed 409. | `test_workflow_concurrency.py` |
| 11. CV version allocation collision | All CV writers use the same short job lock; provider calls happen before taking it. | `test_workflow_concurrency.py` |
| 12. Stale helper PID | Recover positively stale ownership records without signalling unrelated processes; serialize start/stop and publish state atomically. | `test_windows_keepalive.py`, `test_windows_launcher.py` |
| 13. Invalid inbox parameters | Validate cursor structure/range, age, page size and metadata lengths before database writes. | `test_jobs_mvp_regressions.py` |

Additional defects found during repair were also corrected:

- Concurrent capture retries now preserve idempotency and shared source/company
  records; deliberate repeated captures retain duplicate markers.
- Dashboard queue links and counts agree on URL-only captures, duplicates,
  actual CV existence and server-side save age. Skipping an approved job removes
  it from ready counts; unskipping restores its readiness.
- Inbox labels distinguish description, duplicate and follow-up filters.
- Windows PowerShell 5.1 atomic replacement uses a null backup filename correctly;
  configuration encoding and ACLs are preserved. Startup checks actual Windows
  API/dashboard connectivity before reporting success.

Final checks on 4 November 2026:

- API: **433 passed, 9 Windows-only tests skipped on Linux**. Those native Windows
  checks passed separately: **9/9, no skips**. The standalone Linux helper suite
  also passed **4/4, no skips**. Their workflow is
  `.github/workflows/windows-pilot.yml`; hosted execution awaits a push.
  Ruff and Mypy pass. All API database tests use a disposable database, not the pilot.
- Web: Svelte reports **0 errors / 0 warnings**, production build passes,
  and **12 production-server HTTP cases** pass.
- Extension 0.1.6: TypeScript/configuration checks, **51 LinkedIn + 40 Jobstreet
  extraction cases**, and **24 installed-extension Chromium checks** pass.
  All four shipped JavaScript bundles byte-match fresh in-memory builds of the
  current source. The Docker runner uses synthetic provider pages, a disposable
  profile, real injection/messaging and a native `activeTab` grant; no host port
  8000, personal browser profile, credentials or live provider is used. Its test
  containers were removed successfully.
- Browser: **6/6 desktop and Pixel 7 Chromium scenarios pass** on a production
  web build and real API/PostgreSQL with a simulated provider. They cover capture,
  profile, generation, review/approval, PDF download, byte-identical re-export,
  application CV linkage, interview and analytics. Two PDFs and six screenshots
  are retained privately under `var/logs/browser-workflow-20261104102444-69985`.
  The isolated runner publishes no host ports and removes its owned containers.
- Normal pilot: private full backup completed and restored to a disposable
  database successfully; Windows stop/start completed; database/document
  fingerprints remained identical across the upgrade and restart.
- Public source and build files were compared against configured private
  credentials without printing their values; no matches were found.

Re-run the web regression after building with
`node scripts/web/test-job-workflow.mjs`; run the isolated full browser flow with
`bash scripts/web/test-browser-docker.sh`. See `scripts/extension/README.md` for
the separately isolated installed-extension regressions.

## Acceptance still requiring the owner's environment/data

- Career dates have no year-only precision field. PDF dates display month/year;
  imports must not invent months when only a year is known. Optional dates can
  be omitted with the original labels retained privately; employment requiring
  an unknown start month needs a precise source or future precision support.
- Jobstreet direct and selected-search captures passed in the owner's Edge
  during the earlier session. LinkedIn 0.1.6 passes synthetic Chromium cases and
  extraction of the privately saved real DOM, but final live Edge capture remains
  unverified: Computer Use stopped automatically because it could not establish
  the active browser URL for its policy checks. This is not a passing live test.
  A fresh connection inventory on 5 November found no browser provider and
  reported `The browser access host is unavailable`; no native browser input
  was sent during that check.
- The local real-profile gap was closed on **5 November 2026** after explicit
  permission for professional-data processing through OpenAI. Source-backed
  facts were imported, one CV was generated through the production dashboard,
  reviewed, approved, exported/downloaded and verified byte-identical after
  re-export and a Windows/Docker restart. Backup restoration also passed with
  the real profile/PDF. See `22_REAL_PROFILE_ACCEPTANCE.md` for counts, the safely
  rejected skill, provider usage and limits. No profile contents are committed.
- The cause of the earlier WSL shutdown is still unknown. Stale ownership
  recovery and a successful stop/start do not establish that cause.

## Original audit, before repairs

Priority: P1 should be addressed before closing MVP acceptance; P2 affects
reliability or usability; P3 concerns malformed request handling. These priorities
describe the personal pilot, not a general security severity classification.

## P1 — acceptance blockers

### 1. Compose can use different configuration from the values validated

Location: `scripts/pilot.py:201–228`, `compose.pilot.yml:23–28,52–53`.

The helper validates values read from the selected environment file, then starts
Compose with the inherited shell environment. Compose gives shell values higher
precedence. A synthetic `docker compose config` probe, without starting any
containers, proved that inherited values override the validated mode, database
URL and application key. In the fixture, a provider-formatted sentinel key could
become the application credential despite file validation.

Impact: the effective mode/database/key can differ from the configuration the
launcher checked. This did not demonstrate that the current pilot has such an
override. Validate the effective values and pass a consistent environment to all
Compose subprocesses.

### 2. Submitted-CV badge and application record can disagree

Location: `apps/api/src/oscar_api/modules/cv/service.py:207`,
`apps/web/src/routes/cv/[id]/+page.svelte:191`.

Reproduction: create an application using CV1, then mark CV2 as submitted.
`Application.submitted_cv_version_id` remains CV1 while `is_submitted` moves to
CV2. The interface can therefore tell two different stories about the CV sent.
Submission changes need one consistent application/version update.

### 3. Concurrent CV approval can rewind Applied status

Location: `apps/api/src/oscar_api/modules/cv/service.py:132–133`.

Two-session reproduction: pause approval after it reads SAVED; submit the
application in another session; resume approval. The application remains stored,
but the job changes from APPLIED to READY_TO_APPLY. Existing regressions test
sequential actions. Use an atomic conditional update or a refreshed row lock.

### 4. CV generation commits before its event is saved

Location: `apps/api/src/oscar_api/modules/cv/generator.py:135,260–268`.

Injecting a failure while inserting CV_GENERATED produced an exception while a
separate session found one CV, a generation run marked succeeded, and zero
CV_GENERATED events. `_record_run` commits the version/run before the later event.
Version, successful run and event need one transaction, so a failed response does
not leave an apparently successful but incompletely recorded generation.

## P2 — reliability and workflow defects

### 5. Complete status can disagree with the JD used by generation

Locations: `apps/api/src/oscar_api/modules/jobs/models.py:160`,
`apps/api/src/oscar_api/modules/jobs/service.py:235–282`,
`apps/api/src/oscar_api/modules/cv/generator.py:148`.

Two independent synthetic reproductions:

- Capture a URL-only snapshot timestamped tomorrow, then enrich with a full JD
  timestamped now. Status becomes COMPLETE, but `/raw` remains empty because
  snapshots are selected by client-supplied time. Generate returns 422.
- Start with a complete JD, then POST an enrichment with null or empty text.
  The API accepts it with 201, keeps COMPLETE, and selects the empty snapshot.
  Generate returns 422 because no JD is available.

The original snapshot remains stored; it is not deleted. Validate enrichment
content and make effective-snapshot selection and completeness agree. Add a
deterministic ordering policy for equal timestamps as well.

### 6. A COMPLETE JD cannot be corrected through Job Detail

Location: `apps/web/src/routes/jobs/[id]/+page.svelte:73`.

The enrichment form is shown only for partial/incomplete captures. A historically
contaminated JD marked COMPLETE has no description-correction path in the page,
although the API supports append-only enrichment. Allow a new corrected snapshot
while retaining the original.

### 7. Dashboard action filters are dropped by the inbox loader

Location: `apps/web/src/routes/jobs/+page.server.ts:6`.

The actual loader, transpiled and called with a mocked API function, drops
`missing_cv`, `needs_action`, `completeness` and `older_than`. For example,
`missing_cv=1` forwards plain `/jobs`. Dashboard counts can link to an unrelated,
unfiltered list. Forward and validate the supported action-queue parameters.

### 8. Next page drops active inbox filters

Location: `apps/web/src/routes/jobs/+page.svelte:194`.

The generated href contains only `?cursor=...`. Resolving it against a filtered
URL removes status, source and text-search parameters. Preserve filters while
replacing the cursor.

### 9. Job Detail timeline omits application/interview history

Locations: `apps/api/src/oscar_api/modules/jobs/router.py:74`,
`apps/web/src/routes/jobs/[id]/+page.svelte:250`.

After applying and recording an interview, application events exist, but Job
Detail returns only JobEvent records. Its timeline omits APPLICATION_SUBMITTED
and INTERVIEW_RECEIVED. Read the merged timeline or explicitly combine both
event streams.

### 10. Concurrent Mark as Applied requests create duplicate applications

Location: `apps/api/src/oscar_api/modules/applications/service.py:35`.

Two sessions synchronized after reading SAVED both created successful application
rows for the same job. This was a deterministic service-level overlap probe,
not a native-browser double-click test. Serialize the state change and provide
retry/idempotency behavior appropriate to a deliberate application attempt.

### 11. Concurrent CV edits collide on version numbers

Location: `apps/api/src/oscar_api/modules/cv/service.py:47,59,74`.

Synchronizing two edits after their version-number SELECT produced one v2 and
one uncaught IntegrityError (SQLSTATE 23505), which becomes an HTTP 500. Serialize
allocation per job while retaining the database unique constraint. Generation
has the same allocation pattern at `generator.py:71`, but its version-allocation
race was not separately exercised in this audit.

### 12. A reused PID can prevent Windows/WSL launcher recovery

Location: `scripts/windows/hold-wsl.py:72–79`.

An isolated temporary-state fixture pointed an old helper record at an unrelated
live process. Ownership comparison was false, but startup still returned exit 2
merely because the old PID existed. After PID reuse, the launcher can remain
blocked until stale state is repaired. Distinguish an active matching helper
from a stale record without terminating an unrelated process.

This does not establish why Ubuntu stopped during the earlier session. Current
helper ownership checks matched when audited.

## P3 — malformed request handling

### 13. Invalid inbox parameters produce server errors

Location: `apps/api/src/oscar_api/modules/jobs/router.py:100–117`,
`apps/api/src/oscar_api/modules/jobs/service.py:288–289`.

Synthetic ASGI requests `cursor=not-a-cursor` and `older_than=banana` returned 500,
instead of a validation response. Limits of zero and minus one were also accepted
and returned an empty page. Validate cursor encoding, date-filter syntax and
positive pagination bounds.

## Items not classified as newly proven bugs

- The root cause of the earlier WSL shutdown remains unknown.
- A historical PDF that still existed remained byte-identical after fact deletion.
  Regeneration after losing the artifact returned 422 under the documented
  current-fact validation policy; this is a recovery limitation, not another new
  defect established here.
- LinkedIn 0.1.6 still needs final native-Edge capture acceptance. Its synthetic
  browser suite and extraction of the privately saved real DOM passed, but these
  are different forms of evidence.
- Empty local career facts and absent local CV/PDF records are onboarding and
  acceptance gaps, not proof of another generator bug.

The repair status and verification limits above supersede these historical
recommendations. Keep the regression suites green when extending the MVP.
