# OSCAR Job Copilot 0.1.2

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
