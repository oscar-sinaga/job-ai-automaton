# OSCAR Job Copilot

<!-- DOCKER-INSTALL-START -->

## Panduan instalasi Docker

Pilih [tanpa Nginx](#instalasi-docker-tanpa-nginx) atau
[dengan Nginx](#instalasi-docker-dengan-nginx). Panduan ini untuk instalasi baru
yang mandiri; tidak memerlukan Tencent atau ACC.
Prasyarat host Linux/Ubuntu 24.04 atau WSL: Git, Docker Engine, plugin Docker
Compose **2.30+**, Python **3.10+**, dan OpenSSL. Python host hanya menjalankan
helper; aplikasi dan PostgreSQL berjalan di container. Autentikasi GitHub diperlukan
untuk clone repo private. Docker Engine tidak dipasang/diubah otomatis oleh helper.
Di Windows, jalankan perintah Bash dari Ubuntu WSL dan clone di filesystem Linux
(misalnya `~/projects`), agar permission privat 0700/0600 dapat diterapkan.

```bash
git clone --branch main https://github.com/oscar-sinaga/job-ai-automaton.git
cd job-ai-automaton
docker version
docker compose version
python3 --version
openssl version
```

Compose di root untuk development berbeda dari paket mandiri ini. `docker-compose.yml` root hanya menjalankan PostgreSQL; `compose.pilot.yml` adalah pilot lokal.
Paket instalasi memakai `deploy/replica/compose.yaml`; helper memilih profile,
file env privat, dan override yang benar. JSON pada berkas tersebut valid sebagai YAML.
Pilih satu mode pada checkout baru. `init` menolak menimpa `.private/replica` existing;
`up` menolak restart implisit layanan yang sudah aktif. Untuk upgrade existing, audit
dan backup dahulu; jangan menghapus konfigurasi atau volume agar bisa mengulang init.
Untuk instalasi kedua pada daemon yang sama, pilih `--project` dan port yang berbeda.

## Instalasi Docker tanpa Nginx

Mode `direct` menjalankan HTTP pada **127.0.0.1 saja**, untuk laptop atau SSH tunnel
ke server lain. Container Nginx tidak dijalankan dan tidak perlu sertifikat TLS.

```bash
python3 deploy/replica/manage.py init --proxy direct --origin http://127.0.0.1:5173
python3 deploy/replica/manage.py check
python3 deploy/replica/manage.py build
python3 deploy/replica/manage.py migrate
python3 deploy/replica/manage.py up
python3 deploy/replica/manage.py status
```

Buka **http://127.0.0.1:5173/** pada host yang menjalankan Docker.
API langsung tersedia di http://127.0.0.1:8001/api/v1.
Web direct tidak memiliki login gateway Nginx; API tetap memerlukan X-API-Key. Gunakan mesin operator atau SSH tunnel yang berwenang.

Jika Docker berjalan pada server remote, dari laptop jalankan:

```bash
ssh -N -L 5173:127.0.0.1:5173 -L 8001:127.0.0.1:8001 USER@IP_SERVER
```

Lalu buka URL 127.0.0.1 yang sama di laptop. Tetap gunakan port lokal yang sama
agar origin/CORS sesuai. Untuk mengubah port saat init, sesuaikan `--origin`
dan `--direct-api-port` serta tunnel. Mode ini tidak membuka HTTP ke IP publik;
akses internet memakai mode HTTPS di bawah atau terminasi TLS yang dikonfigurasi operator.

## Instalasi Docker dengan Nginx

Mode `nginx` menjalankan reverse proxy rootless melalui satu port **HTTPS 443**.
API, frontend, agent dan PostgreSQL tetap di jaringan Docker tanpa port publik.
Gunakan checkout baru untuk memilih mode ini; ganti `YOUR_HOST` dengan domain atau
IP yang tercakup sertifikat, tanpa path. Tidak memerlukan domain berbayar bila
operator mempunyai sertifikat IP yang sah.

```bash
python3 deploy/replica/manage.py init --proxy nginx --origin https://YOUR_HOST
python3 deploy/replica/manage.py check
python3 deploy/replica/manage.py build
python3 deploy/replica/manage.py migrate
# Pasang sertifikat seperti langkah berikut sebelum menjalankan up.
```

Simpan full certificate chain di `.private/replica/tls/fullchain.pem` dan private
key di `.private/replica/tls/privkey.pem`. Gunakan sertifikat yang sah untuk host
tujuan; sertifikat serta auto-renewal diurus operator dan tidak disalin dari Tencent.
Setup tidak mendaftarkan ACME atau menerima terms pihak ketiga secara otomatis.
Untuk init oleh user Linux biasa, file harus dapat dibaca UID operator yang sama;
batasi private key dengan `chmod 600 .private/replica/tls/privkey.pem`.
Jika init dijalankan root, proxy memakai UID/GID **10001:10001**: ownership
direktori TLS dan kedua file harus sesuai, key tetap mode 0600.

```bash
python3 deploy/replica/manage.py up
python3 deploy/replica/manage.py status
curl --silent --output /dev/null --write-out "%{http_code}\n" https://YOUR_HOST/jobs
# Sebelum login, hasil yang diharapkan: 401.
```

Buka **https://YOUR_HOST/**. Login gateway `oscar` memakai password prompt init; API tetap memerlukan X-API-Key. Perintah curl tanpa autentikasi akan mendapat 401, sehingga gunakan browser untuk pemeriksaan login.

Pada server baru, siapkan akses firewall TCP 443 dan pertahankan akses SSH.
Beberapa aplikasi pada satu IP tidak bisa masing-masing mengikat 443 bersamaan;
gabungkan route pada satu reverse proxy atau gunakan IP publik/mesin yang berbeda. Integrasi
ACC pada Tencent mengikuti registry/guard existing, bukan instalasi standalone ini.

## Database existing, credential dan backup Docker

Untuk memakai PostgreSQL yang sudah ada, tambahkan opsi berikut pada **perintah init
mode yang dipilih** (bukan menjalankan init kedua):

```text
--database existing --db-host YOUR_DB_HOST --db-name oscar_jobs --db-user job_app
```

Buat database/role khusus aplikasi terlebih dahulu; password diminta tersembunyi.
Existing mode tidak membuat ulang server database atau mengganti volume.
Gunakan hostname/IP database yang dapat dijangkau container; `127.0.0.1` di dalam
container menunjuk container itu sendiri.
Untuk database Docker dalam jaringan private, gunakan tambahan
`--db-network NETWORK --db-network-owner COMPOSE_PROJECT` dan, hanya bila jaringan
Docker internal terpercaya itu tidak menyediakan TLS, `--db-sslmode disable`.
Helper memverifikasi bridge internal, label owner/network dan ID jaringan.
Untuk koneksi remote defaultnya TLS `require`; lihat opsi CA/verify-full pada
[panduan replikasi](deploy/replica/README.md).

Job AI dapat dibuka tanpa provider AI; fitur AI memerlukan OPENAI_API_KEY yang diisi privat pada app.env sebelum up. Setup/tes tidak memanggil OpenAI.
Credential tersimpan di host tujuan pada `.private/replica` (0700), file env (0600),
dan tidak masuk Git/image. Jangan menaruh secret pada perintah terminal atau README.
Volume database dan dokumen tetap ada saat container diganti.

```bash
python3 deploy/replica/manage.py backup
python3 deploy/replica/manage.py restore-check --backup-dir backups/replica/TIMESTAMP
```

Ganti TIMESTAMP dengan direktori hasil backup. Restore-check benar-benar mengimpor
dump ke database sementara terisolasi; tidak menimpa database aplikasi yang aktif.
Enkripsi/copy backup off-host dan jadwalkan retensi sesuai kebijakan operator.
Clone source tidak memindahkan data atau credential lama. Jangan memakai `down -v`
atau `volume prune` pada deployment yang berisi data. Rincian resource, restore,
healthcheck dan batas pengujian ada di [panduan replikasi](deploy/replica/README.md).

<!-- DOCKER-INSTALL-END -->

A personal job-search operating system: capture jobs in seconds, generate grounded
tailored CVs from a verified career-fact store (zero fabricated claims), track every
application and which exact CV version was sent, and see the funnel honestly.

> Automatic where automation is reliable, human-assisted where automation is fragile.

**Status (2026-11-03): technical MVP is ready for a personal pilot, with real-model
fixture acceptance and Android emulator sharing verified.**
The review found gaps in CV grounding, approval, PDF rendering and download.
The fixes restrict CV claims to stored career statements, validate skills and edits,
require review before export, preserve application status, and provide a working PDF
download. Deterministic browser/runtime tests use a fake model. Separately, four
approved real-API cases passed with the low-cost `gpt-6-luna` model; see the
[recorded results](evals/cv_grounding/results/2026-11-03_gpt-6-luna.json).
A private real-profile pilot also passed generation, review and PDF download
for three real vacancies using the owner's reference layout; see
[scope and evidence](docs/22_REAL_PROFILE_ACCEPTANCE.md). Gap suggestions remain
review items. Physical-phone compatibility and V1 usage targets still require use.
Android 15 emulator tests passed native Share → HTTP Shortcuts → the capture API,
with the saved job checked in the database and on the device success screen.
See [Android setup and limits](docs/21_ANDROID_SHARE_SHORTCUT.md).

Start with **[docs/18_FIRST_REAL_USAGE.md](docs/18_FIRST_REAL_USAGE.md)** for the
first 3–5 applications, then measure M6 against
[docs/15_ROADMAP_AND_MILESTONES.md](docs/15_ROADMAP_AND_MILESTONES.md).

For a persistent local stack, use **[docs/20_MVP_PILOT.md](docs/20_MVP_PILOT.md)**.
It runs PostgreSQL, the API and a standalone Node web server with Docker Compose,
including explicit simulation mode, backup and restore verification. The CI runtime
check exercises the actual images and verifies data and PDFs after container recreation.
Normal-mode AI setup uses `python scripts/pilot.py configure-ai` with hidden terminal
input. `OSCAR_API_KEY` stays separate from the provider's `OPENAI_API_KEY`.

```bash
python scripts/pilot.py init --simulation
python scripts/pilot.py start --simulation
```

Open `http://127.0.0.1:5173`. Simulation uses example data and deterministic CV
output without AI requests. Omit `--simulation` for the normal local workspace.
The default model is `gpt-6-luna`, with no reasoning, a 4,096-output-token limit
and no automatic upgrade to a more expensive model. The real-usage targets
remain separate from the fixture acceptance result.

For testing without an API key, use **[docs/19_OFFLINE_SIMULATION.md](docs/19_OFFLINE_SIMULATION.md)**:
an isolated simulation server plus desktop/mobile-viewport browser tests. This
checks the app flow with example facts, not model quality or real applications.

## Start here

- **[docs/README.md](docs/README.md)** — the design pack and current pilot guide: PRD, architecture, data model, API design, LLM/grounding design, security, test strategy, risks, and open decisions.
- **[docs/15_ROADMAP_AND_MILESTONES.md](docs/15_ROADMAP_AND_MILESTONES.md)** — what's built, what's verified vs. not, and what M6 requires.
- **[OSCAR_Job_Copilot_AI_Agent_Master_Spec_v2.md](OSCAR_Job_Copilot_AI_Agent_Master_Spec_v2.md)** — the source engineering spec.
- **[OSCAR_Job_Copilot_User_Plan_v2.md](OSCAR_Job_Copilot_User_Plan_v2.md)** — the source product plan (Indonesian).

## Stack (fixed, ADR-001)

FastAPI + PostgreSQL (backend) · SvelteKit + TypeScript + Tailwind CSS (frontend) · Python managed with `uv` · OpenAI behind a provider port (ADR-025).

## Local development

Docker runs inside WSL2 on this machine, and Windows could not reliably reach the WSL2-forwarded Postgres port during development (ADR-022) — so run everything that touches the database **from a WSL terminal**. The web app is unaffected and runs fine from Windows.

```bash
# inside WSL
cp .env.example .env                     # fill in OSCAR_API_KEY, OPENAI_API_KEY
docker compose up -d db

cd apps/api
export UV_PROJECT_ENVIRONMENT=~/.venvs/oscar-api   # keep the venv off /mnt/c (ADR-022)
uv sync
uv run alembic upgrade head
uv run uvicorn oscar_api.main:app --reload --port 8000   # http://127.0.0.1:8000/health
uv run pytest                                            # tests use a database: use a dedicated test DB
```

```bash
# from Windows (or WSL) -- proxies /api to the FastAPI server above
cd apps/web
cp .env.example .env                     # fill in API_KEY (matches OSCAR_API_KEY above)
npm install
npm run dev                                              # http://127.0.0.1:5173
```

Full runbook: [docs/14_DEPLOYMENT_PLAN.md](docs/14_DEPLOYMENT_PLAN.md). WSL rationale: [docs/17_DECISION_LOG.md](docs/17_DECISION_LOG.md) ADR-022.

## Repository layout

```text
apps/
  api/          FastAPI backend (uv-managed): jobs, career profile, CV generation +
                grounding, application tracking, analytics — 6 migrations, ~45 modules
  web/          SvelteKit + TS + Tailwind: Dashboard, Job Inbox/Detail, Career Profile,
                CV Review, Analytics, mobile share-target
  extension/    Browser extension (MV3, esbuild): one-click capture
  mobile/       Mobile capture setup instructions (PWA lives in apps/web; see apps/mobile/README.md)
agents/         LLM agent prompts (cv_generator/v2.md, selection-only pilot); job_parser not built (P1)
adapters/       Future ATS automation adapters (P3, not yet implemented)
domain/         Signpost only — domain logic lives in apps/api (see domain/README.md)
workers/        Signpost only — background tasks run in-process for now (see workers/README.md)
evals/          CV grounding fixtures + harness (apps/api/scripts/); four real-API
                GPT-6 Luna cases passed, with token usage and evidence recorded
docs/           The design pack — read this before touching code
```

## Before Milestone 6

Remaining open decisions in [docs/17_DECISION_LOG.md](docs/17_DECISION_LOG.md) §2 (none currently block anything): OPEN-3 (durable job queue), OPEN-4 (embedding-based retrieval), OPEN-5 (LLM provider data-retention posture — review before sending real career data to OpenAI), OPEN-6 (production hosting).

To actually start using this: set `OPENAI_API_KEY`, populate the career profile with real experience/achievements (`/career-profile`), and run `apps/api/scripts/eval_cv_grounding.py` against its two adversarial cases before trusting CV generation with a real application.
