"""
Scraper berita Kementerian ATR/BPN (https://www.atrbpn.go.id/berita)

Hasil: berita-YYYY-MM.csv dengan kolom judul, tanggal, url, gambar, content.

Cara kerja:
- Tanpa TARGET_MONTH/TARGET_YEAR  -> bulan berjalan + bulan sebelumnya (WIB).
- Dengan TARGET_MONTH / TARGET_YEAR -> hanya periode itu.
- Berita yang sudah ada di CSV (url sama, isi sudah terisi) tidak diunduh ulang.
- Kalau situs tidak bisa diakses, script keluar dengan kode 1 (job merah di Actions)
  dan TIDAK menimpa CSV lama.
"""
import os
import re
import sys
import time
from datetime import datetime, timedelta, timezone
from urllib.parse import urljoin

import cloudscraper
import pandas as pd
from bs4 import BeautifulSoup

BASE = "https://www.atrbpn.go.id"
LIST_URL = BASE + "/berita"
MAX_PAGES = 40         # batas aman penelusuran halaman daftar
DELAY = 1.5            # jeda antar request (detik)

BULAN = {
    "januari": 1, "februari": 2, "maret": 3, "april": 4, "mei": 5, "juni": 6,
    "juli": 7, "agustus": 8, "september": 9, "oktober": 10, "november": 11, "desember": 12,
}
DATE_RE = re.compile(r"(\d{1,2})\s+(" + "|".join(BULAN) + r")\s+(\d{4})", re.I)
LINK_RE = re.compile(r"^(?:https://www\.atrbpn\.go\.id)?/berita/[^/?#]+/?$")
COLUMNS = ["judul", "tanggal", "url", "gambar", "content"]


def clean_content_safety(text: str) -> str:
    return " ".join(text.split()[:500])


def shift_month(year: int, month: int, delta: int):
    idx = year * 12 + (month - 1) + delta
    return idx // 12, idx % 12 + 1


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


def load_existing(csv_filename: str) -> dict:
    if not os.path.exists(csv_filename):
        return {}
    try:
        df = pd.read_csv(csv_filename, dtype=str).fillna("")
        return {r["url"]: r for r in df.to_dict("records") if r.get("url")}
    except Exception as e:
        print(f"⚠️ Gagal membaca {csv_filename} yang lama: {e}")
        return {}


def determine_targets():
    wib_now = datetime.now(timezone.utc) + timedelta(hours=7)
    # `or` (bukan default getenv) karena GitHub Actions mengirim string kosong
    env_month = (os.getenv("TARGET_MONTH") or "").strip()
    env_year = (os.getenv("TARGET_YEAR") or "").strip()

    if env_month or env_year:
        month = int(env_month) if env_month else wib_now.month
        year = int(env_year) if env_year else wib_now.year
        return [(year, month)]

    cur = (wib_now.year, wib_now.month)
    return [cur, shift_month(*cur, -1)]


def scrape_atr_bpn_auto():
    targets = determine_targets()
    oldest = min(targets)
    print("📅 Periode yang diambil:", ", ".join(f"{m:02d}/{y}" for y, m in targets))

    scraper = cloudscraper.create_scraper(
        browser={"browser": "chrome", "platform": "windows", "mobile": False}
    )
    scraper.headers.update({"Accept-Language": "id-ID,id;q=0.9,en;q=0.8"})

    # 1) Telusuri halaman daftar sampai melewati periode paling lama
    matched = []
    for page in range(1, MAX_PAGES + 1):
        html = fetch(scraper, f"{LIST_URL}?page={page}")
        if not html:
            print("❌ Gagal memuat halaman daftar. CSV lama tidak diubah.")
            sys.exit(1)
        items = parse_list(html)
        print(f"🔍 Halaman {page}: {len(items)} berita ditemukan")
        if not items:
            if page == 1:
                print("❌ Halaman daftar terbuka tapi tidak ada berita yang terbaca "
                      "(struktur HTML berubah atau halaman diblokir). CSV lama tidak diubah.")
                sys.exit(1)
            break
        matched += [it for it in items if it["ym"] in targets]
        if all(it["ym"] < oldest for it in items):
            break
        time.sleep(DELAY)

    # 2) Per periode: ambil detail berita, lalu simpan CSV
    for ym in targets:
        year, month = ym
        csv_filename = f"berita-{year}-{month:02d}.csv"
        existing = load_existing(csv_filename)
        rows = []

        for it in [x for x in matched if x["ym"] == ym]:
            old = existing.get(it["url"])
            if old and old.get("content"):
                rows.append({c: old.get(c, "") for c in COLUMNS})
                continue
            time.sleep(DELAY)
            html = fetch(scraper, it["url"])
            gambar, konten = parse_detail(html) if html else ("", "")
            rows.append({
                "judul": it["judul"],
                "tanggal": it["tanggal"],
                "url": it["url"],
                "gambar": gambar,
                "content": clean_content_safety(konten),
            })

        pd.DataFrame(rows, columns=COLUMNS).to_csv(
            csv_filename, index=False, encoding="utf-8", quoting=1
        )
        print(f"📊 {csv_filename}: {len(rows)} berita")


if __name__ == "__main__":
    scrape_atr_bpn_auto()
