import os
import re
import time
from datetime import datetime
import cloudscraper
import pandas as pd


def clean_content_safety(text: str) -> str:
    words = text.split()
    return " ".join(words[:500])


def save_to_csv(results: list, csv_filename: str) -> None:
    if results:
        df = pd.DataFrame(results, columns=["judul", "tanggal", "url", "gambar", "content"])
        df.to_csv(csv_filename, index=False, encoding="utf-8", quoting=1)
        print(f"📊 SELESAI: {len(results)} data berhasil disimpan ke {csv_filename}.")
    else:
        df = pd.DataFrame(columns=["judul", "tanggal", "url", "gambar", "content"])
        df.to_csv(csv_filename, index=False, encoding="utf-8", quoting=1)
        print(f"📊 SELESAI: Tidak ada data baru. File {csv_filename} tetap diperbarui.")


def scrape_atr_bpn_auto():
    now = datetime.now()
    target_month = os.getenv("TARGET_MONTH", now.strftime("%m"))
    target_year = os.getenv("TARGET_YEAR", now.strftime("%Y"))
    csv_filename = f"berita-{target_year}-{target_month}.csv"

    if os.path.exists(csv_filename):
        os.remove(csv_filename)

    scraper = cloudscraper.create_scraper(
        delay=10,
        browser={
            "browser": "chrome",
            "platform": "windows",
            "mobile": False,
        },
    )

    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
        "Accept": "application/json, text/plain, */*",
        "Accept-Language": "id-ID,id;q=0.9,en-US;q=0.8,en;q=0.7",
        "Referer": "https://www.atrbpn.go.id/berita",
        "X-Requested-With": "XMLHttpRequest",
        "Sec-Ch-Ua": '"Chromium";v="124", "Google Chrome";v="124", "Not-A.Brand";v="99"',
        "Sec-Ch-Ua-Mobile": "?0",
        "Sec-Ch-Ua-Platform": '"Windows"',
    }

    results = []
    print(f"📅 MENGHUBUNGI SERVER ATR/BPN (Periode {target_month}/{target_year})...")

    try:
        print("💡 Melakukan handshake dengan server...")
        scraper.get("https://www.atrbpn.go.id/", headers=headers, timeout=20)
        time.sleep(5)

        api_url = (
            "https://www.atrbpn.go.id/items/berita"
            "?sort=-tanggal_rilis&limit=50&fields=id,judul,tanggal_rilis,slug,konten,gambar"
        )
        response = scraper.get(api_url, headers=headers, timeout=30)

        if response.status_code != 200:
            print(f"❌ Gagal mengambil API. Status: {response.status_code}")
            save_to_csv(results, csv_filename)
            return

        data = response.json().get("data", [])
        print(f"🔍 Server merespons. Memeriksa {len(data)} data berita...")

        for item in data:
            tgl_raw = str(item.get("tanggal_rilis", "") or "")
            cocok_iso = tgl_raw.startswith(f"{target_year}-{target_month}")
            cocok_id = tgl_raw.endswith(f"/{target_month}/{target_year}")

            if cocok_iso or cocok_id:
                judul = item.get("judul", "Tanpa Judul")
                raw_konten = item.get("konten", "") or ""
                clean_konten = re.sub(r"<[^>]+>", "", raw_konten)
                clean_konten = re.sub(r"\s+", " ", clean_konten).strip()

                gambar_id = item.get("gambar", "")
                gambar_url = ""
                if isinstance(gambar_id, str) and gambar_id.startswith("http"):
                    gambar_url = gambar_id
                elif gambar_id:
                    gambar_url = f"https://www.atrbpn.go.id/assets/{gambar_id}"

                slug = item.get("slug", "")
                url_berita = f"https://www.atrbpn.go.id/berita/{slug}" if slug else "https://www.atrbpn.go.id/berita"

                results.append({
                    "judul": judul,
                    "tanggal": tgl_raw,
                    "url": url_berita,
                    "gambar": gambar_url,
                    "content": clean_content_safety(clean_konten),
                })

    except Exception as e:
        print(f"💥 Terjadi kesalahan teknis: {e}")

    save_to_csv(results, csv_filename)


if __name__ == "__main__":
    scrape_atr_bpn_auto()
