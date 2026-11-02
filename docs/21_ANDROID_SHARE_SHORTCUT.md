# Capture dari menu Share Android

Jalur prototipe ADR-020 memakai [HTTP Shortcuts](https://http-shortcuts.rmy.ch/):
pilih Share pada lowongan, pilih HTTP Shortcuts (label **Send to…** pada beberapa
versi Android), lalu **Save to OSCAR**. Aplikasi
menampilkan **Saved as Jxxx** setelah server benar-benar menyimpan lowongan.
URL/judul saja tetap ditandai parsial; lengkapi deskripsi di OSCAR sebelum membuat CV.

Ini jalur prototipe yang terpisah dari PWA Web Share Target. Shortcut pada layar
utama Chrome tidak otomatis membuat OSCAR muncul sebagai penerima Share Android.

## Menyiapkan konfigurasi privat

1. Jalankan runtime pada [20_MVP_PILOT.md](20_MVP_PILOT.md).
2. Siapkan alamat HTTPS privat yang dapat dijangkau HP sesuai ADR-019/Tailscale
   pada [09_MOBILE_CAPTURE_DESIGN.md](09_MOBILE_CAPTURE_DESIGN.md). `127.0.0.1`
   laptop tidak bisa dipakai langsung pada HP.
3. Pasang HTTP Shortcuts dari distribusi resmi pembuatnya. Format konfigurasi
   ini mengikuti versi 4.9.0 dan diuji dengan APK x86_64 resmi di emulator.
4. Dari root repository, buat ZIP untuk alamat API privat yang sebenarnya:

```bash
python scripts/mobile/create_android_shortcut.py \
  --env-file .env.pilot \
  --api-base-url https://NAMA_PERANGKAT_PRIVAT/api/v1 \
  --output backups/mobile/capture.oscar-shortcut.zip
```

Ganti alamat contoh dengan alamat HTTPS API yang sudah dikonfigurasi. Helper
mengambil `OSCAR_API_KEY` dari file konfigurasi dan tidak mencetak nilainya.
**ZIP berisi kunci akses aplikasi:** pindahkan secara privat ke HP, jangan commit
atau bagikan. File dibuat dengan izin `600` dan file yang sudah ada tidak ditimpa.

5. Di HTTP Shortcuts, buka **Import / Export → Import from File**, lalu pilih ZIP.
6. Share tautan dari browser/aplikasi lowongan ke HTTP Shortcuts dan pilih
   **Save to OSCAR**. Periksa pesan berhasil dan lowongannya pada Job Inbox.

## Retry dan batas prototipe

Jika server tidak dapat dijangkau, pesan **Not saved** ditampilkan. Buka lagi
**Save to OSCAR** untuk mengulang kiriman terakhir. Kiriman terakhir yang sama
menggunakan Idempotency-Key yang sama, sehingga retry mendapat hasil asli.
Jika isi kiriman berubah, kunci baru dibuat. Ini bukan antrean offline untuk
banyak lowongan; jangan menganggap kiriman sudah tersimpan sebelum ada pesan sukses.

API key ditandai rahasia di aplikasi dan nilai variabel tidak disertakan saat
diekspor ulang oleh HTTP Shortcuts. Teks kiriman disusun dengan `JSON.stringify`
agar kutip, baris baru, dan karakter non-ASCII tetap menjadi data.

## Bukti pengujian

Workflow **Android emulator verification** memakai Android 15/Chrome Android
pada AVD, API/database Docker, dan APK HTTP Shortcuts 4.9.0 yang diverifikasi
dengan SHA-256 dari rilis resminya. Konfigurasi emulator memakai API key simulasi
dan port forwarding ADB, tanpa endpoint publik atau panggilan model AI.

Tes penerima web, status instalasi PWA, dan jalur native HTTP Shortcuts dicatat
terpisah di `result.json`. Untuk jalur native, pemilih Share Android harus benar-benar
terbuka, aplikasi tujuan harus terlihat, dan hasilnya harus ada pada database
serta layar sukses. Rekaman perangkat disimpan sebagai artifact Actions.

Hasil emulator tidak menggantikan pengujian HP fisik, koneksi Tailscale/data
seluler, iOS, atau aplikasi LinkedIn/Jobstreet asli. Sumber contoh pada tes
mengirim URL sintetis.
