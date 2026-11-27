# Auto Scraper Berita ATR/BPN

Paket otomatis untuk mengambil berita Kementerian ATR/BPN berdasarkan bulan & tahun berjalan dan menampilkannya di GitHub Pages.

## Isi Paket
- `scrape.py`: Script scraper otomatis yang menghasilkan file `berita-YYYY-MM.csv` dengan kolom `judul`, `tanggal`, `url`, `gambar`, dan `content`.
- `scrape_bintan.py`: Scraper berita daerah Kantah Kab. Bintan (`kab-bintan.atrbpn.go.id/berita`) yang menghasilkan `berita-bintan-YYYY-MM.csv`. Memakai Playwright karena situsnya aplikasi JavaScript, dan mengimpor fungsi bantu dari `scrape.py` (kedua file harus berada di folder yang sama).
- `index.html`: Halaman web monitoring berita dengan tab sumber (Pusat / Kantah Bintan) dan menu bulan. Membaca `berita-YYYY-MM.csv` (pusat) dan `berita-bintan-YYYY-MM.csv` (Bintan). Parameter URL: `?s=pusat|bintan&m=YYYY-MM`.
- `requirements.txt`: Daftar library Python yang dibutuhkan.
- `.github/workflows/scrape.yml`: Jadwal otomatis GitHub Actions setiap hari pukul 08:00 WIB (`0 1 * * *` UTC) sekaligus mendukung pemanggilan manual (`Run workflow`).

## Cara Pakai
1. Ekstrak seluruh isi file ZIP ini (termasuk folder `.github/workflows/`).
2. Unggah/timpa seluruh file ke repositori GitHub Anda (`Monthly-Scraper` atau repositori baru).
3. Pastikan di **Settings > Actions > General > Workflow permissions** terpilih **Read and write permissions**.
4. Aktifkan **Settings > Pages** dari branch `main` folder `/ (root)`.

## Kalau scraper Bintan gagal
Job akan merah dan mengunggah artifact `debug-bintan` (HTML halaman + daftar tautan di log). Biasanya cukup menyesuaikan pola tautan di fungsi `norm_url()` atau daftar `NEXT_SELECTORS` di `scrape_bintan.py`. Berita pusat tetap tersimpan.
