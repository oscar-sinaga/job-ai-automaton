# OSCAR Job Copilot 0.1.6

## Pasang di Chrome atau Edge

1. Ekstrak ZIP ke folder tetap, misalnya `OSCAR-Extension`.
2. Buka `chrome://extensions` atau `edge://extensions`.
3. Aktifkan **Developer mode**, klik **Load unpacked**, lalu pilih folder yang berisi `manifest.json`.
4. Buka **Extension options** dari menu extension.
5. Isi **API base URL** dengan `http://127.0.0.1:8000/api/v1` dan **API key** sesuai backend OSCAR yang sedang berjalan. Klik **Save**.
6. Buka halaman detail lowongan, klik ikon OSCAR, lalu **Save this job**.
7. Buka Job Inbox di web OSCAR untuk melihat hasilnya.

Backend dan database harus berjalan di komputer yang bisa dijangkau browser. Alamat `127.0.0.1` menunjuk ke komputer tempat browser dijalankan. Runner GitHub hanya hidup selama tes dan tidak menyediakan backend permanen.

Paket ini mengizinkan koneksi ke `http://127.0.0.1:8000/*` dan port alternatif
`http://127.0.0.1:8001/*`. Jika memakai launcher Windows, isi API base URL dengan
`http://127.0.0.1:8001/api/v1`. Untuk domain atau port lain, sesuaikan
`host_permissions` di `manifest.json`, muat ulang extension, lalu ubah URL di options.

API key adalah kunci autentikasi backend OSCAR. Fitur capture memakai DOM halaman dan tidak memerlukan API AI. `simulation-only-key` hanya berlaku saat backend dijalankan dengan script simulasi repository.

## Hasil dan kondisi yang diuji

- Pada LinkedIn dan Jobstreet, JD, judul, dan perusahaan dibaca dari panel detail terpilih. Identitas yang tidak cocok atau belum jelas menyimpan tautan saja.
- Pada situs lain, judul dan perusahaan dibaca dari JSON-LD JobPosting atau microdata. Judul memakai heading utama jika metadata tidak tersedia, lalu judul tab sebagai fallback.
- Judul tab asli dan teks capture tetap disimpan dalam snapshot.
- Menyimpan URL yang sama lagi menghasilkan capture baru dengan penanda kemungkinan duplikat, sesuai kontrak aplikasi.
- Jika API tidak dapat dijangkau, popup menampilkan pesan untuk memeriksa backend dan URL. Tombol Save aktif lagi untuk mencoba ulang.

Jika extension diperbarui, ganti isi folder dengan paket terbaru, klik **Reload** di halaman extensions, lalu muat ulang halaman lowongan.

## LinkedIn dengan daftar lowongan dan panel detail

Capture mengambil deskripsi dari panel detail lowongan yang terbuka, beserta
judul/perusahaan pada panel yang sama. Daftar rekomendasi, Premium, kontak dan
sidebar tidak menjadi bagian JD. URL pencarian dengan `currentJobId` disimpan
sebagai tautan langsung ke job tersebut; URL halaman asal tetap menjadi metadata.

Susunan LinkedIn lama dan susunan baru dengan judul berupa tautan serta bagian
**About the job** didukung. Jika teks lengkap belum tersedia atau ID di
panel tidak sesuai URL, extension menyimpan tautan saja. Buka deskripsi lengkap
dan capture ulang, atau lengkapi JD melalui Job Detail. Snapshot lama tetap
menjadi riwayat; pembaruan extractor tidak menghapus atau menulis ulang data lama.

## Jobstreet dengan daftar lowongan dan panel detail

Capture hanya membaca elemen deskripsi lowongan, tanpa daftar pencarian,
insights, employer questions, profil perusahaan, dan rekomendasi. URL selected
`jobId` pada halaman pencarian disimpan sebagai tautan langsung `/job/<id>`.
Pada halaman pencarian, ID panel atau tautan judul harus cocok; JSON-LD yang
cocok URL, judul, dan perusahaan dapat membuktikan identitas panel yang terlihat.
JSON-LD lowongan lain tidak dipakai sebagai pengganti deskripsi.

Jika situs mengubah struktur atau panel masih berganti, popup memberi tahu bahwa
capture belum lengkap. Buka halaman detail langsung, tunggu selesai dimuat, lalu
capture ulang. Snapshot sebelumnya tetap tersimpan sebagai riwayat.

## Saat halaman meminta verifikasi atau login

Extension mengenali pola halaman verifikasi Cloudflare, halaman login, dan access denied yang umum. **Save this job** tetap menyimpan tautan dengan status **NEEDS_ENRICHMENT**, tanpa memakai pesan verifikasi sebagai deskripsi atau judul lowongan.

1. Buka job yang disimpan melalui Job Inbox OSCAR.
2. Buka halaman lowongan dengan browser biasa. Selesaikan login/verifikasi bila diminta situs.
3. Salin deskripsi lowongan yang terlihat dan tempel pada kolom pelengkap di detail job OSCAR, lalu klik **Save description**.
4. Setelah deskripsi tersimpan, tombol **Generate CV** tersedia. Judul dan perusahaan dapat diperbaiki melalui **Correct title / company** pada halaman yang sama.

Jika halaman belum bisa dibuka, simpan URL melalui formulir **Save a job** di web OSCAR dan lengkapi nanti. Web search dapat membantu menemukan URL atau situs karier perusahaan asal. Paket ini tidak menyediakan layanan web search otomatis atau mengubah aturan akses portal. Pola verifikasi/login dapat berubah, sehingga deteksi bersifat konservatif.
