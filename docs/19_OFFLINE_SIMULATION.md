# Simulasi tanpa API di environment Codex

Tanggal verifikasi: 2 November 2026. Menggunakan profil dan lowongan contoh,
PostgreSQL sementara, serta provider deterministik `simulation-no-api`.
Tidak ada request OpenAI atau lamaran yang dikirim ke perusahaan.

## Hasil

| Pemeriksaan | Hasil |
| --- | --- |
| Backend dengan PostgreSQL 16.15 | 238 test lulus, termasuk 5 penolakan konfigurasi database simulasi yang salah |
| Migrasi | Upgrade sampai head, downgrade satu revisi, upgrade kembali lulus |
| Kualitas backend | Ruff lint/format dan mypy, termasuk entry point simulasi, lulus |
| Frontend | Svelte check: 0 error, 0 warning; production build lulus |
| Browser desktop | Alur lengkap lulus pada Chromium 134, viewport 1280 × 720 |
| Browser ukuran HP | Alur lengkap lulus pada Chromium dengan emulasi Pixel 7, viewport 393 × 727 |
| Extension | Type-check dan build lulus; belum diuji sebagai extension terpasang |
| PDF | Diunduh melalui UI, signature PDF dan kesamaan byte saat export ulang diperiksa; hasil dirender dan ditinjau visual |

Browser menjalankan formulir asli SvelteKit dan API asli dengan penyimpanan PDF
di disk. Satu-satunya dependency aplikasi yang diganti adalah provider LLM.
Assertion juga memeriksa tidak ada page error atau console error, dan halaman
profil tidak meluap secara horizontal pada kedua viewport.

Alur yang diperiksa:

1. Menyimpan kontak CV dan summary, termasuk menyimpan ulang nilai yang sama.
2. Menambahkan pengalaman dan achievement, lalu menyimpan URL/deskripsi lowongan contoh.
3. Generate CV; export sebelum approval ditolak dengan HTTP 409.
4. Menghapus summary menghasilkan versi baru yang belum disetujui; versi lama tetap utuh.
5. Review dan approve versi baru, export, lalu download PDF melalui browser.
6. Export ulang menghasilkan byte PDF yang sama.
7. Mark as Applied dengan versi CV yang tepat, lalu catat Interview received.
8. Approve ulang tidak memundurkan status Interview; KPI Saved, Applied dan Interview bertambah sesuai data contoh.

## Masalah yang ditemukan dan diperbaiki

- Sidebar selebar desktop menyisakan ruang terlalu sempit pada HP. Navigasi kini
  berada di atas pada layar kecil; formulir profil memakai satu kolom dan kontrol
  mengikuti lebar ruang yang tersedia.
- Default reset pada enhanced form dapat mengosongkan tampilan kontak/summary
  setelah menyimpan ulang nilai yang sama. Form edit tersebut kini mempertahankan
  nilai input; form penambahan pengalaman/achievement tetap dikosongkan sesudah sukses.

## Menjalankan ulang

Gunakan PostgreSQL khusus simulasi. Contoh di bawah memakai service `db` dari
Docker Compose repo dan tidak mengubah database utama `oscar`:

```bash
docker compose up -d db
docker compose exec db createdb -U oscar oscar_simulation_browser

cd apps/api
uv sync --frozen
uv run python scripts/serve_simulation.py \
  --database-url postgresql+psycopg://oscar:oscar@127.0.0.1:5432/oscar_simulation_browser \
  --storage-dir ../../var/storage/simulation
```

Jika database sudah ada, jangan jalankan `createdb` lagi. Entry point hanya
menerima driver `postgresql+psycopg`, host loopback, nama database berawalan
`oscar_simulation_`, dan tanpa opsi URL tambahan. Ia menjalankan migrasi tetapi
tidak membuat, menghapus atau membersihkan database. Env aplikasi dipaksa menjadi
`simulation`, API key lokal menjadi `simulation-only-key`, dan provider diganti
secara eksplisit. Server hanya bind ke `127.0.0.1:8001`.

Di terminal kedua:

```bash
cd apps/web
npm ci
npx playwright install chromium
npm run test:simulation
```

Playwright membangun frontend, menyalakan production preview sendiri di
`127.0.0.1:5173`, dan menghentikannya
setelah test. Port 5173 harus kosong. Test memeriksa `/health` untuk memastikan
env `simulation` dan database sehat sebelum menulis data. Request browser ke
host selain loopback ditolak. Hasil PDF/screenshot/trace berada di direktori
`apps/web/test-results/` yang diabaikan Git. Setiap run menambahkan contoh baru;
gunakan database simulasi baru bila menginginkan profil kosong.

Untuk mencoba UI secara manual, jalankan frontend dengan `API_BASE_URL` bernilai
`http://127.0.0.1:8001/api/v1` dan `API_KEY` bernilai `simulation-only-key`.
Isi hanya data contoh dan periksa health env sebelum menggunakan UI.

## Batas hasil ini

Provider hanya menyalin fakta yang disediakan, tanpa penilaian relevansi pekerjaan,
ranking cerdas, atau parafrase. Missing requirements menampilkan pemberitahuan
simulasi, dan token usage bernilai nol. Ini membuktikan integrasi aplikasi,
bukan kualitas model atau efektivitas CV untuk rekrutmen.

Emulasi viewport HP bukan pengujian perangkat fisik, PWA install, OS share target,
Tailscale, atau browser HP asli. Belum ada profil asli, evaluasi model asli,
lamaran nyata, atau pencapaian target M6/V1 dari sesi ini. Environment Codex
bersifat sementara; hasil ini tidak berarti aplikasi telah menjadi layanan hosting.

## Regresi lanjutan di cloud VM (2 November 2026)

Dijalankan ulang dari `f70cd1b` dengan PostgreSQL 16.6 terisolasi dan Chromium
headless 134. Backend: **240 test lulus**; migrasi upgrade, downgrade satu revisi,
dan upgrade kembali lulus. Ruff, format, mypy, Svelte check (0 error/warning),
dan production build lulus. Empat browser test lulus pada desktop dan emulasi
Pixel 7: dua alur lengkap di atas, ditambah dua regresi capture.

Bug yang direproduksi pada kedua viewport: menekan **Hide** setelah menempelkan
job description menghapus teks ketika editor dibuka lagi. Editor kini hanya
disembunyikan, bukan dilepas dari DOM. Test memeriksa teks tetap ada, ikut
tersimpan meskipun editor ditutup, dan formulir bersih setelah berhasil disimpan.
Fixture pengalaman memiliki nama unik per run agar pemilihan pengalaman tidak
ambigu saat database simulasi digunakan kembali.

Untuk merekam browser test yang sebenarnya (bukan demo live di desktop):

```bash
SIMULATION_VIDEO=1 npm run test:simulation
```

Video `.webm`, screenshot, dan PDF berada di `apps/web/test-results/`.

Harness extension deterministik tersedia di
[`scripts/extension/README.md`](../scripts/extension/README.md). Type-check,
build, dan syntax check lulus, tetapi assertion **installed extension belum
berjalan** di cloud VM ini: full Chromium ditolak saat membuat Unix-domain IPC
socket (`process_singleton_posix.cc`, `Operation not permitted`). Headless shell
yang dipakai tes web tidak membuktikan extension terpasang. Tidak ada klaim
baru tentang kompatibilitas live JobStreet/Kalibrr, kualitas model, perangkat HP
fisik, atau lamaran nyata.

Catatan runner terbatas: jika cache home tidak dapat ditulis, gunakan
`UV_CACHE_DIR` / `npm --cache` / `PLAYWRIGHT_BROWSERS_PATH` pada direktori writable.
Jika tiap command memakai namespace jaringan terpisah, jalankan database, API,
dan Playwright di dalam satu proses orchestration yang membersihkan hanya
proses miliknya. PostgreSQL dapat menggunakan TCP loopback tanpa Unix socket;
jangan melonggarkan pembatasan keamanan runner untuk menjalankan browser.
