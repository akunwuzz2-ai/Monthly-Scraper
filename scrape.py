import os
import re
import time
from datetime import datetime, timedelta, timezone
from urllib.parse import urljoin

import cloudscraper
import pandas as pd
from bs4 import BeautifulSoup

BASE = "https://www.atrbpn.go.id"
LIST_URL = BASE + "/berita"
MAX_PAGES = 8          # maksimal halaman daftar yang ditelusuri
DELAY = 1.5            # jeda antar request (detik), supaya tidak membebani server

BULAN = {
    "januari": 1, "februari": 2, "maret": 3, "april": 4, "mei": 5, "juni": 6,
    "juli": 7, "agustus": 8, "september": 9, "oktober": 10, "november": 11, "desember": 12,
}
DATE_RE = re.compile(r"(\d{1,2})\s+(" + "|".join(BULAN) + r")\s+(\d{4})", re.I)
LINK_RE = re.compile(r"^(?:https://www\.atrbpn\.go\.id)?/berita/[^/?#]+/?$")
COLUMNS = ["judul", "tanggal", "url", "gambar", "content"]


def clean_content_safety(text: str) -> str:
    return " ".join(text.split()[:500])


def save_to_csv(results: list, csv_filename: str) -> None:
    df = pd.DataFrame(results, columns=COLUMNS)
    df.to_csv(csv_filename, index=False, encoding="utf-8", quoting=1)
    print(f"📊 SELESAI: {len(results)} data disimpan ke {csv_filename}.")


def fetch(scraper, url: str, retries: int = 3):
    for attempt in range(1, retries + 1):
        try:
            r = scraper.get(url, timeout=30)
            print(f"   GET {url} -> {r.status_code}")
            if r.status_code == 200:
                return r.text
            if r.status_code in (403, 429, 503):
                print(f"   ⚠️ Kemungkinan diblokir. Cuplikan respons: {r.text[:150]!r}")
        except Exception as e:
            print(f"   ⚠️ Percobaan {attempt} gagal: {e}")
        time.sleep(3 * attempt)
    return None


def parse_list(html: str) -> list:
    """Ambil judul, tanggal, dan url dari halaman daftar berita."""
    soup = BeautifulSoup(html, "html.parser")
    items, seen = [], set()
    for a in soup.find_all("a", href=True):
        if not LINK_RE.match(a["href"]):
            continue
        text = a.get_text(" ", strip=True)
        m = DATE_RE.search(text)
        if not m:
            continue
        url = urljoin(BASE, a["href"])
        if url in seen:
            continue
        seen.add(url)

        title = text[: m.start()].strip()
        words = title.split()
        n = len(words)
        if n and n % 2 == 0 and words[: n // 2] == words[n // 2:]:
            title = " ".join(words[: n // 2])  # judul tampil ganda (alt gambar + teks)

        items.append({
            "judul": title,
            "tanggal": m.group(0),
            "url": url,
            "ym": (int(m.group(3)), BULAN[m.group(2).lower()]),
        })
    return items


def parse_detail(html: str):
    """Ambil gambar utama (og:image) dan isi berita dari halaman detail."""
    soup = BeautifulSoup(html, "html.parser")

    gambar = ""
    og = soup.find("meta", attrs={"property": "og:image"})
    if og and og.get("content"):
        gambar = urljoin(BASE, og["content"])

    container = soup.find("article") or soup.find("main") or soup.body or soup
    paragraphs = [p.get_text(" ", strip=True) for p in container.find_all("p")]
    paragraphs = [p for p in paragraphs if len(p) > 30]
    return gambar, " ".join(paragraphs)


def scrape_atr_bpn_auto():
    wib_now = datetime.now(timezone.utc) + timedelta(hours=7)
    # `or` (bukan default getenv) karena GitHub Actions mengirim string kosong
    target_month = (os.getenv("TARGET_MONTH") or wib_now.strftime("%m")).zfill(2)
    target_year = os.getenv("TARGET_YEAR") or wib_now.strftime("%Y")
    target = (int(target_year), int(target_month))
    csv_filename = f"berita-{target_year}-{target_month}.csv"

    scraper = cloudscraper.create_scraper(
        browser={"browser": "chrome", "platform": "windows", "mobile": False}
    )
    scraper.headers.update({"Accept-Language": "id-ID,id;q=0.9,en;q=0.8"})

    print(f"📅 Mengambil berita periode {target_month}/{target_year} dari {LIST_URL}")
    matched = []

    for page in range(1, MAX_PAGES + 1):
        html = fetch(scraper, f"{LIST_URL}?page={page}")
        if not html:
            print("❌ Gagal memuat halaman daftar, berhenti.")
            break
        items = parse_list(html)
        print(f"🔍 Halaman {page}: {len(items)} berita ditemukan")
        if not items:
            break
        matched += [it for it in items if it["ym"] == target]
        if all(it["ym"] < target for it in items):
            break  # sudah melewati periode target (berita urut dari terbaru)
        time.sleep(DELAY)

    results = []
    for it in matched:
        time.sleep(DELAY)
        html = fetch(scraper, it["url"])
        gambar, konten = parse_detail(html) if html else ("", "")
        results.append({
            "judul": it["judul"],
            "tanggal": it["tanggal"],
            "url": it["url"],
            "gambar": gambar,
            "content": clean_content_safety(konten),
        })

    save_to_csv(results, csv_filename)


if __name__ == "__main__":
    scrape_atr_bpn_auto()
