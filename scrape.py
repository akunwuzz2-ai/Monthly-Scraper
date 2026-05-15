import cloudscraper
import pandas as pd
import time
import re
import os

def scrape_atr_bpn_final():
    # Menghapus file lama agar fresh
    if os.path.exists('berita-mei-2026.csv'):
        os.remove('berita-mei-2026.csv')

    # Menggunakan cloudscraper dengan request khusus untuk bypass 403
    scraper = cloudscraper.create_scraper(
        delay=10, 
        browser={
            'browser': 'chrome',
            'platform': 'windows',
            'mobile': False
        }
    )

    # Headers yang sangat spesifik meniru browser Chrome Windows
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36',
        'Accept': 'application/json, text/plain, */*',
        'Accept-Language': 'id-ID,id;q=0.9,en-US;q=0.8,en;q=0.7',
        'Referer': 'https://www.atrbpn.go.id/berita',
        'X-Requested-With': 'XMLHttpRequest',
        'Sec-Ch-Ua': '"Chromium";v="124", "Google Chrome";v="124", "Not-A.Brand";v="99"',
        'Sec-Ch-Ua-Mobile': '?0',
        'Sec-Ch-Ua-Platform': '"Windows"',
    }

    target_month = "05"
    target_year = "2026"
    results = []

    print(f"📅 MENGHUBUNGI SERVER ATR/BPN...")

    try:
        # Langkah 1: Pemanasan (Warm-up) untuk mendapatkan cookies
        # Kita buka halaman depan dulu
        print("💡 Melakukan handshake dengan server...")
        scraper.get("https://www.atrbpn.go.id/", headers=headers, timeout=20)
        time.sleep(5)

        # Langkah 2: Tembak API List
        # Kita gunakan endpoint publikasi yang mungkin lebih longgar proteksinya
        api_url = "https://www.atrbpn.go.id/items/berita?sort=-tanggal_rilis&limit=30&fields=id,judul,tanggal_rilis,slug,konten"
        
        response = scraper.get(api_url, headers=headers, timeout=30)
        
        if response.status_code != 200:
            print(f"❌ Gagal Total. Server tetap memberikan status: {response.status_code}")
            # Jika 403 lagi, kita coba metode darurat: ambil dari HTML mentah tanpa API
            return scrape_fallback_html(scraper, headers, target_month, target_year)

        data = response.json().get('data', [])
        print(f"🔍 Server merespons. Memeriksa {len(data)} data berita...")

        for item in data:
            tgl = item.get('tanggal_rilis', '')
            if tgl and tgl.startswith(f"{target_year}-{target_month}"):
                judul = item.get('judul', 'Tanpa Judul')
                print(f"✅ Menemukan: {judul[:50]}...")
                
                # Bersihkan HTML dari konten
                raw_konten = item.get('konten', '')
                clean_konten = re.sub(r'<[^>]+>', '', raw_konten)
                clean_konten = re.sub(r'\s+', ' ', clean_konten).strip()

                results.append({
                    "judul": judul,
                    "tanggal": tgl,
                    "url": f"https://www.atrbpn.go.id/berita/detail/{item.get('slug')}",
                    "konten": clean_content_safety(clean_konten)
                })

    except Exception as e:
        print(f"💥 Terjadi kesalahan teknis: {e}")

    # Simpan hasil
    save_to_csv(results)

def scrape_fallback_html(scraper, headers, month, year):
    print("⚠️ Mencoba metode Fallback (HTML Parsing)...")
    try:
        res = scraper.get("https://www.atrbpn.go.id/berita", headers=headers, timeout=30)
        # Tambahkan logika parsing BeautifulSoup sederhana di sini jika perlu
        # Tapi jika API saja 403, biasanya HTML juga akan kena tantangan Cloudflare (JS Challenge)
        print("❌ Metode Fallback juga terhambat proteksi tingkat tinggi.")
    except:
        pass

def clean_content_safety(text):
    # Mengambil 500 kata pertama agar CSV tidak rusak
    words = text.split()
    return " ".join(words[:500])

def save_to_csv(results):
    if results:
        df = pd.DataFrame(results)
        df.to_csv('berita-mei-2026.csv', index=False, encoding='utf-8', quoting=1)
        print(f"📊 SELESAI: {len(results)} data berhasil disimpan ke CSV.")
    else:
        print("📊 SELESAI: Tidak ada data yang bisa diambil.")

if __name__ == "__main__":
    scrape_atr_bpn_final()
