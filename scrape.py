import cloudscraper
import pandas as pd
import json
import time

def scrape_atr_bpn_api():
    # Inisialisasi scraper untuk bypass proteksi Cloudflare
    scraper = cloudscraper.create_scraper()
    
    target_month = "05"
    target_year = "2026"
    results = []

    print(f"📅 START SCRAPING MEI 2026 (via Directus API)")

    # 1. Endpoint API untuk mengambil daftar berita terbaru
    # Kita menggunakan limit 50 untuk memastikan berita bulan Mei ter-cover
    api_list_url = "https://www.atrbpn.go.id/items/berita?sort=-tanggal_rilis&limit=50&fields=id,judul,tanggal_rilis,slug"

    try:
        response = scraper.get(api_list_url, timeout=30)
        if response.status_code != 200:
            print(f"❌ Gagal akses API List. Status: {response.status_code}")
            return

        data_berita = response.json().get('data', [])
        print(f"🔍 Ditemukan {len(data_berita)} berita terbaru di server.")

        for berita in data_berita:
            # Format tanggal dari API biasanya YYYY-MM-DD
            tgl_rilis = berita.get('tanggal_rilis', '')
            if not tgl_rilis: continue
            
            # Cek kecocokan bulan dan tahun
            # Contoh tgl_rilis: "2026-05-15"
            tahun_api = tgl_rilis.split('-')[0]
            bulan_api = tgl_rilis.split('-')[1]

            if bulan_api == target_month and tahun_api == target_year:
                judul = berita.get('judul')
                slug = berita.get('slug')
                berita_id = berita.get('id')
                
                # URL halaman berita asli (untuk referensi di CSV)
                url_web = f"https://www.atrbpn.go.id/berita/detail/{slug}"
                
                print(f"➡️ Mengambil konten: {judul[:50]}...")

                # 2. Ambil konten detail menggunakan endpoint yang kamu temukan
                # Catatan: Kita sesuaikan parameter fields-nya agar mendapatkan konten teks
                api_detail_url = f"https://www.atrbpn.go.id/items/berita/{berita_id}?fields=konten"
                
                try:
                    detail_res = scraper.get(api_detail_url, timeout=20)
                    detail_data = detail_res.json().get('data', {})
                    raw_content = detail_data.get('konten', '')

                    # Konten dari API biasanya berbentuk HTML, kita bersihkan sedikit
                    # (Menghapus tag HTML sederhana agar teksnya bersih di CSV)
                    import re
                    clean_content = re.sub('<[^<]+?>', '', raw_content)

                    results.append({
                        "judul": judul,
                        "tanggal": tgl_rilis,
                        "url": url_web,
                        "konten": clean_content.strip()
                    })
                    
                    time.sleep(1) # Jeda singkat
                except Exception as e:
                    print(f"   ❌ Gagal ambil detail ID {berita_id}: {e}")

    except Exception as e:
        print(f"💥 Error Utama: {e}")

    # 3. Simpan hasil
    if results:
        df = pd.DataFrame(results)
        df.to_csv('berita-mei-2026.csv', index=False, encoding='utf-8', quoting=1)
        print(f"✅ BERHASIL! {len(results)} data dari API tersimpan.")
    else:
        print("📊 SELESAI. Tidak ada data yang cocok dengan kriteria API.")

if __name__ == "__main__":
    scrape_atr_bpn_api()
