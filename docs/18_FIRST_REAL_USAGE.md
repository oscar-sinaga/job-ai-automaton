# Mulai memakai OSCAR Job Copilot

Updated: 2026-11-02. Acuan scope tetap User Plan v2, PRD dan roadmap M0–M6.

## Tujuan terdekat

Pakai satu alur untuk lamaran nyata:

**Simpan lowongan → pilih fakta karier untuk CV → review → approve → export dan
download PDF → melamar secara manual → Mark as Applied dengan versi CV yang dikirim.**

Checkpoint pertama: 5–10 lowongan tersimpan dan 3–5 lamaran nyata. Sesudah itu,
perbaiki hambatan berdasarkan pengalaman. Target akhir V1 tetap 50 lowongan,
25 lamaran, capture HP, dashboard/analytics yang benar, dan target kualitas/waktu.

## Yang sudah dibereskan

- Klaim harus cocok dengan satu kalimat achievement yang dirujuk; ID fakta saja
  tidak cukup. Untuk pilot, AI memilih dan mengurutkan kalimat, tanpa parafrase bebas.
- Skills diperiksa; fakta tidak boleh ditempatkan di pengalaman/proyek yang salah.
- Edit CV diperiksa dan membuat versi baru yang belum disetujui.
- Fakta sumber, perusahaan/jabatan/periode, serta kontak disimpan bersama versi CV.
- Approve tidak memundurkan Applied, Interview atau status lain.
- PDF mendukung beberapa bullet dan Unicode dengan font DejaVu yang dibundel.
- Export memerlukan approval versi tersebut; hasilnya menyediakan tautan download.
- Ekspor ulang memakai file yang sama. Perubahan profil tidak menimpa CV lama.
- Nilai CORS dari `.env.example` sekarang dapat dibaca saat startup; daftar
  comma-separated dan JSON sama-sama didukung.

## Persiapan profil asli

1. Jalankan aplikasi mengikuti README dan runbook. Gunakan database test terpisah
   untuk test; jangan menjalankan test atau percobaan migrasi pada data lamaran asli.
2. Buka **Career Profile**. Di Application preferences, isi **CV name** dan
   **CV email**, lalu kontak/tautan lain jika diinginkan. Klik Save preferences.
3. Isi pengalaman dan proyek yang relevan dengan jenis pekerjaan yang diincar.
4. Tambahkan achievement sebagai kalimat yang sudah layak muncul di CV. Hubungkan
   ke pengalaman atau proyek yang benar; beri skill/technology tags. Mulai dengan
   pengalaman terpenting, lalu lengkapi menuju target profil pada M2.
5. Jika kalimat memakai angka, isi metric_value yang mendukung angka tersebut
   dan tandai verified hanya setelah memastikan kebenarannya.

Kalimat yang ingin diperbaiki bahasanya disunting di Career Profile terlebih dulu.
Fakta sumber harus tetap benar meskipun belum ada pemeriksaan semantik independen.

## Coba satu lowongan

1. Buka **Job Inbox**, simpan URL dan paste deskripsi lengkap. Ini cukup untuk
   percobaan pertama; extension dan HP tetap bagian V1 yang perlu diuji tersendiri.
2. Buka Job Detail dan klik Generate CV. Profil dikirim ke provider sesuai desain;
   selesaikan evaluasi model dan keputusan data-retention OPEN-5 sebelum memakai
   data pribadi nyata. Jangan menganggap hasil test model palsu membuktikan kualitas AI.
3. Periksa kalimat, skills, kontak, judul pengalaman dan **Career facts used in
   this version**. Hapus bullet yang tidak ingin digunakan. Edit membuat versi baru.
4. Jika kontak/headings berubah, klik **Update CV from profile** untuk membuat
   versi baru dari profil saat ini. Fakta yang telah berubah/dihapus bisa membuat
   validasi gagal; perbaiki sumber dan buat draft baru, jangan memaksakan export.
5. Konfirmasi checkbox review, klik **Approve CV**, lalu **Export PDF** dan
   **Download PDF**. Buka PDF dan periksa sebelum mengirimnya.
6. Kirim lamaran di situs tujuan secara manual. Kembali ke Job Detail, pilih
   Submitted CV yang benar, lalu **Mark as Applied**. Periksa status dan versinya.
7. Catat Assessment/Interview/Rejected/Offer saat ada perkembangan.

## Ukur sambil memakai

Untuk setiap percobaan, catat lowongan, menit aktif menyiapkan CV dan mengurus
lamaran, banyaknya koreksi, serta satu hambatan utama. Waktu aktif perlu dicatat
manual; selisih timestamp Saved→Applied juga mencakup waktu menunggu.

Prioritaskan hambatan yang berulang. Autofill, ATS adapters dan discovery otomatis
tetap mengikuti data pemakaian setelah V1, sesuai User Plan §17.

## Batas verifikasi saat ini

Pemeriksaan terakhir: **233 test backend lulus**, Ruff lint/format dan mypy lulus,
serta Svelte type-check dan build frontend lulus.

Perbaikan diuji dengan database sementara, profil contoh dan fake LLM. Form HTML
frontend, API, penyimpanan PDF, unduhan dan hubungan versi CV dengan lamaran diuji
melalui HTTP. PDF unduhan dirender dan diperiksa secara visual, termasuk Unicode.
Interaksi browser belum berhasil diotomasi di sesi ini. Belum ada evaluasi model
asli, profil asli yang dilengkapi, pengujian HP, atau lamaran nyata yang dikirim.

## Serah-terima untuk sesi berikutnya

Pekerjaan berikutnya adalah mempersiapkan profil asli dan akses model, mengevaluasi
prompt v2 dengan fakta/lowongan yang representatif, lalu mencoba satu lamaran nyata.
Profil contoh dalam verifikasi tidak dimasukkan ke database utama. Jangan menandai
M6 atau V1 selesai berdasarkan test otomatis. Catatan teknis perubahan ada di
ADR-026; PRD dan scope User Plan v2 tetap menjadi acuan.
