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
