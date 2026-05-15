import cloudscraper
import pandas as pd
import json
import time
import re

def scrape_atr_bpn_api():
    # Inisialisasi scraper
    scraper = cloudscraper.create_scraper()
    
    # Tambahkan Headers agar terlihat seperti akses dari browser asli di website mereka
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36',
        'Accept': 'application/json, text/plain, */*',
        'Accept-Language': 'id-ID,id;q=0.9,en-US;q=0.8,en;q=0.7',
        'Referer': 'https://www.atrbpn.go.id/berita',
        'Origin': 'https://www.atrbpn.go.id',
        'Sec-Fetch-Dest': 'empty',
        'Sec-Fetch-Mode': 'cors',
        'Sec-Fetch-Site': 'same-origin',
        'Connection': 'keep-alive'
    }
    
    target_month = "05"
    target_year = "2026"
    results = []

    print(f"📅 START SCRAPING MEI 2026 (Refined API Request)")

    # Gunakan endpoint yang sedikit berbeda atau tambahkan parameter pencarian
    api_list_url = "https://www.atrbpn.go.id/items/berita?sort=-tanggal_rilis&limit=25&fields=id,judul,tanggal_rilis,slug"

    try:
        # Kirim permintaan dengan headers lengkap
        response = scraper.get(api_list_url, headers=headers, timeout=30)
        
        if response.status_code == 403:
            print("❌ Masih kena 403. Server memblokir akses otomatis.")
            print("💡 Mencoba akses melalui URL utama terlebih dahulu untuk mendapatkan session...")
            scraper.get("https://www.atrbpn.go.id/berita", headers=headers)
            time.sleep(5)
            response = scraper.get(api_list_url, headers=headers, timeout=30)

        if response.status_code != 200:
            print(f"❌ Gagal akses API. Status: {response.status_code}")
            return

        data_berita = response.json().get('data', [])
        print(f"🔍 Ditemukan {len(data_berita)} berita terbaru.")

        for berita in data_berita:
            tgl_rilis = berita.get('tanggal_rilis', '')
            if not tgl_rilis: continue
            
            tahun_api = tgl_rilis.split('-')[0]
            bulan_api = tgl_rilis.split('-')[1]

            if bulan_api == target_month and tahun_api == target_year:
                judul = berita.get('judul')
                slug = berita.get('slug')
                berita_id = berita.get('id')
                url_web = f"https://www.atrbpn.go.id/berita/detail/{slug}"
                
                print(f"➡️ Ambil detail: {judul[:50]}...")

                # Detail endpoint
                api_detail_url = f"https://www.atrbpn.go.id/items/berita/{berita_id}?fields=konten"
                
                try:
                    detail_res = scraper.get(api_detail_url, headers=headers, timeout=20)
                    detail_data = detail_res.json().get('data', {})
                    raw_content = detail_data.get('konten', '')

                    # Pembersihan HTML yang lebih rapi
                    clean_content = re.sub(r'<[^>]+>', '', raw_content) # Hapus semua tag HTML
                    clean_content = re.sub(r'\s+', ' ', clean_content).strip() # Rapikan spasi

                    results.append({
                        "judul": judul,
                        "tanggal": tgl_rilis,
                        "url": url_web,
                        "konten": clean_content
                    })
                    time.sleep(2) 
                except:
                    continue

    except Exception as e:
        print(f"💥 Error: {e}")

    if results:
        df = pd.DataFrame(results)
        df.to_csv('berita-mei-2026.csv', index=False, encoding='utf-8', quoting=1)
        print(f"✅ BERHASIL! {len(results)} data tersimpan.")
    else:
        print("📊 Selesai. Tidak ada data yang ditemukan.")

if __name__ == "__main__":
    scrape_atr_bpn_api()
