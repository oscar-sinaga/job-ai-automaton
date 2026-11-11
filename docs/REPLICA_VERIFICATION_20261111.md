# Verifikasi replikasi job-ai-automaton — 11 November 2026

Perubahan ini menambahkan paket `deploy/replica`, bukan aktivasi rilis pada Tencent.
Source aplikasi dan Dockerfile aplikasi existing dipertahankan; scraper menambah
direktori state scheduler non-root pada image. Tidak ada perubahan pada VPS,
password produksi, layanan, tabel atau volume produksi dalam pekerjaan ini.

## Hasil nyata di Docker Linux lokal

- Build image aplikasi dari source repo berhasil.
- Bootstrap PostgreSQL baru, migrasi dan healthcheck berhasil.
- Mode PostgreSQL existing berhasil memakai network database internal yang owner,
  label dan ID-nya diverifikasi; ID container database tetap sama setelah migrasi.
- HTTPS dengan CA fixture yang dipercaya, login dan kontrol akses aplikasi berhasil.
- Backup format custom berhasil di-restore ke PostgreSQL sementara tanpa jaringan
  atau port publik. Checksum manifest dan arsip/state tambahan diverifikasi.
- Helper menolak restart implisit pada stack yang sudah aktif.
- Delapan tes operator lulus, mencakup literal secret, perlindungan overwrite,
  host HTTPS, SQL identifier, owner/isolasi/ID network, checksum dan path arsip.

Cgroup memory Docker teramati sesuai cap pada uji lokal.
CI `Verify portable replica` menjalankan pengujian yang sama pada Ubuntu 24.04
dengan `REPLICA_REQUIRE_CGROUP=1`. Hasil CI terbaru harus dibaca di GitHub sebelum
rollout. Pengujian lokal/CI bukan bukti deployment publik pada server baru.

## Batas verifikasi dan operasi

TLS fixture self-signed hanya untuk loopback uji dan tidak dipasang di Tencent.
Server baru memerlukan origin dan sertifikat yang sah beserta auto-renew operator.
Tidak ada registrasi ACME, provider AI/Bright Data, pengiriman email, atau request
ke situs scraping dalam smoke test ini. Credential dibuat ulang di host tujuan,
tidak ikut source/image/backup publik. Data bisnis lama perlu backup dan restore
terpisah; clone Git bukan migrasi data/secret. ARM belum diuji.

Paket standalone bukan bundel empat aplikasi pada satu IP:443. Untuk memasangnya
bersama pada Tencent, gunakan satu proxy/registry ACC serta database/role terpisah,
audit budget global dan guard deployment existing. Panduan operasional dan opsi
database tersedia di [README paket](../deploy/replica/README.md).


## README installation modes — 11 November 2026

README utama kini memuat langkah Docker lengkap untuk mode tanpa Nginx dan dengan
Nginx, termasuk clone, prasyarat, secret, migrasi, alamat akses/tunnel, database
existing, TLS dan backup. Web direct hanya mempublikasikan loopback; Job API tetap
memerlukan API key dan Decision frontend memakai URL API/CORS langsung. ACC direct
menjalankan panel/API dengan demo/browser/scheduled sample/gateway tidak aktif.
Worker scraper tidak membutuhkan Nginx atau port HTTP pada kedua situasi host.

Local Docker verification passed for each documented mode: actual image build,
new/existing PostgreSQL, web access/authentication (where applicable), backup and
real isolated restore. Direct mode starts no edge container. Nginx mode preserves
CA-verified HTTPS and gateway authentication. Nine operator cases pass. CI now has
independent proxy-mode jobs and requires actual kernel memory-controller limits.
No Tencent runtime configuration, service, volume or scraping quota was changed.
