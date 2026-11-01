# OSCAR Job Copilot — Product Plan & User Guide

## 1. Executive Summary

**OSCAR Job Copilot** adalah aplikasi personal untuk mempercepat proses pencarian kerja, penyesuaian CV, pencatatan lamaran, dan analisis progres job hunting.

Tujuan utama versi awal **bukan** membuat bot yang mencari dan melamar pekerjaan sepenuhnya otomatis. Tujuan awal adalah menghilangkan pekerjaan repetitif yang paling banyak membuang waktu, sambil mempertahankan manusia sebagai pengambil keputusan utama.

Prinsip produk:

> **Automatic where automation is reliable, human-assisted where automation is fragile.**

Versi awal harus sudah benar-benar berguna untuk dipakai sehari-hari dalam beberapa bulan ke depan.

---

# 2. Masalah yang Ingin Diselesaikan

Saat mencari kerja, waktu banyak terbuang pada aktivitas yang berulang:

1. menemukan lowongan;
2. menyimpan link lowongan;
3. menyalin job description;
4. mengingat lowongan mana yang sudah dilihat;
5. menyesuaikan CV satu per satu;
6. mengganti nama file CV;
7. mengingat CV versi mana yang dikirim;
8. mengisi form aplikasi yang berulang;
9. mencatat apakah sudah apply atau belum;
10. melacak assessment/interview/rejection/offer;
11. memahami apakah strategi pencarian kerja saat ini efektif;
12. memahami role, skill, dan sumber lowongan mana yang paling menghasilkan respons.

OSCAR Job Copilot bertujuan mengurangi friction tersebut secara bertahap.

---

# 3. Sasaran Produk

## Sasaran utama jangka pendek

Dalam beberapa bulan, aplikasi harus membantu user:

- menyimpan lowongan dari desktop maupun HP dalam hitungan detik;
- menyimpan raw job description tanpa copy-paste manual jika memungkinkan;
- menghasilkan tailored CV berdasarkan lowongan tertentu;
- menjaga CV tetap faktual dan tidak mengarang pengalaman;
- menyimpan versi CV yang digunakan untuk tiap lowongan;
- mencatat status lamaran dengan cepat;
- melihat funnel dan progres job hunting;
- melihat tren role, skill, source, dan conversion;
- mengetahui backlog lowongan yang sudah disimpan tetapi belum dilamar.

## North-star metric

**Human active time per application.**

Tujuan produk adalah terus menurunkan waktu aktif manusia tanpa menurunkan kualitas aplikasi.

Contoh target progresif:

- Manual: 20–40 menit/application
- V1: 3–5 menit/application
- V2/V3: 1–2 menit/application
- Selective automation: hanya beberapa detik intervensi manusia untuk flow yang sudah trusted

---

# 4. Prinsip Produk

## 4.1 Human-in-the-loop dahulu

Pada awalnya user tetap:

- mencari lowongan;
- menentukan apakah tertarik;
- review CV;
- mengisi hal yang tidak pasti;
- menekan Submit;
- mengonfirmasi bahwa aplikasi sudah dikirim.

AI mengerjakan:

- capture;
- penyimpanan;
- parsing dasar;
- tailoring CV;
- pemilihan experience yang relevan;
- tracking;
- analytics;
- saran jawaban;
- pengurangan pekerjaan repetitif.

## 4.2 Progressive autonomy

Automasi ditingkatkan per kemampuan, bukan langsung "full auto".

| Capability | V1 | V2 | V3+ |
|---|---|---|---|
| Save job | Auto | Auto | Auto |
| Parse JD | Basic | Better | High reliability |
| Generate CV | Auto + review | Auto + review | Selective auto |
| Form autofill | Tidak wajib | Assisted | High-confidence auto |
| Submit | Human | Human | Selective auto |
| Job discovery | Human | Assisted | Selective automation |
| Exception handling | Human | Human | Human fallback |

## 4.3 Raw data first

Raw job description dan URL selalu disimpan sebelum parsing.

Parser boleh tidak sempurna pada V1.

```text
Raw Job
   ├── URL
   ├── raw_text
   ├── source
   ├── captured_at
   └── parser_output
```

CV generator tidak boleh bergantung pada parser yang sempurna.

## 4.4 Grounded CV generation

CV tidak boleh dibuat dari imajinasi model.

Sumber fakta utama adalah **Master Career Profile**.

AI hanya boleh:

- memilih fakta yang relevan;
- mengubah urutan;
- memperjelas wording;
- menyesuaikan penekanan;
- meringkas;
- menggabungkan fakta yang sudah ada.

AI tidak boleh:

- mengarang skill;
- mengarang teknologi;
- mengarang tanggung jawab;
- mengarang pencapaian;
- mengarang angka/metric;
- menaikkan lama pengalaman.

## 4.5 Simple frontend first

Stack frontend V1 ditetapkan menjadi **SvelteKit + TypeScript + Tailwind CSS**. Backend menggunakan **FastAPI** dengan **PostgreSQL** sebagai database utama.

Frontend V1 tidak perlu polished.

Prioritas:

1. fungsi;
2. reliability;
3. workflow cepat;
4. data tersimpan benar;
5. mudah dikembangkan;
6. baru setelah itu visual polish.

---

## 4.6 Generic-first capture

V1 tidak dibuat khusus untuk LinkedIn atau JobStreet. Fondasi capture harus generik sehingga lowongan dari sumber mana pun dapat masuk ke satu database dengan kontrak yang sama.

```text
Any Job Source
   ↓
Generic Capture
   ↓
Raw URL/Text Storage
   ↓
Optional Source-Specific Extractor
   ↓
Common Job Model
```

Site-specific extractor hanya dipakai sebagai peningkatan kualitas. Jika extractor tidak ada atau gagal, job tetap disimpan.

Untuk mobile, jika aplikasi sumber hanya membagikan URL/title dan tidak memberikan full JD, job disimpan sebagai **partial capture** dan dapat diperkaya kemudian.

---

# 5. Target User Experience V1

## Desktop

User membuka LinkedIn, JobStreet, Glints, Dealls, Kalibrr, career page perusahaan, atau source lainnya.

```text
Open Job
   ↓
Save to OSCAR Job Copilot
   ↓
Raw JD + metadata tersimpan
   ↓
AI generate tailored CV
   ↓
User review CV
   ↓
Export PDF
   ↓
User apply manual
   ↓
Klik "I Applied"
   ↓
Application tercatat
```

## Mobile

User sedang menggunakan aplikasi LinkedIn/JobStreet.

```text
Share
  ↓
OSCAR Job Copilot
  ↓
Job tersimpan
  ↓
AI memproses
  ↓
CV draft siap
```

User dapat mengumpulkan lowongan sepanjang hari melalui HP lalu melakukan batch application di laptop.

---

# 6. Scope V1 — Wajib Jadi

V1 dianggap selesai hanya jika komponen di bawah benar-benar usable end-to-end.

## P0.1 Universal Job Capture

### Desktop
- browser extension;
- manual URL fallback;
- paste text fallback.

### Mobile
- share URL/text ke app;
- quick save;
- minimal friction.

Data minimal:

- source;
- URL;
- raw text/JD;
- captured_at;
- title jika tersedia;
- company jika tersedia.

## P0.2 Job Inbox

Halaman semua lowongan yang sudah disimpan.

Minimal filter:

- Saved;
- Ready to Apply;
- Applied;
- Assessment;
- Interview;
- Final Interview;
- Rejected;
- Offer;
- Withdrawn;
- Skipped.

Card/list minimal:

- title;
- company;
- source;
- captured date;
- current status;
- CV readiness;
- fit score jika tersedia.

## P0.3 Master Career Profile

Single source of truth untuk semua fakta karier.

Bagian:

- personal/professional summary;
- work experience;
- projects;
- education;
- certifications;
- skills;
- technologies;
- domains;
- accomplishments;
- preferred roles;
- work preferences;
- links;
- application profile.

Setiap achievement sebaiknya bisa menyimpan:

- statement;
- company/project;
- skill tags;
- domain tags;
- evidence/source;
- metric jika memang benar ada.

## P0.4 Tailored CV Engine

Input:

```text
Master Career Profile
+
Raw Job Description
```

Output:

- selected experiences;
- selected bullets;
- reordered skills;
- tailored summary;
- tailored CV preview;
- export PDF;
- version ID.

UI harus menunjukkan:

- JD emphasis;
- experience yang dipilih;
- missing requirements;
- unsupported claims = zero;
- nama/version CV.

Contoh:

```text
CV_J001_v1
CV_J001_v2
```

## P0.5 CV Review & Version Tracking

Untuk setiap job:

- lihat CV draft;
- edit manual;
- regenerate bagian tertentu;
- save version;
- export PDF;
- tandai version yang benar-benar dikirim.

Relasi harus tersimpan:

```text
Job
  ↓
CV Version
  ↓
Application
```

## P0.6 Application Tracker

Status minimal:

```text
SAVED
READY_TO_APPLY
APPLYING
APPLIED
ASSESSMENT
INTERVIEW
FINAL_INTERVIEW
OFFER
REJECTED
WITHDRAWN
SKIPPED
```

User cukup menekan:

- Mark as Applied
- Assessment Received
- Interview
- Rejected
- Offer

Aplikasi tidak perlu mendeteksi semuanya otomatis di V1.

## P0.7 Event History

Jangan hanya menyimpan status terakhir.

Simpan event:

```text
JOB_SAVED
JOB_UPDATED
CV_GENERATED
CV_REGENERATED
CV_EDITED
CV_APPROVED
APPLICATION_STARTED
APPLICATION_SUBMITTED
ASSESSMENT_RECEIVED
INTERVIEW_RECEIVED
INTERVIEW_COMPLETED
FINAL_INTERVIEW
REJECTED
OFFER_RECEIVED
WITHDRAWN
SKIPPED
```

Setiap event punya timestamp.

Ini diperlukan untuk:

- funnel;
- time-to-apply;
- conversion;
- backlog;
- historical analysis;
- future automation learning.

## P0.8 Analytics Dashboard

Dashboard harus masuk V1.

### Overview

- jobs saved;
- ready to apply;
- applied;
- assessment;
- interview;
- final interview;
- offers;
- rejected.

### Funnel

```text
Saved
  ↓
Applied
  ↓
Assessment
  ↓
Interview
  ↓
Final
  ↓
Offer
```

### Conversion

- Applied / Saved
- Assessment / Applied
- Interview / Applied
- Offer / Interview
- Offer / Applied

### Backlog

- CV ready but not applied;
- saved > X days;
- jobs without CV;
- applications needing follow-up.

### Trends

- jobs saved per week;
- applications per week;
- interviews per week;
- saved vs applied;
- source trend;
- role trend.

### Role analytics

- AI Engineer;
- ML Engineer;
- Data Scientist;
- GenAI Engineer;
- other roles.

### Source analytics

- LinkedIn;
- JobStreet;
- Glints;
- Dealls;
- Kalibrr;
- company career pages;
- others.

### Skill trend

Top requirements from jobs user saved:

- Python;
- SQL;
- AWS;
- Docker;
- Kubernetes;
- LLM;
- RAG;
- FastAPI;
- PyTorch;
- Spark;
- etc.

Important:

V1 analytics menggambarkan **sample lowongan yang user capture**, bukan keseluruhan market.

### Productivity

- median saved → CV ready;
- median saved → applied;
- applications per week;
- estimated time saved;
- backlog size.

---

# 7. P1 — Penting tetapi Tidak Boleh Menghambat V1

## Basic Job Parser

Tujuan:

- title;
- company;
- location;
- work mode;
- seniority;
- salary jika ada;
- required skills;
- preferred skills;
- experience years.

Tidak perlu sempurna.

Jika confidence rendah, user bisa melakukan quick correction.

## Basic Fit Score

Tidak perlu menjadi model canggih.

Awal:

- hard requirements;
- technical match;
- seniority;
- domain;
- work mode/location;
- missing skills.

Fit score hanya decision support, bukan penentu otomatis.

## Application Question Assistant

Simpan common answers:

- notice period;
- expected salary;
- current salary jika user memilih menyimpan;
- work authorization;
- relocation;
- location;
- LinkedIn;
- GitHub;
- portfolio;
- years of experience;
- career summary.

Custom question:

- AI generate draft;
- human review.

---

# 8. P2 — Setelah V1 Stabil

## Autofill

Autofill bukan blocker V1.

Target:

- name;
- email;
- phone;
- location;
- LinkedIn;
- GitHub;
- education;
- simple work authorization;
- CV upload.

Custom/ambiguous question tetap human review.

## Browser Application Assistant

Saat application page dibuka:

```text
12 fields detected
8 can autofill
2 have suggested answers
2 need human input
```

---

# 9. P3 — ATS-Specific Automation

Bangun adapter berdasarkan data penggunaan nyata.

Prioritas ditentukan dari:

- berapa banyak application memakai ATS tertentu;
- berapa banyak waktu user terbuang;
- seberapa stabil flow tersebut.

Contoh:

- Greenhouse;
- Lever;
- Ashby;
- Workday;
- SmartRecruiters;
- generic forms.

Interface konseptual:

```text
detect()
extract_fields()
map_profile()
fill_form()
upload_cv()
answer_questions()
detect_submission()
```

---

# 10. P4 — Selective Autonomous Application

Hanya untuk flow:

- permitted;
- tested;
- high reliability;
- high confidence;
- clear user preferences.

Jika ada:

- CAPTCHA;
- unknown flow;
- ambiguous question;
- legal declaration;
- salary ambiguity;
- authentication issue;
- bot challenge;

maka:

```text
PAUSE
→ HUMAN_REQUIRED
→ user handles exception
→ RESUME
```

Tujuan bukan bypass anti-bot.

Tujuan adalah memaksimalkan automation melalui jalur yang stabil dan diperbolehkan.

---

# 11. P5 — Autonomous Discovery

Baru dilakukan setelah V1–V4 menghasilkan data nyata.

Sistem dapat belajar:

- role yang paling sering user save;
- role dengan interview conversion terbaik;
- skill gap;
- source dengan conversion terbaik;
- location/work mode preference;
- salary pattern;
- jobs yang kemungkinan besar user sukai.

Kemudian automated collectors dapat ditambahkan hanya untuk source yang stabil dan layak.

---

# 12. Dashboard V1 — Minimum Screen Set

Frontend sederhana tetapi functional.

## Screen 1 — Dashboard
- KPI cards;
- funnel;
- saved vs applied trend;
- source breakdown;
- role breakdown;
- action queue.

## Screen 2 — Job Inbox
- table/list;
- filters;
- status;
- quick actions.

## Screen 3 — Job Detail
- raw JD;
- parsed metadata;
- fit;
- generated CV;
- timeline;
- actions.

## Screen 4 — CV Review
- generated sections;
- edit;
- regenerate;
- save version;
- export PDF.

## Screen 5 — Career Profile
- experiences;
- projects;
- skills;
- application profile.

## Screen 6 — Analytics
- funnel;
- conversion;
- role trend;
- source trend;
- skill trend;
- productivity.

## Screen 7 — Settings
- profile;
- default CV preferences;
- data export;
- integrations.

---

# 13. Data Model Konseptual

Core entities:

```text
User
CareerProfile
CareerExperience
CareerProject
CareerAchievement
CareerSkill

Job
JobRawSnapshot
JobParsedData
JobSkill
JobEvent

CVVersion
CVSection
CVGenerationRun

Application
ApplicationEvent
ApplicationAnswer

Source
Company
RoleCategory

AnalyticsSnapshot (optional)
```

Important relation:

```text
Job
 ├── RawSnapshot
 ├── ParsedData
 ├── CVVersion[]
 ├── JobEvent[]
 └── Application
       └── ApplicationEvent[]
```

---

# 14. Non-Goals V1

V1 tidak perlu:

- perfect parser;
- beautiful UI;
- mass scraping;
- anti-bot circumvention;
- full auto apply;
- advanced recommendation;
- model training;
- complex ATS adapters;
- sophisticated mobile app;
- universal form automation.

---

# 15. Definition of Done V1

V1 baru dianggap selesai ketika:

1. Job dari desktop dapat disimpan dalam beberapa detik.
2. Job dari HP dapat di-share ke sistem dengan friction rendah.
3. Raw JD selalu tersimpan.
4. CV dapat dibuat langsung dari raw JD + career profile.
5. Generated CV tidak menambahkan unsupported claims.
6. User dapat review/edit/export PDF.
7. CV version per job tersimpan.
8. User dapat menandai Applied/Interview/Rejected/Offer.
9. Semua perubahan status menghasilkan event timestamp.
10. Dashboard menampilkan funnel dan backlog dengan benar.
11. Analytics menunjukkan source/role/skill trends.
12. Workflow sudah digunakan pada real jobs.

Target awal praktis:

- >= 50 real jobs captured;
- >= 25 real applications tracked;
- median tailored CV preparation < 2 menit;
- human active time per application mendekati 3–5 menit;
- zero known fabricated experience in final exported CV.

---

# 16. Product KPIs

## Primary
- Human active minutes/application
- Applications/week
- Saved → Applied conversion
- Applied → Interview conversion
- Interview → Offer conversion

## Efficiency
- Time saved → CV ready
- Time saved → applied
- CV regeneration rate
- application backlog

## Quality
- CV factuality
- user edit rate
- parser correction rate
- fit score usefulness

## Automation maturity
- % workflow automated
- human interventions/application
- success rate per adapter
- failure rate per capability

---

# 17. Development Strategy

Gunakan iterative development.

```text
Build
 ↓
Use on real jobs
 ↓
Capture failures
 ↓
Prioritize bottlenecks
 ↓
Fix / automate
 ↓
Measure improvement
 ↓
Repeat
```

Roadmap tidak boleh hanya didasarkan pada perkiraan teknis.

Setelah V1, fitur berikutnya dipilih berdasarkan data nyata:

- jika application form paling memakan waktu → bangun autofill;
- jika CV review paling memakan waktu → improve CV generation;
- jika discovery terlalu sedikit → improve source collection;
- jika Workday paling menyiksa → build Workday assistant;
- jika banyak save tetapi sedikit apply → fokus backlog workflow.

---

# 18. Security & Privacy

Karena data karier dan aplikasi bersifat pribadi:

- credentials jangan disimpan plaintext;
- PII harus dibatasi;
- secrets via environment/secrets manager;
- audit critical actions;
- export/delete user data;
- avoid storing password situs pekerjaan jika tidak diperlukan;
- raw page capture harus dibatasi ke halaman job/application yang memang relevan;
- sensitive application answers harus bisa ditandai private.

---

# 19. Product Vision

```text
V1
Personal Job Search Operating System
        ↓
V2
Smart Application Assistant
        ↓
V3
ATS-Aware Application Copilot
        ↓
V4
Selectively Autonomous Job Agent
        ↓
V5
Adaptive Career Agent
```

Goal akhirnya bukan sekadar "apply sebanyak mungkin".

Goal:

> Membantu user menemukan pekerjaan yang relevan, membuat aplikasi berkualitas dengan lebih cepat, memahami strategi job hunting secara data-driven, dan secara progresif mengurangi pekerjaan manual yang repetitif.
