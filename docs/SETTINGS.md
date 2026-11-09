# Workspace settings

The Settings page now supports saved CV defaults, AI generation preferences,
portable exports and explicitly confirmed data deletion. Migration `0007_settings`
adds settings, a durable file-cleanup queue and a preference snapshot on CV runs.
It does not replace any database or existing career facts.

## CV and integration preferences

Choose English/Indonesian headings, standard/compact PDF spacing and 1–8 bullets
per role. Verified statements remain verbatim. Defaults apply to subsequent
generations, with request-specific overrides; existing versions keep their saved
presentation. Generation uses prompt `cv_generator/v4` and records the effective
preferences for reproducibility. Manual edits preserve those preferences.

AI settings allow a model ID and a 512–16,000 output-token ceiling. Blank fields
follow server defaults. These affect CV generation, not the separate job parser.
Provider keys remain server environment values; the browser never receives them.
“Key configured” does not assert model access, available credit or API health.
The extension API address is derived from the current deployment base path.

## Data controls

`GET /api/v1/export?format=json|zip` requires the application API key. The web
streams this through a server-only route. JSON contains all application table
data and row counts. ZIP adds saved CV PDFs and a SHA-256 integrity manifest.
Exports exclude deletion challenges, cleanup internals and server credentials.
Personal data inside career records and job descriptions is included intentionally.

Rows and PDF bytes are read incrementally. ZIP supports up to 10,000 PDFs to bound
archive metadata; JSON remains available for larger datasets. Export requires
256 MiB free storage. A missing PDF or archive failure returns an error instead
of a partial ZIP. Temporary exports use the application storage volume, are
removed after downloads and are reclaimed after one hour if abandoned.

Deletion first returns counts and a single-use five-minute token. The owner must
type the exact scope-specific phrase. A changed record count invalidates preview.
Job-only deletion preserves career records and preferences. Full deletion leaves
the implicit account, static role categories and an empty usable profile.
It clears personal settings but retains server connection configuration.

Database deletion commits before files are removed. Failed file removals remain
in a transactional queue, retried every minute and manually from Settings.
The pending count survives reload. An outage after commit is reported as cleanup
pending, not as an unsuccessful database reset. Export/reset coordinate through
transaction locks. Backups retain their existing operator retention policy;
this feature does not delete backups or other applications' data.

## Verification and rollout

Backend acceptance uses isolated PostgreSQL and a fake provider. Browser tests
exercise persisted preferences, real JSON/ZIP downloads, cancellation, both
deletion scopes and a usable empty profile on desktop/mobile. No live provider
calls or production deletion are part of these tests.

Run API Ruff/mypy/pytest, web check/build and
`bash scripts/web/test-browser-docker.sh`. CI rehearses upgrade/downgrade/upgrade
on a disposable database. Back up production databases and documents before
applying migration `0007_settings`; keep volumes and root-only API env files.
