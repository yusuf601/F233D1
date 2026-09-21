# Desain dashboard kualitas udara OpenAQ

Status: disetujui untuk dilanjutkan ke rencana implementasi.

## 1. Tujuan

Proyek ini adalah dashboard kualitas udara untuk tugas kuliah yang dapat dikembangkan menjadi portofolio. Dashboard menampilkan persebaran lokasi pemantauan secara global dan menyediakan statistik PM2.5 yang lebih mendalam untuk Indonesia.

Seluruh layanan yang di-deploy harus dapat memakai paket gratis. Apache Airflow berjalan di laptop pengguna dan hanya memperbarui data ketika laptop aktif. Situs tetap tersedia melalui Netlify dan menampilkan hasil publikasi terakhir ketika Airflow tidak berjalan.

## 2. Batasan dan keputusan utama

- Sumber data adalah OpenAQ API v3 dengan API key.
- Polutan awal adalah PM2.5. Nilai selalu ditampilkan bersama satuannya dan tidak disebut AQI karena tidak ada perhitungan indeks AQI dalam cakupan awal.
- Peta global menunjukkan lokasi yang menyediakan PM2.5. Nilai terbaru dan riwayat hanya ditampilkan untuk Indonesia.
- Riwayat Indonesia dibatasi pada 30 hari.
- Airflow berjalan lokal setiap hari pukul 07.00 WIB dengan `catchup=False` dan dapat dipicu manual sebelum demo.
- Backend tidak menyediakan web API. Airflow menghasilkan JSON statis dan menerbitkannya ke GitHub.
- Netlify membangun dan menerbitkan frontend setiap kali satu versi data baru masuk ke branch `main`.
- Kode frontend dan pipeline berada dalam satu repository, `yusuf601/F233D1`.

## 3. Dasar keputusan dari audit OpenAQ

Audit read-only menemukan sedikitnya 7.000 lokasi PM2.5 global; tujuh halaman berisi penuh masing-masing 1.000 lokasi dan halaman kedelapan dapat diakses. Indonesia memiliki 73 lokasi hasil filter `parameters_id=2` dan `iso=ID`.

Inventaris global membutuhkan sekitar 3,3–4,7 detik dan 1,1–1,3 MB per halaman. Permintaan latest membutuhkan sekitar 0,53–0,87 detik per lokasi. Karena OpenAQ membatasi penggunaan gratis hingga 2.000 request per jam, mengambil latest untuk semua lokasi global tidak layak untuk lingkup tugas ini.

Riwayat sampel Indonesia cukup segar tetapi tidak lengkap: dua sensor Bali hanya memiliki 13/720 dan 21/720 jam, sedangkan satu sensor Jakarta memiliki 158/720 jam. Karena itu, nilai kosong tidak boleh dianggap nol dan statistik 30 hari harus selalu disertai ukuran coverage.

Audit juga menemukan satu lokasi berlabel Indonesia dengan nama atau zona waktu Bulgaria. Pipeline harus memvalidasi kode negara dan koordinat geografis, bukan mempercayai `country.code` saja.

## 4. Arsitektur

```text
OpenAQ API
    |
    v
Airflow lokal + Python
    |  extract, validate, transform, aggregate
    v
JSON staging dan cache lokal
    |
    v
Satu commit atomik ke GitHub branch main
    |
    v
Netlify build React
    |
    v
Dashboard publik
```

Kegagalan Airflow tidak mematikan situs. Netlify tetap menyajikan deployment terakhir yang berhasil. Frontend tidak memanggil OpenAQ secara langsung dan tidak memiliki akses ke API key.

## 5. Struktur repository

```text
F233D1/
├── airflow/
│   ├── dags/
│   ├── pipeline/
│   ├── tests/
│   └── docker-compose.yaml
├── data/
│   ├── cache/
│   └── staging/
├── frontend/
│   ├── public/data/
│   └── src/
│       ├── components/
│       ├── features/map/
│       ├── features/statistics/
│       ├── services/
│       └── types/
├── docs/
├── .env
└── .env.example
```

`data/cache`, `data/staging`, token, log Airflow, dan artefak sementara tidak di-commit. Lima JSON hasil publikasi berada di `frontend/public/data` dan masuk ke Git agar Netlify dapat menyertakannya pada build.

Compose tetap memakai `airflow/.env` untuk nilai lokal seperti `AIRFLOW_UID` dan memuat `../.env` ke container untuk rahasia proyek. Volume tambahan memberikan pipeline akses ke cache, staging, dan output frontend. Contoh DAG bawaan Airflow dinonaktifkan.

## 6. Pipeline Airflow

Satu DAG utama bernama `openaq_air_quality_pipeline` menjalankan alur berikut:

```text
fetch_global_locations
          |
          +--> filter_global_pm25
          |
          +--> validate_indonesia_locations
                         |
                  select_pm25_sensors
                         |
              fetch_indonesia_measurements
                         |
                aggregate_daily_30d
                         |
              calculate_comparison_stats
                         |
                 validate_all_outputs
                         |
                    build_json
                         |
                 publish_to_github
```

Pagination global berlanjut sampai halaman yang jumlah record-nya kurang dari limit, tanpa hard-code jumlah halaman. Lokasi Indonesia lolos bila kode negaranya `ID` dan koordinatnya berada dalam batas geografis Indonesia yang ditetapkan pipeline. Pemeriksaan koordinat adalah filter kewajaran, bukan pengganti geometri batas negara yang presisi.

Jika satu lokasi memiliki beberapa sensor PM2.5, pipeline memilih sensor aktif dengan waktu pengukuran paling baru. ID sensor yang dipilih dicatat agar keputusan dapat diaudit. Pengambilan riwayat menggunakan endpoint agregasi yang tersedia per sensor; bila agregasi yang dibutuhkan tidak tersedia, pipeline mengambil data hourly dan menghitung rata-rata harian sendiri.

Pengambilan per sensor memakai dynamic task mapping dengan maksimal empat task aktif secara bersamaan. Task jaringan memiliki timeout, retry terbatas, dan jeda bertahap. DAG memakai `max_active_runs=1` agar dua publikasi tidak berlomba memperbarui branch yang sama.

## 7. Kontrak JSON

Frontend membaca lima file:

```text
frontend/public/data/
├── manifest.json
├── global-stations.json
├── indonesia-latest.json
├── indonesia-history-30d.json
└── indonesia-comparison.json
```

### `manifest.json`

Menjadi titik masuk frontend dan memuat:

- `schemaVersion`
- `datasetVersion`
- `generatedAt`
- nama sumber
- status setiap bagian data
- jumlah lokasi global dan Indonesia
- jumlah data Indonesia yang fresh, stale, kosong, atau gagal
- nama file data

`datasetVersion` sama untuk seluruh file dalam satu publikasi. Waktu disimpan dalam UTC dan diformat oleh frontend untuk pengguna.

### `global-stations.json`

Berformat GeoJSON `FeatureCollection`. Setiap feature hanya memuat ID lokasi, nama, negara, koordinat, dan penanda ketersediaan PM2.5. File ini tidak menjanjikan nilai terbaru.

### `indonesia-latest.json`

Berformat GeoJSON `FeatureCollection` dengan tambahan ID sensor terpilih, nilai PM2.5, satuan, waktu pengukuran, penyedia, dan status `fresh`, `stale`, atau `unavailable`. Data dianggap fresh bila waktu pengukurannya tidak lebih lama dari 24 jam terhadap waktu kalkulasi pipeline.

### `indonesia-history-30d.json`

Memuat maksimal 30 titik harian per stasiun. Setiap titik berisi tanggal, mean, jumlah sampel, dan coverage. Hari tanpa pengukuran tidak dibuat menjadi nilai nol; frontend menampilkannya sebagai celah.

### `indonesia-comparison.json`

Memuat statistik turunan yang digunakan halaman Indonesia Statistics:

- jumlah seluruh stasiun dan stasiun aktif dalam 24 jam terakhir
- median nilai terbaru dari stasiun aktif
- stasiun dengan nilai terbaru tertinggi dan terendah
- ranking nilai terbaru stasiun aktif
- mean dan maksimum 30 hari per stasiun
- jumlah hari tersedia, jumlah jam observasi, dan coverage per stasiun
- coverage pelaporan per hari untuk kebutuhan visualisasi

Ranking utama memakai nilai terbaru yang masih berada dalam jendela 24 jam. Statistik 30 hari selalu menyertakan coverage karena kelengkapan data antarstasiun berbeda jauh.

## 8. Publikasi GitHub dan Netlify

Pipeline menerbitkan kelima file sebagai satu commit atomik melalui GitHub Git Data API:

1. Membaca SHA branch dan tree terbaru.
2. Membuat blob untuk file yang berubah.
3. Membuat satu tree baru berbasis tree terbaru.
4. Membuat satu commit.
5. Memindahkan reference `main` ke commit baru.

Jika hash seluruh output sama dengan versi yang telah dipublikasikan, task tidak membuat commit. Konflik branch memicu pembacaan ulang reference dan satu kali percobaan ulang. Token fine-grained hanya memiliki izin `Contents: read and write` pada repository ini.

Netlify menggunakan `frontend` sebagai base directory, menjalankan build Vite, dan menerbitkan `frontend/dist`. React Router menggunakan rute `/map` dan `/indonesia`; aturan SPA fallback Netlify mengarahkan rute aplikasi ke `index.html`.

## 9. Antarmuka

Frontend memakai React, TypeScript, Vite, MapLibre GL JS, Apache ECharts, Tailwind CSS, dan Lucide React. Data diambil dengan `fetch`; state server tambahan tidak diperlukan untuk lima file statis.

Navbar memiliki dua halaman utama:

### Map Explorer

Peta global menjadi elemen dominan. MapLibre membaca GeoJSON dan mengelompokkan titik ketika zoom jauh. Halaman menyediakan pencarian stasiun, kontrol fokus Indonesia, waktu pembaruan pipeline, serta panel detail lokasi.

Lokasi global hanya menjelaskan ketersediaan pemantauan PM2.5. Lokasi Indonesia dapat menampilkan nilai terbaru, satuan, waktu pengukuran, status freshness, dan tautan menuju statistik terkait. Pada perangkat seluler, detail muncul di bawah peta agar tidak menutupi peta.

### Indonesia Statistics

Halaman terpisah ini mencegah informasi analitik menumpuk di halaman peta. Isinya:

- kartu ringkasan stasiun aktif, median PM2.5, dan nilai tertinggi
- grafik batang ranking PM2.5 terbaru antarstasiun aktif
- grafik tren 30 hari untuk maksimal tiga stasiun pilihan
- visualisasi coverage untuk menjelaskan ketersediaan data

Nama stasiun, waktu pengukuran, dan coverage tetap terlihat dalam perbandingan. Satu stasiun tidak disebut mewakili seluruh kota atau provinsi.

## 10. Penanganan kegagalan

- HTTP 429 dan error server dicoba ulang dengan jeda bertahap serta menghormati `Retry-After` bila tersedia.
- HTTP 400, 401, atau 403 dan respons yang tidak sesuai kontrak dianggap kesalahan konfigurasi atau skema dan menggagalkan publikasi.
- Kegagalan satu sensor memakai data terakhir dari cache bila tersedia dan menandainya `stale`.
- Lokasi tanpa pengukuran yang valid ditandai `unavailable`, bukan gagal dan bukan bernilai nol.
- Jika inventaris global gagal, pipeline memakai inventaris terakhir. Bila tidak ada cache awal, publikasi dibatalkan.
- Output dibangun di staging. File publik tidak diubah sampai seluruh validasi selesai.
- Kegagalan validasi atau publikasi mempertahankan versi GitHub dan deployment Netlify sebelumnya.
- Frontend menampilkan kondisi loading, data kosong, data lama, dan kegagalan pemuatan secara berbeda.

## 11. Keamanan

- `OPENAQ_API_KEY` dan `GITHUB_DATA_TOKEN` hanya berada di `.env` lokal dan environment container.
- `.env` dan varian lokalnya diabaikan Git. `.env.example` hanya memuat nama variabel tanpa nilai.
- Token tidak dimasukkan ke URL log, exception, XCom, JSON, atau bundle frontend.
- Log request hanya mencatat endpoint tanpa header autentikasi.
- Token GitHub yang pernah dibagikan melalui chat harus diganti sebelum pipeline publikasi digunakan.

## 12. Verifikasi

Pengujian pipeline menggunakan fixture respons OpenAQ agar transformasi dapat diuji tanpa menghabiskan kuota. Kasus utama mencakup pagination, koordinat Indonesia yang salah label, pemilihan beberapa sensor, data kosong, deduplikasi, agregasi harian, coverage, freshness, fallback cache, dan kegagalan autentikasi.

DAG diuji terlebih dahulu dengan task publikasi dinonaktifkan. Setelah output lokal lolos validasi skema, publikasi diuji menggunakan perubahan JSON kecil. Pemeriksaan memastikan kelima file berada dalam satu commit dan Netlify hanya memulai satu deployment.

Frontend harus lolos type-check, lint, dan production build. Pemeriksaan manual mencakup clustering peta, pencarian, fokus Indonesia, ranking, pemilihan tiga stasiun, celah pada grafik, status stale, navigasi langsung ke kedua rute, serta layout desktop dan ponsel. Bundle produksi diperiksa untuk memastikan tidak mengandung API key atau token GitHub.

## 13. Di luar cakupan awal

- Latest dan riwayat seluruh stasiun global
- Data realtime atau pembaruan ketika laptop mati
- Database dan backend API publik
- Prediksi kualitas udara
- Perhitungan AQI
- Akun pengguna, notifikasi, dan personalisasi
- Jaminan bahwa setiap kota Indonesia memiliki stasiun aktif

