import cloudscraper
import pandas as pd
from bs4 import BeautifulSoup
import time
import os

def scrape_atr_bpn():
    # Inisialisasi scraper yang bisa bypass bot-protection
    scraper = cloudscraper.create_scraper(
        browser={
            'browser': 'chrome',
            'platform': 'windows',
            'desktop': True
        }
    )
    
    target_month = "/05/2026"
    results = []

    print("📅 START SCRAPING MEI 2026 (via CloudScraper)")

    try:
        # 1. Ambil halaman daftar berita
        # Gunakan URL publikasi agar lebih spesifik
        url_main = "https://www.atrbpn.go.id/publikasi/berita"
        response = scraper.get(url_main, timeout=30)
        
        if response.status_code != 200:
            print(f"❌ Gagal akses. Status: {response.status_code}")
            return

        soup = BeautifulSoup(response.text, 'html.parser')
        
        # Mencari elemen kartu berita
        items = soup.select(".col-md-3.col-6") or soup.find_all('div', class_='card')
        print(f"🔍 Items ditemukan di halaman utama: {len(items)}")

        for item in items:
            try:
                link_el = item.find('a')
                if not link_el: continue
                
                url = link_el['href']
                # Pastikan URL lengkap
                if not url.startswith('http'):
                    url = "https://www.atrbpn.go.id" + url
                    
                title = link_el.text.strip()
                date_text = item.get_text()

                # Cek apakah berita bulan Mei 2026
                if target_month in date_text:
                    print(f"➡️ Mengambil isi: {title[:50]}...")
                    
                    # 2. Ambil isi detail berita
                    detail_res = scraper.get(url, timeout=20)
                    detail_soup = BeautifulSoup(detail_res.text, 'html.parser')
                    
                    # Cari semua paragraf di dalam artikel
                    # Biasanya berita ada di dalam tag <article> atau div dengan class tertentu
                    content_area = detail_soup.find('article') or detail_soup.find('div', class_='entry-content')
                    
                    if content_area:
                        paragraphs = content_area.find_all('p')
                    else:
                        paragraphs = detail_soup.find_all('p')

                    content = "\n\n".join([p.get_text().strip() for p in paragraphs if len(p.get_text()) > 25])

                    results.append({
                        "judul": title,
                        "tanggal": date_text.strip().split('\n')[0],
                        "url": url,
                        "konten": content
                    })
                    time.sleep(2) # Jeda sopan agar tidak diblokir
            except Exception as e:
                print(f"⚠️ Skip satu item karena error: {e}")
                continue

    except Exception as e:
        print(f"💥 Error Utama: {e}")

    # 3. Simpan hasil ke CSV menggunakan Pandas (lebih aman untuk karakter spesial)
    if results:
        df = pd.DataFrame(results)
        df.to_csv('berita-mei-2026.csv', index=False, encoding='utf-8', quoting=1)
        print(f"✅ BERHASIL! {len(results)} berita Mei 2026 tersimpan di CSV.")
    else:
        print("📊 SELESAI. Tidak ada berita Mei 2026 yang ditemukan hari ini.")

if __name__ == "__main__":
    scrape_atr_bpn()
