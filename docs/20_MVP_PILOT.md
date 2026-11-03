# Menjalankan MVP OSCAR secara lokal

Scope tetap personal workspace sesuai PRD. Runtime ini menjalankan database,
API dan web dengan Docker Compose. Data database, PDF dan log berada pada volume
terpisah dan bertahan setelah container dihentikan atau dibuat ulang.

## Persiapan

- Docker Desktop atau Docker Engine dengan Compose v2 dan dukungan `up --wait`.
- Python 3.12 atau lebih baru untuk helper pengelolaan.
- Source repository terbaru. Port `8000` dan `5173` tersedia.

Semua perintah dijalankan dari root repository. Untuk pemakaian normal:

```bash
python scripts/pilot.py init
python scripts/pilot.py start
```

Buka **http://127.0.0.1:5173**. Inisialisasi membuat `.env.pilot` dengan kunci API
OSCAR dan password database acak. File yang sudah ada tidak ditimpa. Simpan file
tersebut secara privat. Kredensial tidak dimasukkan ke image atau paket extension.

Mode normal menyediakan capture, profil, tracking dan analytics. Generasi AI
memerlukan kredensial provider yang valid. Jika belum dikonfigurasi, aplikasi
memberi pesan bahwa AI belum tersedia. Hasil simulasi tidak otomatis menggantikan
model pada mode normal.

## Mengaktifkan AI pada mode normal

`OSCAR_API_KEY` adalah kunci akses aplikasi untuk web, extension dan shortcut HP.
`OPENAI_API_KEY` adalah kunci provider AI. Jangan menggunakan kunci OpenAI sebagai
kunci aplikasi atau memasukkannya ke pengaturan extension/HTTP Shortcuts.

Sesudah `init`, jalankan:

```bash
python scripts/pilot.py configure-ai
python scripts/pilot.py start
```

Masukkan kunci OpenAI saat diminta di terminal; input tidak ditampilkan. Helper
memperbarui `.env.pilot` secara atomik dengan izin privat, mempertahankan kunci
aplikasi dan password database. Kunci tidak diberikan lewat argumen command line,
tidak dicetak, dan tidak di-commit. Jika stack sudah berjalan, `start` membuat
ulang layanan yang konfigurasinya berubah. Mode simulasi tidak memerlukan kunci AI.

Model default tetap `gpt-4.1`. Satu generasi memakai satu percobaan provider,
timeout 90 detik dan batas output 16.000 token. Respons tidak disimpan untuk
retrieval di OpenAI (`store=false`); ini bukan pernyataan bahwa akun sudah
mendapat Zero Data Retention. Review OPEN-5 sebelum mengirim profil pribadi.

Pesan kegagalan membedakan autentikasi, kuota, rate limit, timeout dan koneksi.
Kegagalan tidak membuat versi CV parsial. Periksa konfigurasi/billing/koneksi
sesuai pesan sebelum mengulang.

Evaluasi empat kasus dengan profil contoh publik sebelum memakai profil asli:

```bash
cd apps/api
uv run python scripts/eval_cv_grounding.py --suite --env-file ../../.env.pilot \
  --json-output ../../var/logs/live-eval.json
```

Evaluasi melakukan panggilan berbayar dan mengirim fixture ke OpenAI; jalankan
hanya dengan izin pemilik kunci. Hasilnya harus `passed`, bukan sekadar berhasil
mencetak draft. Kasusnya mencakup kecocokan peran, angka yang tidak didukung,
teknologi yang tidak dimiliki, dan instruksi berbahaya dalam teks lowongan.

## Mencoba alur tanpa API AI

Gunakan mode simulasi yang terpisah untuk contoh data:

```bash
python scripts/pilot.py init --simulation
python scripts/pilot.py start --simulation
```

Mode ini menggunakan `.env.simulation`, project Compose `oscar-simulation`,
database `oscar_simulation_pilot` dan volume berbeda. Banner pada web menjelaskan
bahwa hasil CV bersifat deterministik. Provider menyalin fakta contoh, sehingga
alur aplikasi dapat diuji tanpa menilai kualitas AI.

Kedua mode menggunakan port yang sama. Hentikan salah satunya sebelum menjalankan
mode lain. `stop` menyimpan volume:

```bash
python scripts/pilot.py status --simulation
python scripts/pilot.py stop --simulation
```

Untuk mode normal, gunakan perintah yang sama tanpa `--simulation`.

## Capture dan extension

1. Buka Job Inbox. Simpan URL dan deskripsi lengkap untuk percobaan pertama.
2. Untuk extension 0.1.3, ekstrak ZIP, buka halaman extensions, aktifkan Developer
   mode dan pilih Load unpacked. Panduan lengkap ada di `apps/extension/INSTALL.md`.
3. API base URL extension adalah `http://127.0.0.1:8000/api/v1`. API key diambil
   dari `OSCAR_API_KEY` pada file konfigurasi mode yang sedang dijalankan.
4. Jika halaman portal menampilkan verifikasi/login, URL dapat disimpan untuk
   dilengkapi. Buka job yang sama di OSCAR, tempel deskripsi asli, lalu simpan.

Pada 2 November 2026, halaman contoh Jobstreet dan Kalibrr berhasil dibuka di
browser cloud, sedangkan probe GitHub runner sebelumnya mendapat verifikasi
Cloudflare. Pembacaan nama perusahaan dari markup yang diamati diuji lewat
fixture. Capture extension langsung pada kedua portal tersebut masih perlu
divalidasi pada browser yang memuat extension. Native popup telah diuji pada
lowongan publik Fitch dan capture LinkedIn sudah diverifikasi pada sesi sebelumnya.

## Profil, CV, dan lamaran pertama

Untuk prototipe Share Android melalui HTTP Shortcuts, lihat
[21_ANDROID_SHARE_SHORTCUT.md](21_ANDROID_SHARE_SHORTCUT.md). Penerimaan PWA dan
penerimaan melalui aplikasi shortcut diuji dan dilaporkan secara terpisah.

Ikuti [18_FIRST_REAL_USAGE.md](18_FIRST_REAL_USAGE.md). Isi fakta karier secara
akurat, review setiap versi CV, approve, lalu export dan periksa PDF sebelum
dipakai. Lamaran dikirim secara manual dan versi CV yang dikirim dicatat di OSCAR.

Evaluasi model asli, profil asli yang lengkap, share dari perangkat HP fisik dan
lamaran nyata tetap merupakan pemeriksaan pilot. Hasil tes otomatis dengan
provider simulasi tidak memenuhi pemeriksaan tersebut.

## Backup dan pemeriksaan pemulihan

Saat stack berjalan:

```bash
python scripts/pilot.py backup
python scripts/pilot.py verify-backup --directory backups/NAMA_BACKUP
```

Tambahkan `--simulation` untuk data simulasi. Backup berisi dump PostgreSQL,
arsip PDF dan manifest checksum. Perintah hanya menyatakan backup selesai setelah
kedua file berhasil dibuat. Direktori tujuan yang sudah ada tidak ditimpa.

`verify-backup` memeriksa checksum, memulihkan dump pada database baru dengan nama
acak, mengekstrak PDF ke direktori sementara dan memeriksa format file. Hanya
database uji pemulihan yang kemudian dihapus. Database aktif tetap digunakan oleh
aplikasi. Simpan backup beserta file konfigurasi secara privat di lokasi lain.

Untuk pemulihan operasional setelah kerusakan, pertahankan salinan backup asli,
pulihkan ke database baru dan arsip PDF ke volume dokumen yang baru, lalu arahkan
konfigurasi ke hasil pemulihan. Hindari menimpa data aktif saat memeriksa backup.

## Bukti penerimaan teknis

Workflow **Local pilot runtime** membangun image sebenarnya dan memeriksa:

- bootstrap database baru dan health seluruh stack;
- otorisasi API dan kunci server tidak muncul dalam HTML browser;
- enam tes browser desktop/mobile pada server Node di container, termasuk form, review, approval dan download;
- capture halaman verifikasi, enrichment, profil, simulasi CV, approval dan PDF;
- tracking sampai interview serta dashboard;
- backup database/PDF dan restore pada database uji;
- job, versi CV dan byte PDF bertahan setelah container dibuat ulang;
- mode normal tetap berjalan saat AI belum dikonfigurasi dan mengembalikan 503 yang jelas.

CI lain menjalankan tes API, enam tes browser desktop/mobile, pemeriksaan
extension deterministik dan native popup. Lihat hasil Actions pada commit yang
sedang dipakai. Batas selesai V1 pada roadmap tetap memerlukan bukti pemakaian
nyata, termasuk target 50 lowongan dan 25 lamaran.

## Batas akses

Web dan API dipublikasikan pada loopback komputer lokal. Database tidak memiliki
port host. Akses HP memerlukan setup privat/HTTPS pada
[09_MOBILE_CAPTURE_DESIGN.md](09_MOBILE_CAPTURE_DESIGN.md). Runtime ini tidak
menyediakan hosting publik atau login multiuser.
