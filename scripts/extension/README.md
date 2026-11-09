# Deterministic extension regression checks

The offline runner loads the **built, unmodified Manifest V3 extension** into a
fresh Chromium profile and runs its real options, popup, service worker, and
injected content scripts. A temporary HTTP server on `127.0.0.1:8000` serves
synthetic pages and records capture requests. It never uses a real API key,
PostgreSQL, an LLM, or external job sites. Port 8000 must be free; the runner
refuses to replace an existing service and shuts down only its own server.

```bash
cd apps/web
npm ci
npx playwright install chromium
cd ../extension
npm ci
npm run test:offline
```

If browser binaries are stored outside the default cache, set
`PLAYWRIGHT_BROWSERS_PATH`. To use an explicit **full Chromium** executable, set
`PLAYWRIGHT_CHROMIUM_EXECUTABLE_PATH`. Chrome headless shell does not support the
installed-extension checks. Browser execution requires normal Chromium local IPC
permissions; a `process_singleton_posix.cc` / `socket() ... Operation not permitted`
launch error is an environment blocker, not a passing test or application failure.

Coverage:

- JSON-LD graph, invalid JSON-LD with microdata fallback, LinkedIn-style employer
  markup, and plain-heading fallback.
- Original page title, URL, full fixture description, API key header, and unique
  idempotency keys.
- Double-click suppression while saving, later-save duplicate feedback, HTTP
  errors, lost connection, successful retry, and missing-key rejection.

Default mode limits: the popup is exercised as an extension page while the fixture tab stays
active. This does **not** test the native toolbar popup, the `activeTab` grant on
third-party origins, a real backend, or compatibility with live job providers.
The fixture origin uses the manifest's existing localhost host permission;
permissions are not expanded for tests. `verify-capture.cjs` is the separate,
legacy environment-specific live demonstration and is not run by this command.

For isolated Linux browser checks, first build the extension, then run:

```bash
bash scripts/extension/test-offline-docker.sh
```

The Docker runner uses the official Playwright 1.51.1 image, matching the web
lockfile, and a disposable Chromium profile on a private Xvfb display. It mounts
only the built extension and test script read-only. It publishes no host ports,
mounts no credentials or personal data, and runs with Docker networking disabled;
its synthetic API listens only inside the container.

This mode also fulfills synthetic HTML at LinkedIn and Jobstreet URLs, invokes
the native extension action with a Linux keyboard shortcut to grant `activeTab`,
then drives the shipped popup handler in an extension tab. It verifies selected
description/title/company/canonical URL payloads, exclusion of recommendations
and company profiles, direct Jobstreet details, and safe partial captures for
stale, collapsed or unselected details. No manifest permissions are added. This
checks actual Chromium injection and messaging, but does not verify a mouse click
on the native popup, live provider markup, or the user's installed Edge profile.

The script also accepts `PLAYWRIGHT_MODULE_PATH` and `EXTENSION_PATH` for isolated
dependency and bundle locations. `EXTENSION_NATIVE_ACTION=1` enables the provider
fixtures and requires Linux X11, `xdotool`, and a visible browser on that private
display; leave it unset for the default headless localhost checks above.
