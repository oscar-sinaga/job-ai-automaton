# Replikasi job-ai-automaton ke host Linux baru

Paket terpisah dari deployment Tencent yang sedang berjalan. Compose pada direktori
ini memakai sintaks JSON yang valid sebagai YAML. Docker Engine dan Compose 2.30+
harus sudah tersedia. Ubuntu 24.04/WSL dengan Python 3.10+ dan OpenSSL didukung.
Tidak ada instalasi ulang host, penghapusan volume, SSH/password lama, atau perubahan
firewall otomatis. Jalankan audit read-only layanan, disk, RAM dan listener sebelum memasang.

## Setup dengan PostgreSQL baru

```bash
python3 deploy/replica/manage.py init --origin https://YOUR_HOST
python3 deploy/replica/manage.py check
python3 deploy/replica/manage.py build
python3 deploy/replica/manage.py migrate
# Siapkan sertifikat sebelum up (scraper tidak membuka port web).
python3 deploy/replica/manage.py up
python3 deploy/replica/manage.py status
```

Setup membuat `.private/replica` mode 0700 dan file credential 0600 pada host target.
Password database baru dan secret aplikasi dibuat acak di sana. Username panel/gateway
`oscar`; password dipilih melalui prompt tersembunyi. Tidak ada ketergantungan Windows
Credential Manager. Jangan menyalin `.private`, database atau backup ke Git/image.

Untuk PostgreSQL existing, gunakan init berikut sebagai pengganti init di atas:

```bash
python3 deploy/replica/manage.py init --origin https://YOUR_HOST --database existing \
  --db-host YOUR_DB_HOST --db-name oscar_jobs --db-user job_app
```

Host database harus dapat dijangkau dari jaringan Docker. Buat database khusus aplikasi
dan role owner yang sesuai terlebih dahulu; jangan arahkan migrasi ke database aplikasi
lain. Existing mode tidak membuat/mengganti server database atau volume. Password diminta
tersembunyi. Default koneksi existing memerlukan TLS (`--db-sslmode require`); gunakan
`verify-full` dengan CA yang tersedia di image, atau `disable` hanya pada jaringan Docker
privat terpercaya. Untuk database dalam container existing, hubungkan jaringan private
yang sesuai menggunakan init `--db-network NETWORK --db-network-owner COMPOSE_PROJECT`.
Hanya network bridge lokal internal berlabel Compose network=database dan owner project
yang cocok yang diterima; ID network dipin dan dicek ulang sebelum setiap operasi.
Helper menulis override privat. Jangan membuka 5432
ke internet. Database baru memakai private network tanpa port host dan password SCRAM.

## HTTPS dan kredensial aplikasi

Pasang sertifikat untuk hostname/IP yang dipilih sebagai `.private/replica/tls/fullchain.pem`
dan `privkey.pem`. Path sertifikat dibaca dari bind mount; jangan taruh key di repo.
Proxy berjalan tanpa root memakai UID/GID operator yang dicatat saat init. File TLS
harus dimiliki UID tersebut dan private key mode 0600. Jika init dijalankan root,
UID proxy dipilih 10001:10001; ubah ownership file TLS ke UID/GID itu. Jangan membuat
private key atau hash gateway bisa dibaca oleh user lain.
Sertifikat publik dan auto-renew harus disiapkan operator/ACME sesuai domain/IP yang baru;
sertifikat Tencent tidak dipakai ulang. Reload Nginx setelah sertifikat diperbarui.
Tanpa domain, sertifikat IP yang sah tetap diperlukan. Self-signed hanya untuk uji lokal.

Hanya edge HTTPS 443 dipublikasikan. API, frontend, agent dan PostgreSQL tidak menerbitkan
port host. Untuk uji laptop gunakan origin `https://localhost:8443` (bind loopback).
Jangan menjalankan beberapa edge di IP:443 yang sama. Bila semua aplikasi dipasang pada
satu server, gunakan satu reverse proxy ACC dan registry workspace yang ada, dengan
PostgreSQL bersama dan database/role terpisah. Paket ini memasang aplikasi secara mandiri,
bukan satu bundel yang otomatis menggabungkan empat deployment.

## Resource, data dan backup

Semua service mempunyai cap RAM/CPU/PID dan rotasi log. Lihat nilai sebenarnya pada
`compose.yaml`; cap bukan penggunaan aktual. Sisakan RAM untuk OS/cache. Batas masing-masing
paket tidak berarti empat stack dengan empat PostgreSQL muat bersamaan pada RAM 4 GB.
Volume bernama mengikuti project, sehingga data tetap ada setelah container diganti.
Jangan gunakan `down -v` atau `volume prune` pada server yang berisi data.

```bash
python3 deploy/replica/manage.py backup
python3 deploy/replica/manage.py restore-check --backup-dir backups/replica/TIMESTAMP
```

Backup mencakup dump PostgreSQL format custom dan manifest SHA256; ACC menambah dua SQLite
konsisten dan config/visibility registry, Job AI menambah PDF. Private env/key tidak ikut:
simpan salinan credential terpisah secara terenkripsi. Data DB/PDF yang sedang berubah
dapat berbeda titik waktu; hentikan penulisan pada jendela maintenance untuk pemulihan
bisnis yang konsisten lintas penyimpanan. Log bukan sumber pemulihan utama.
`restore-check` memverifikasi checksum, SQLite/archive, lalu benar-benar mengimpor dump ke
PostgreSQL sementara tanpa jaringan/port. Hanya container uji miliknya yang dibersihkan.
Ia tidak menimpa data aplikasi yang aktif. Untuk pemulihan nyata, buat replica/database
kosong, restore dump tanpa owner/ACL menggunakan role migrasi, restore volume ke path
yang sesuai, lalu verifikasi login/data sebelum memindahkan trafik. Jangan restore
langsung di atas database produksi. Enkripsi dan salin backup off-host secara terjadwal;
retensi dan penjadwalan backup mengikuti kebijakan operator.

Helper `up` hanya untuk aplikasi yang belum aktif. Ia menolak restart/upgrade implisit.
Untuk upgrade existing: audit, backup, validasi image/migrasi di staging, persetujuan bila
layanan protected perlu direstart, lalu rollout yang ditinjau. Di Tencent semua aplikasi
wajib masuk ACC terlebih dahulu dan gunakan guard `deploy_registered.py`; jangan memakai
paket standalone untuk melewati registry atau menduplikasi jadwal yang sudah ada.

## Verifikasi host kosong

1. Clone repo private melalui login GitHub/operator; buat secret baru dengan init.
2. Check Compose, build image, jalankan migrasi pada database tujuan khusus aplikasi.
3. Pasang sertifikat sesuai origin, start, pastikan seluruh healthcheck sehat.
4. Verifikasi HTTPS dengan CA yang benar, akses anonim/akun berwenang, lalu lakukan satu
   operasi aplikasi dan pastikan data tersimpan setelah container dibuat ulang di staging.
5. Ambil backup dan jalankan restore-check. Catat commit, image ID dan hasil verifikasi.
6. Jangan menyatakan deployed hanya karena config/build atau fixture offline lulus.

## Job AI

Web standalone dilindungi HTTP Basic melalui HTTPS (user oscar), karena UI menggunakan
API key server-side dan belum menyediakan login user mandiri. API tetap memerlukan
X-API-Key; extension/mobile pada mode ini perlu autentikasi gateway juga. Deployment
Tencent mempertahankan login ACC yang sudah ada. Isi OPENAI_API_KEY hanya pada app.env
privat jika fitur AI akan dipakai; kosong berarti fitur AI belum bisa memanggil provider.
Tidak ada AI request yang dijalankan oleh setup atau healthcheck. API berjalan dengan
OSCAR_ENV=production, memakai migrasi eksplisit dan tidak memakai serve_pilot.py.
