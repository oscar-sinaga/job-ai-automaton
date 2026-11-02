# OSCAR Job Copilot 0.1.3

## Pasang di Chrome atau Edge

1. Ekstrak ZIP ke folder tetap, misalnya `OSCAR-Extension`.
2. Buka `chrome://extensions` atau `edge://extensions`.
3. Aktifkan **Developer mode**, klik **Load unpacked**, lalu pilih folder yang berisi `manifest.json`.
4. Buka **Extension options** dari menu extension.
5. Isi **API base URL** dengan `http://127.0.0.1:8000/api/v1` dan **API key** sesuai backend OSCAR yang sedang berjalan. Klik **Save**.
6. Buka halaman detail lowongan, klik ikon OSCAR, lalu **Save this job**.
7. Buka Job Inbox di web OSCAR untuk melihat hasilnya.

Backend dan database harus berjalan di komputer yang bisa dijangkau browser. Alamat `127.0.0.1` menunjuk ke komputer tempat browser dijalankan. Runner GitHub hanya hidup selama tes dan tidak menyediakan backend permanen.

Paket ini mengizinkan koneksi ke `http://127.0.0.1:8000/*`. Untuk backend dengan domain atau port lain, sesuaikan `host_permissions` di `manifest.json`, muat ulang extension, lalu ubah API base URL di options.

API key adalah kunci autentikasi backend OSCAR. Fitur capture memakai DOM halaman dan tidak memerlukan API AI. `simulation-only-key` hanya berlaku saat backend dijalankan dengan script simulasi repository.

## Hasil dan kondisi yang diuji

- Judul dan perusahaan dibaca dari JSON-LD JobPosting atau microdata. Judul memakai heading utama jika metadata tidak tersedia, lalu judul tab sebagai fallback.
- Judul tab asli dan teks capture tetap disimpan dalam snapshot.
- Menyimpan URL yang sama lagi menghasilkan capture baru dengan penanda kemungkinan duplikat, sesuai kontrak aplikasi.
- Jika API tidak dapat dijangkau, popup menampilkan pesan untuk memeriksa backend dan URL. Tombol Save aktif lagi untuk mencoba ulang.

Jika extension diperbarui, ganti isi folder dengan paket terbaru, klik **Reload** di halaman extensions, lalu muat ulang halaman lowongan.

## Saat halaman meminta verifikasi atau login

Extension mengenali pola halaman verifikasi Cloudflare, halaman login, dan access denied yang umum. **Save this job** tetap menyimpan tautan dengan status **NEEDS_ENRICHMENT**, tanpa memakai pesan verifikasi sebagai deskripsi atau judul lowongan.

1. Buka job yang disimpan melalui Job Inbox OSCAR.
2. Buka halaman lowongan dengan browser biasa. Selesaikan login/verifikasi bila diminta situs.
3. Salin deskripsi lowongan yang terlihat dan tempel pada kolom pelengkap di detail job OSCAR, lalu klik **Save description**.
4. Setelah deskripsi tersimpan, tombol **Generate CV** tersedia. Judul dan perusahaan dapat diperbaiki melalui **Correct title / company** pada halaman yang sama.

Jika halaman belum bisa dibuka, simpan URL melalui formulir **Save a job** di web OSCAR dan lengkapi nanti. Web search dapat membantu menemukan URL atau situs karier perusahaan asal. Paket ini tidak menyediakan layanan web search otomatis atau mengubah aturan akses portal. Pola verifikasi/login dapat berubah, sehingga deteksi bersifat konservatif.
