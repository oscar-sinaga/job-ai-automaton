# Tencent personal workspace

The operator explicitly authorized a Tencent VPS installation on 2026-11-09.
The Windows/local pilot remains supported; the VPS is independent of Windows
Credential Manager, VS Code Remote and the operator's laptop.

## Runtime contract

- Public UI: `https://150.109.17.147/workspaces/jobs/` after signing in to the
  Application Control Center as its administrator. Ordinary ACC accounts cannot
  access this single-person career workspace.
- External capture API: `/workspaces/jobs/api/v1`; all business endpoints require
  the separate `X-API-Key`. The web server adds that key only on server-side calls.
  The OpenAI provider key never reaches the browser or extension.
- Build the web image with `OSCAR_BASE_PATH=/workspaces/jobs`. An empty base keeps
  local development behavior. Internal links, redirects, manifest and service
  worker use the configured base.
- Run the real API using `python -m uvicorn oscar_api.main:app`, one worker,
  `OSCAR_ENV=production`. The simulation entry point is never a fallback in this
  installation. Local browser acceptance uses an explicit fake provider and
  synthetic data; it does not validate paid model quality.
- Use the existing PostgreSQL 17 instance, database `job_ai_automaton`, restricted
  role `job_ai_app`, pool size 3 with overflow 1. Do not create another database
  server or import local career records as part of source deployment.
- API: 192 MiB / 0.10 CPU; Node web: 96 MiB / 0.05 CPU. Containers run as UID
  10001 with read-only root, dropped capabilities, bounded temporary files/logs
  and no published host ports. Documents and application logs use named volumes.

## Credentials and operations

The approved existing provider key is stored only at
`/srv/oscar/job-ai-automaton/.private/api.env` (root, mode 0600; directory 0700).
Database credentials and the client API key are generated on the VPS. Web-only
configuration lives in the adjacent `web.env`. These files must remain outside
Git, build contexts and source archives.

The shared deployment manifest and Nginx locations are maintained with the ACC
deployment. Nginx uses owner authorization subrequests, strips panel cookies
before forwarding to this application and supports 120-second API responses.
Only HTTPS 443 and SSH 22 are exposed. Existing protected containers are kept;
ingress changes require syntax validation followed by a graceful reload.

The existing daily PostgreSQL backup job must include this database, global role
definitions without passwords, and `job-documents` PDFs. Snapshots are private,
checksummed and require restore rehearsal. App secrets require separate secure
operator retention; role dumps intentionally do not contain passwords.

Before starting these always-on containers, reserve their caps in ACC's global
budget together with Decision Engine. On the 3724 MiB host, one 256 MiB demo,
the existing scheduled job and a 640 MiB available-memory guard remain budgeted.
Do not stop protected services to reclaim capacity.

## Validation record

API: 433 passed, 9 Windows-only skips; Ruff and mypy passed. Web Svelte check:
0 errors / 0 warnings. Both frontend lockfiles pin patched `devalue` 5.9.4.
Deployment evidence, exact revisions, browser results, runtime resources and
restore results are recorded in the shared operator deployment report. A local
Docker pass is not a claim that the public VPS deployment is complete.

## GitHub synchronization follow-up

On 2026-11-09 the operator authorized pushing all application/VPS changes.
The Windows launcher workflow explicitly selects native Windows PowerShell for
its Windows test process, preventing PowerShell 7 module paths from breaking
the WinPS 5.1 ACL check. Linux uses Bash. This CI-only change does not alter the
running Tencent application image or require a service restart.
