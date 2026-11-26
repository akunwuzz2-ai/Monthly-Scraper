# Auto Scraper Berita ATR/BPN

Paket otomatis untuk mengambil berita Kementerian ATR/BPN berdasarkan bulan & tahun berjalan dan menampilkannya di GitHub Pages.

## Isi Paket
- `scrape.py`: Script scraper otomatis yang menghasilkan file `berita-YYYY-MM.csv` dengan kolom `judul`, `tanggal`, `url`, `gambar`, dan `content`.
- `index.html`: Halaman web monitoring berita yang otomatis mendeteksi bulan & tahun berjalan serta membaca `berita-YYYY-MM.csv`.
- `requirements.txt`: Daftar library Python yang dibutuhkan.
- `.github/workflows/scrape.yml`: Jadwal otomatis GitHub Actions setiap hari pukul 08:00 WIB (`0 1 * * *` UTC) sekaligus mendukung pemanggilan manual (`Run workflow`).

## Cara Pakai
1. Ekstrak seluruh isi file ZIP ini (termasuk folder `.github/workflows/`).
2. Unggah/timpa seluruh file ke repositori GitHub Anda (`Monthly-Scraper` atau repositori baru).
3. Pastikan di **Settings > Actions > General > Workflow permissions** terpilih **Read and write permissions**.
4. Aktifkan **Settings > Pages** dari branch `main` folder `/ (root)`.
