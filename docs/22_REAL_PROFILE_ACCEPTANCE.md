# Real-profile acceptance and reference PDF template

On 3 November 2026, the owner authorized using an uploaded CV together with the
previously supplied LinkedIn profile for real-provider testing. Personal profile
records, PDFs, database dumps and full generation payloads remain private and are
not committed to this public repository.

## Verified sample

The private local pilot imported 6 experiences, 7 projects, 29 career facts,
25 skills, 2 education records and 4 selected credentials through the application's
API. Three current public detail pages were captured through the supported
paste-text contract:

- [Sagara Data Scientist](https://sagaratech.com/careers/jobs/data-scientist-5m3n/)
- [Sagara Data Engineer](https://sagaratech.com/careers/jobs/data-engineer-2o6r/)
- [Metrodata Data Scientist, Kalibrr](https://kalibrr.id/c/metrodata/jobs/273252/data-scientist-4)

The normal provider, `gpt-6-luna` with `cv_generator/v3`, generated all three
versions. The final sample used 15,678 input and 1,585 output tokens, with request
latencies of 12,750 / 11,973 / 13,468 ms. There were 55 claim/skill checks and no
rejections in these final outputs. Additional calls were made during diagnosis;
the token counts above describe only the final three-generation sample.

A production web build was used to click Generate CV for one vacancy. All three
versions were reviewed/exported/downloaded in desktop Chromium and Pixel 7
emulation. Source statement matching, source-parent association, contact and
education snapshots, rejection of unauthorized requests, duplicate capture,
approval gating and stable re-export bytes were checked. After final visual
alignment corrections, unchanged snapshots were saved as new versions and
approved/exported/downloaded again through the API, with no extra model requests.
The exported PDFs are selectable text, one A4 page each for this selected sample.

A closed Jobstreet URL was also captured without a description. Generation was
correctly blocked until a full description is supplied. A search listing alone
was not treated as evidence that the vacancy remained open.

Local verification: 270 API tests on PostgreSQL; migrations up/down/up; Ruff,
Mypy, Svelte checks and production web build. Public CI uses synthetic data;
personal career records and API credentials must never be uploaded as CI artifacts.
The changed prompt also passed all four real-provider synthetic regression cases
(role fit, metric inflation, unsupported technology and JD injection); see the
[v3 fixture results](../evals/cv_grounding/results/2026-11-03_gpt-6-luna_v3.json).

## Changes prompted by real data

- The PDF follows the owner's reference style: single-column A4, prominent name,
  contact row, section rules, company heading and right-aligned month/year dates,
  with left-aligned text bullets. It is a fixed code template, not an arbitrary
  PDF-to-template importer or a pixel-exact copy of the uploaded document.
- Owner-entered education, credentials and location are frozen with each CV,
  displayed in review and included in export. Updates create another version.
- The model selects statements; their source records determine role/project
  placement. This fixes confusion between concurrent roles at one employer
  without rewriting claims or weakening the grounding verifier.
- Education, skills and dated roles are supplied to the model as metadata for
  gap assessment. Contact details are excluded from that model context.

## Limits and remaining review

The model's gap suggestions are less reliable than deterministic claim checking.
The sample still suggested NumPy or R/Scala as review items even where the
vacancy accepted a known alternative. Degree equivalence and the duration of
related engineering work also require judgment. The UI therefore labels these
items **Requirements to check**, not automatic disqualification. CV claims still
must pass the existing fact, parent, metric and skill checks.

This proves a real profile-to-PDF flow for the three tested vacancies. It does
not establish direct extension capture on Jobstreet/Kalibrr, physical-phone/PWA
share compatibility, employer ATS acceptance, successful job applications or M6
usage/time targets. No applications were sent. Vacancy status may change.

The owner authorized this specific personal-profile API test. That does not
establish an organization-wide retention policy or resolve OPEN-5 generally.
