"""
Scraper berita Kementerian ATR/BPN (https://www.atrbpn.go.id/berita)

Hasil: berita-YYYY-MM.csv dengan kolom judul, tanggal, url, gambar, content.

Cara kerja:
- Tanpa TARGET_MONTH/TARGET_YEAR  -> bulan berjalan + bulan sebelumnya (WIB).
- Dengan TARGET_MONTH / TARGET_YEAR -> hanya periode itu.
- Berita yang sudah ada di CSV (url sama, isi sudah terisi) tidak diunduh ulang.
  Berita yang isinya masih kosong akan dicoba lagi di run berikutnya.
- Kalau situs tidak bisa diakses, script keluar dengan kode 1 (job merah di Actions)
  dan TIDAK menimpa CSV lama.

Pengambilan isi berita (parse_detail) memakai beberapa cara berurutan:
  1. div.prose berisi <p> (struktur halaman ATR/BPN yang sebenarnya).
  2. Data JSON/RSC yang disisipkan Next.js (self.__next_f / __NEXT_DATA__).
  3. Blok teks umum di halaman (p, li, blockquote, div berisi teks).
  4. JSON-LD (articleBody).
  5. Meta description (cuplikan singkat, pilihan terakhir).
"""
import json
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
MAX_WORDS = 600        # batas panjang isi berita yang disimpan
MIN_GOOD = 300         # isi dianggap "cukup" kalau minimal sekian karakter

BULAN = {
    "januari": 1, "februari": 2, "maret": 3, "april": 4, "mei": 5, "juni": 6,
    "juli": 7, "agustus": 8, "september": 9, "oktober": 10, "november": 11, "desember": 12,
}
DATE_RE = re.compile(r"(\d{1,2})\s+(" + "|".join(BULAN) + r")\s+(\d{4})", re.I)
LINK_RE = re.compile(r"^(?:https://www\.atrbpn\.go\.id)?/berita/[^/?#]+/?$")
COLUMNS = ["judul", "tanggal", "url", "gambar", "content"]

# Teks yang bukan isi berita (menu, footer, kredit penulis, dsb.)
BOILERPLATE = (
    "hadir untuk memberikan pelayanan", "jl. sisingamangaraja", "chat only",
    "surat@atrbpn", "open main menu", "kontak & alamat", "social media",
    "bagikan", "penulis", "editor", "fotografer",
)


def clean_content_safety(text: str, max_words: int = MAX_WORDS) -> str:
    """Batasi jumlah kata tetapi pertahankan pemisah paragraf."""
    out, count = [], 0
    for para in re.split(r"\n+", text or ""):
        words = para.split()
        if not words:
            continue
        if count + len(words) > max_words:
            out.append(" ".join(words[: max_words - count]))
            break
        out.append(" ".join(words))
        count += len(words)
    return "\n\n".join(out)


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


# ---------------------------------------------------------------------------
# Pengambilan isi berita
# ---------------------------------------------------------------------------
def _is_boilerplate(text: str) -> bool:
    low = text.lower()
    return any(b in low for b in BOILERPLATE) and len(text) < 200


def _is_noise_para(p) -> bool:
    """Paragraf yang bukan isi berita: hashtag, footer Biro Humas, keterangan foto."""
    t = p.get_text(" ", strip=True)
    if t.startswith("#") or t.startswith("Biro Hubungan Masyarakat"):
        return True
    if "italic" in (p.get("class") or []):
        return True
    if p.find_parent(class_="social-auto-list"):
        return True
    # keterangan foto: seluruh isi paragraf dibungkus <em>/<i>
    em_text = " ".join(e.get_text(" ", strip=True) for e in p.find_all(["em", "i"]))
    return bool(em_text) and em_text.replace(" ", "") == t.replace(" ", "")


def _html_to_paragraphs(fragment: str) -> list:
    """Ubah potongan HTML menjadi daftar paragraf teks."""
    frag = BeautifulSoup(fragment, "html.parser")
    pr = _from_prose(frag)                      # struktur div.prose, kalau ada
    if pr:
        return pr
    paras = []
    blocks = frag.find_all(["p", "li", "blockquote", "h2", "h3", "h4"])
    if blocks:
        for b in blocks:
            if b.name == "p" and _is_noise_para(b):
                continue
            t = b.get_text(" ", strip=True)
            if len(t) > 20:
                paras.append(t)
    else:
        t = frag.get_text("\n", strip=True)
        paras = [x.strip() for x in t.split("\n") if len(x.strip()) > 20]
    return paras


def _dedupe(paras: list) -> list:
    seen, out = set(), []
    for p in paras:
        key = " ".join(p.split())
        if key and key not in seen:
            seen.add(key)
            out.append(key)
    return out


def _from_prose(soup) -> list:
    """Cara 0: div.prose berisi <p> isi berita (struktur halaman ATR/BPN).
    Dicari di seluruh dokumen, bukan hanya di <main>/<article>, karena Next.js
    kadang menaruh isi di luar elemen itu. Div prose milik keterangan foto
    (miring/italic) dan hashtag/footer dilewati."""
    best = []
    for div in soup.find_all("div"):
        classes = div.get("class") or []
        if "prose" not in classes or "italic" in classes:
            continue
        paras = []
        for p in div.find_all("p"):
            if _is_noise_para(p):
                continue                                # hashtag, footer Humas, caption
            t = p.get_text(" ", strip=True)
            if len(t) < 20:
                continue
            paras.append(t)
        paras = _dedupe(paras)
        if sum(len(x) for x in paras) > sum(len(x) for x in best):
            best = paras
    return best


def _from_dom(soup) -> list:
    """Cara 1: kumpulkan blok teks dari halaman (setelah membuang menu/footer)."""
    for t in soup(["script", "style", "noscript", "nav", "footer", "header",
                   "aside", "form", "svg", "button", "figcaption"]):
        t.decompose()

    root = soup.body or soup   # seluruh halaman: isi bisa berada di luar <main>
    block_children = ["p", "div", "ul", "ol", "li", "h1", "h2", "h3", "h4",
                      "table", "section", "article"]
    paras = []
    for el in root.find_all(["p", "li", "blockquote", "div", "span"]):
        if el.name in ("div", "span"):
            if el.find(block_children):        # bukan elemen "daun"
                continue
            if el.name == "span" and el.find_parent(["p", "li", "blockquote"]):
                continue
            min_len = 60
        else:
            min_len = 30
        text = el.get_text(" ", strip=True)
        if len(text) < min_len or _is_boilerplate(text):
            continue
        # lewati kalau teks ini sudah termuat di <p>/<li> induknya
        if el.name in ("div", "span") and el.find_parent(["p", "li", "blockquote"]):
            continue
        paras.append(text)
    return _dedupe(paras)


def _next_payload(soup) -> str:
    """Gabungkan semua potongan self.__next_f.push([1, "..."]) milik Next.js."""
    chunks = []
    for s in soup.find_all("script"):
        t = (s.string or s.get_text() or "").strip()
        if "__next_f" not in t:
            continue
        m = re.search(r"self\.__next_f\.push\((\[.*\])\)\s*;?\s*$", t, re.S)
        if not m:
            continue
        try:
            arr = json.loads(m.group(1))
        except Exception:
            continue
        if len(arr) > 1 and isinstance(arr[1], str):
            chunks.append(arr[1])
    return "".join(chunks)


def _json_strings(blob: str):
    """Hasilkan string-string JSON panjang dari sebuah blob teks."""
    for m in re.finditer(r'"((?:[^"\\]|\\.){200,})"', blob):
        try:
            yield json.loads('"' + m.group(1) + '"')
        except Exception:
            continue


def _looks_like_article(s: str) -> bool:
    if s.startswith(("http", "/", "$", "{", "[")) or "/_next/" in s:
        return False
    words = s.split()
    if len(words) < 40:
        return False
    letters = sum(c.isalpha() or c.isspace() for c in s)
    return letters / max(len(s), 1) > 0.85 or "<p" in s


def _from_next(soup) -> list:
    """Cara 2: isi berita yang tertanam di data JSON Next.js."""
    blobs = [_next_payload(soup)]
    nd = soup.find("script", id="__NEXT_DATA__")
    if nd:
        blobs.append(nd.string or nd.get_text() or "")

    best = []
    for blob in blobs:
        if not blob:
            continue
        candidates = []
        # a) HTML mentah lewat dangerouslySetInnerHTML
        for m in re.finditer(r'"__html":("(?:[^"\\]|\\.)*")', blob):
            try:
                candidates.append(json.loads(m.group(1)))
            except Exception:
                pass
        # a2) deretan <p>...</p> mentah (RSC menyimpan teks panjang tanpa tanda kutip)
        raw_ps = re.findall(r"<p[ >].*?</p>", blob, re.S)
        if raw_ps:
            candidates.append("".join(raw_ps))
        # b) string panjang apa pun yang tampak seperti isi artikel
        candidates += [s for s in _json_strings(blob) if _looks_like_article(s)]

        for c in candidates:
            paras = _html_to_paragraphs(c) if "<" in c else \
                [p.strip() for p in re.split(r"\n+", c) if len(p.strip()) > 20]
            paras = [p for p in _dedupe(paras) if not _is_boilerplate(p)]
            if sum(len(p) for p in paras) > sum(len(p) for p in best):
                best = paras
    return best


def _from_jsonld(soup) -> list:
    """Cara 3: JSON-LD (articleBody)."""
    for s in soup.find_all("script", type="application/ld+json"):
        try:
            data = json.loads(s.string or s.get_text() or "")
        except Exception:
            continue
        stack = data if isinstance(data, list) else [data]
        while stack:
            d = stack.pop()
            if isinstance(d, dict):
                body = d.get("articleBody")
                if isinstance(body, str) and len(body) > 100:
                    return [p.strip() for p in re.split(r"\n+", body) if p.strip()]
                stack.extend(v for v in d.values() if isinstance(v, (dict, list)))
            elif isinstance(d, list):
                stack.extend(d)
    return []


def parse_detail(html: str):
    """Ambil gambar utama (og:image) dan isi berita dari halaman detail."""
    soup = BeautifulSoup(html, "html.parser")

    gambar = ""
    og = soup.find("meta", attrs={"property": "og:image"})
    if og and og.get("content"):
        gambar = urljoin(BASE, og["content"])

    desc = ""
    for attrs in ({"property": "og:description"}, {"name": "description"}):
        tag = soup.find("meta", attrs=attrs)
        if tag and tag.get("content") and len(tag["content"].strip()) > 30:
            desc = tag["content"].strip()
            break

    # Ambil data tertanam DULU, karena _from_dom membuang tag <script>.
    results = {}
    results["prose"] = _from_prose(soup)
    results["next"] = _from_next(soup)
    results["jsonld"] = _from_jsonld(soup)
    results["dom"] = _from_dom(soup)   # terakhir: fungsi ini menghapus tag dari soup

    def size(paras):
        return sum(len(p) for p in paras)

    # Urutan prioritas; pakai yang pertama cukup panjang.
    chosen, name = [], ""
    for key in ("prose", "next", "dom", "jsonld"):
        if size(results[key]) >= MIN_GOOD:
            chosen, name = results[key], key
            break
    if not chosen:  # tidak ada yang cukup panjang -> ambil yang terpanjang
        name, chosen = max(results.items(), key=lambda kv: size(kv[1]))
        if size(chosen) < 100:
            chosen, name = ([desc] if desc else []), "meta-description"

    print(f"   📝 isi diambil via '{name}': {size(chosen)} karakter "
          f"(prose={size(results['prose'])}, next={size(results['next'])}, "
          f"dom={size(results['dom'])}, jsonld={size(results['jsonld'])}, desc={len(desc)})")
    return gambar, "\n".join(chosen)


# ---------------------------------------------------------------------------
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
            if not konten:
                print(f"   ⚠️ Isi kosong untuk: {it['url']}")
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
