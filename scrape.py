"""
Scraper berita daerah: Kantor Pertanahan Kabupaten Bintan
(https://kab-bintan.atrbpn.go.id/berita)

Hasil: berita-bintan-YYYY-MM.csv dengan kolom judul, tanggal, url, gambar, content
(kolom sama dengan scrape.py, hanya nama file berbeda supaya tidak bentrok).

Perbedaan utama dengan scrape.py:
- Situs Bintan adalah aplikasi JavaScript (HTML awalnya kosong), jadi SEMUA halaman
  dibuka lewat browser sungguhan (Playwright), bukan cloudscraper.
- Pola halaman tidak diasumsikan kaku: tautan berita dicari lewat pola /berita/<slug>,
  tanggal dicari dengan beberapa format, dan paginasi dicoba lewat ?page=N lalu
  lewat klik tombol "berikutnya"/scroll.

Cara kerja periode sama dengan scrape.py:
- Tanpa TARGET_MONTH/TARGET_YEAR -> bulan berjalan + bulan sebelumnya (WIB).
- Dengan TARGET_MONTH / TARGET_YEAR -> hanya periode itu.
- Berita yang sudah ada di CSV (url sama, isi sudah terisi) tidak diunduh ulang.
- Kalau daftar berita tidak terbaca, script keluar dengan kode 1, menyimpan
  debug-bintan.html untuk diperiksa, dan TIDAK menimpa CSV lama.
"""
import re
import sys
from urllib.parse import urljoin, urlparse

import pandas as pd
from bs4 import BeautifulSoup

import scrape as pusat  # pakai ulang fungsi bantu dari scrape.py
from scrape import (BULAN, COLUMNS, MIN_GOOD, MIN_REUSE, clean_content_safety,
                    determine_targets, load_existing)

BASE = "https://kab-bintan.atrbpn.go.id"
LIST_URL = BASE + "/berita"
pusat.BASE = BASE        # parse_detail() memakai BASE untuk mengubah og:image relatif
MAX_PAGES = 15           # batas aman penelusuran halaman daftar
MAX_SCROLL = 8           # batas scroll per halaman (untuk daftar "infinite scroll")
DELAY_MS = 1200          # jeda antar halaman (milidetik)
CSV_PREFIX = "berita-bintan"
DEBUG_FILE = "debug-bintan.html"

# Segmen setelah /berita/ yang BUKAN artikel (kategori, tag, dsb.)
SKIP_SEGMENTS = {"kategori", "category", "tag", "tags", "page", "arsip", "archive", "search", "cari"}

# ---------------------------------------------------------------------------
# Tanggal
# ---------------------------------------------------------------------------
MONTH_ALIASES = dict(BULAN)
MONTH_ALIASES.update({
    "jan": 1, "feb": 2, "mar": 3, "apr": 4, "jun": 6, "jul": 7, "agu": 8, "agt": 8,
    "ags": 8, "sep": 9, "sept": 9, "okt": 10, "nov": 11, "des": 12,
    "january": 1, "february": 2, "march": 3, "may": 5, "june": 6, "july": 7,
    "august": 8, "aug": 8, "october": 10, "oct": 10, "december": 12, "dec": 12,
})
_MON = "|".join(sorted(MONTH_ALIASES, key=len, reverse=True))
NAMA_BULAN = {v: k.capitalize() for k, v in BULAN.items()}

DATE_PATTERNS = [
    (re.compile(r"(\d{4})-(\d{2})-(\d{2})"), lambda m: (int(m[1]), int(m[2]), int(m[3]))),
    (re.compile(rf"(\d{{1,2}})\s+({_MON})\.?,?\s+(\d{{4}})", re.I),
     lambda m: (int(m[3]), MONTH_ALIASES[m[2].lower()], int(m[1]))),
    (re.compile(rf"({_MON})\.?\s+(\d{{1,2}}),?\s+(\d{{4}})", re.I),
     lambda m: (int(m[3]), MONTH_ALIASES[m[1].lower()], int(m[2]))),
    (re.compile(r"(\d{1,2})[/.](\d{1,2})[/.](\d{4})"), lambda m: (int(m[3]), int(m[2]), int(m[1]))),
]


def find_date(text: str):
    """Kembalikan (tahun, bulan, hari) pertama yang valid dari sebuah teks, atau None."""
    for rx, conv in DATE_PATTERNS:
        for m in rx.finditer(text or ""):
            try:
                y, mo, d = conv(m)
            except (KeyError, ValueError):
                continue
            if 2000 <= y <= 2100 and 1 <= mo <= 12 and 1 <= d <= 31:
                return (y, mo, d)
    return None


def fmt_date(d) -> str:
    return f"{d[2]} {NAMA_BULAN[d[1]]} {d[0]}"


# ---------------------------------------------------------------------------
# Daftar berita
# ---------------------------------------------------------------------------
def norm_url(href: str):
    """Kembalikan URL artikel yang sudah dinormalkan, atau None kalau bukan artikel."""
    u = urlparse(urljoin(BASE + "/", href or ""))
    if u.netloc != urlparse(BASE).netloc:
        return None
    parts = [p for p in u.path.split("/") if p]
    if len(parts) < 2 or parts[0] != "berita" or parts[1].lower() in SKIP_SEGMENTS:
        return None
    return f"{BASE}/" + "/".join(parts)


def _dedupe_title(title: str) -> str:
    words = title.split()
    n = len(words)
    if n and n % 2 == 0 and words[: n // 2] == words[n // 2:]:
        return " ".join(words[: n // 2])
    return title


def _card_of(a, url):
    """Naik ke pembungkus terbesar yang hanya memuat tautan artikel ini (= 'kartu' berita)."""
    card = a
    for _ in range(6):
        parent = card.parent
        if parent is None or parent.name in ("body", "html"):
            break
        links = {norm_url(x["href"]) for x in parent.find_all("a", href=True)} - {None}
        if links - {url}:
            break
        card = parent
    return card


def _img_src(card) -> str:
    for img in card.find_all("img"):
        for attr in ("src", "data-src", "data-lazy-src"):
            src = (img.get(attr) or "").strip()
            if not src and img.get("srcset"):
                src = img["srcset"].split(",")[0].strip().split(" ")[0]
            if src and not src.startswith("data:"):
                return urljoin(BASE + "/", src)
    return ""


def parse_list(html: str) -> list:
    """Ambil judul, tanggal, gambar, dan url dari halaman daftar berita."""
    soup = BeautifulSoup(html, "html.parser")
    found = {}
    for a in soup.find_all("a", href=True):
        url = norm_url(a["href"])
        if not url:
            continue
        card = _card_of(a, url)

        t = card.find("time")
        date = find_date((t.get("datetime") or "") if t else "") or \
            find_date(t.get_text(" ", strip=True) if t else "") or \
            find_date(card.get_text(" ", strip=True))

        title = ""
        for h in card.find_all(["h1", "h2", "h3", "h4", "h5"]):
            if h.get_text(strip=True):
                title = h.get_text(" ", strip=True)
                break
        if not title:
            title = a.get("title") or a.get_text(" ", strip=True)
            for rx, _ in DATE_PATTERNS:
                title = rx.sub("", title)
        if not title.strip():
            img = card.find("img")
            title = (img.get("alt") if img else "") or ""
        title = _dedupe_title(" ".join(title.split()))

        cur = found.setdefault(url, {"judul": "", "tanggal": None, "url": url, "gambar": ""})
        if len(title) > len(cur["judul"]):
            cur["judul"] = title
        cur["tanggal"] = cur["tanggal"] or date
        cur["gambar"] = cur["gambar"] or _img_src(card)
    return [v for v in found.values() if v["judul"]]


# ---------------------------------------------------------------------------
# Browser
# ---------------------------------------------------------------------------
def launch():
    from playwright.sync_api import sync_playwright
    pw = sync_playwright().start()
    browser = pw.chromium.launch(headless=True)
    ctx = browser.new_context(
        locale="id-ID",
        viewport={"width": 1366, "height": 900},
        user_agent=("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                    "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"),
    )
    return pw, browser, ctx


def goto(page, url: str, wait_selector: str = None):
    print(f"   GET {url}")
    page.goto(url, wait_until="domcontentloaded", timeout=45000)
    try:
        page.wait_for_load_state("networkidle", timeout=20000)
    except Exception:
        pass
    if wait_selector:
        try:
            page.wait_for_selector(wait_selector, timeout=15000)
        except Exception:
            pass
    page.wait_for_timeout(DELAY_MS)


def autoscroll(page):
    """Scroll ke bawah sampai jumlah tautan berita tidak bertambah (infinite scroll)."""
    last = -1
    for _ in range(MAX_SCROLL):
        n = page.locator('a[href*="/berita/"]').count()
        if n == last:
            break
        last = n
        page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
        page.wait_for_timeout(900)


NEXT_SELECTORS = [
    'a[rel="next"]', 'button:has-text("Selanjutnya")', 'a:has-text("Selanjutnya")',
    'button:has-text("Berikutnya")', 'a:has-text("Berikutnya")',
    'button:has-text("Next")', 'a:has-text("Next")', '[aria-label*="next" i]',
    'li.next a', 'a:has-text("›")', 'button:has-text("›")', 'a:has-text("»")',
]


def click_next(page) -> bool:
    for sel in NEXT_SELECTORS:
        try:
            loc = page.locator(sel).first
            if not loc.count() or not loc.is_visible() or not loc.is_enabled():
                continue
            if (loc.get_attribute("aria-disabled") or "") == "true" or \
                    "disabled" in (loc.get_attribute("class") or ""):
                continue
            loc.click()
            try:
                page.wait_for_load_state("networkidle", timeout=15000)
            except Exception:
                pass
            page.wait_for_timeout(DELAY_MS)
            return True
        except Exception:
            continue
    return False


def _sig(items):
    return tuple(i["url"] for i in items)


def iter_list_pages(page):
    """Hasilkan daftar berita halaman demi halaman (?page=N, kalau tidak bisa: klik 'next')."""
    goto(page, LIST_URL, 'a[href*="/berita/"]')
    autoscroll(page)
    items1 = parse_list(page.content())
    yield items1
    if not items1:
        return

    # Mode A: paginasi lewat URL ?page=N
    prev = _sig(items1)
    goto(page, f"{LIST_URL}?page=2", 'a[href*="/berita/"]')
    autoscroll(page)
    items2 = parse_list(page.content())
    if items2 and _sig(items2) != prev:
        print("   ↪ paginasi lewat ?page=N")
        yield items2
        prev = _sig(items2)
        for n in range(3, MAX_PAGES + 1):
            goto(page, f"{LIST_URL}?page={n}", 'a[href*="/berita/"]')
            autoscroll(page)
            items = parse_list(page.content())
            if not items or _sig(items) == prev:
                return
            yield items
            prev = _sig(items)
        return

    # Mode B: klik tombol "berikutnya"
    print("   ↪ ?page=N tidak berubah, coba klik tombol berikutnya")
    goto(page, LIST_URL, 'a[href*="/berita/"]')
    prev = _sig(items1)
    for _ in range(MAX_PAGES - 1):
        if not click_next(page):
            return
        autoscroll(page)
        items = parse_list(page.content())
        if not items or _sig(items) == prev:
            return
        yield items
        prev = _sig(items)


def dump_debug(page, note: str):
    """Simpan HTML + daftar tautan supaya mudah mendiagnosis kalau struktur situs berbeda."""
    html = page.content()
    with open(DEBUG_FILE, "w", encoding="utf-8") as f:
        f.write(html)
    soup = BeautifulSoup(html, "html.parser")
    hrefs = sorted({a["href"] for a in soup.find_all("a", href=True)})
    print(f"❌ {note}")
    print(f"   HTML disimpan di {DEBUG_FILE} ({len(html)} karakter). Tautan yang ada di halaman:")
    for h in hrefs[:60]:
        print("    ", h)


# ---------------------------------------------------------------------------
# Detail berita
# ---------------------------------------------------------------------------
CONTENT_SELECTORS = ["article", "div.prose", '[class*="prose"]', '[class*="content"]',
                     '[class*="detail"]', "main"]


def _size(paras):
    return sum(len(p) for p in paras)


def parse_detail(html: str):
    """Kembalikan (gambar, isi, tanggal) dari halaman detail yang sudah dirender."""
    soup = BeautifulSoup(html, "html.parser")

    # tanggal terbit
    date = None
    meta = soup.find("meta", attrs={"property": "article:published_time"})
    if meta and meta.get("content"):
        date = find_date(meta["content"])
    if not date:
        for t in soup.find_all("time"):
            date = find_date(t.get("datetime") or "") or find_date(t.get_text(" ", strip=True))
            if date:
                break
    if not date:
        root = soup.find("article") or soup.find("main") or soup.body or soup
        date = find_date(root.get_text(" ", strip=True)[:1500])

    # gambar: gambar pertama di dalam artikel, lalu og:image
    gambar = ""
    art = soup.find("article") or soup.find("main")
    if art:
        gambar = _img_src(art)

    # isi: ambil <p> dari wadah isi yang paling mungkin
    chosen = []
    for sel in CONTENT_SELECTORS:
        best = []
        for el in soup.select(sel):
            paras = [p.get_text(" ", strip=True) for p in el.find_all("p")]
            paras = [t for t in paras
                     if len(t) > 20 and not t.startswith("#") and not pusat._is_boilerplate(t)]
            paras = pusat._dedupe(paras)
            if _size(paras) > _size(best):
                best = paras
        if _size(best) >= MIN_GOOD:
            chosen = best
            break

    # cadangan: pakai pengurai umum dari scrape.py
    if _size(chosen) < MIN_GOOD:
        g2, k2 = pusat.parse_detail(html)
        if len(k2) > _size(chosen):
            chosen = [k2]
        gambar = gambar or g2
    elif not gambar:
        og = soup.find("meta", attrs={"property": "og:image"})
        if og and og.get("content"):
            gambar = urljoin(BASE + "/", og["content"])

    return gambar, "\n".join(chosen), date


def fetch_detail(ctx, url: str):
    page = ctx.new_page()
    try:
        goto(page, url, "article, div.prose, main p")
        return parse_detail(page.content())
    except Exception as e:
        print(f"   ⚠️ Gagal membuka detail: {e}")
        return "", "", None
    finally:
        page.close()


# ---------------------------------------------------------------------------
# Alur utama
# ---------------------------------------------------------------------------
def _csv_name(ym):
    return f"{CSV_PREFIX}-{ym[0]}-{ym[1]:02d}.csv"


def scrape_bintan():
    targets = determine_targets()
    oldest = min(targets)
    print("📅 Periode yang diambil:", ", ".join(f"{m:02d}/{y}" for y, m in targets))

    existing = {}
    for ym in targets:
        existing.update(load_existing(_csv_name(ym)))

    pw, browser, ctx = launch()
    try:
        page = ctx.new_page()
        cache = {}      # url -> (gambar, isi, tanggal) hasil buka halaman detail
        matched = []    # berita yang masuk periode target
        seen = set()

        try:
            pages = iter_list_pages(page)
            for n, items in enumerate(pages, 1):
                print(f"🔍 Halaman {n}: {len(items)} berita ditemukan")
                if n == 1 and not items:
                    dump_debug(page, "Halaman daftar terbuka tapi tidak ada tautan berita "
                                     "(pola URL/struktur situs berbeda). CSV lama tidak diubah.")
                    sys.exit(1)

                dates = []
                for it in items:
                    if it["url"] in seen:
                        continue
                    seen.add(it["url"])
                    d = it["tanggal"]
                    old = existing.get(it["url"])
                    if not d and old:
                        d = find_date(old.get("tanggal", ""))
                    if not d:   # daftar tidak menampilkan tanggal -> baca dari halaman detail
                        cache[it["url"]] = fetch_detail(ctx, it["url"])
                        d = cache[it["url"]][2]
                    it["tanggal"] = d
                    dates.append(d)
                    if d and (d[0], d[1]) in targets:
                        matched.append(it)

                known = [d for d in dates if d]
                if known and all((d[0], d[1]) < oldest for d in known):
                    break
        except SystemExit:
            raise
        except Exception as e:
            print(f"❌ Gagal menelusuri daftar berita: {e}")
            try:
                dump_debug(page, "Penelusuran daftar berhenti karena error.")
            except Exception:
                pass
            sys.exit(1)

        for ym in targets:
            rows = []
            for it in [x for x in matched if (x["tanggal"][0], x["tanggal"][1]) == ym]:
                old = existing.get(it["url"])
                if old and len(old.get("content", "")) >= MIN_REUSE:
                    rows.append({c: old.get(c, "") for c in COLUMNS})
                    continue
                if it["url"] not in cache:
                    cache[it["url"]] = fetch_detail(ctx, it["url"])
                gambar, konten, _ = cache[it["url"]]
                if not konten:
                    print(f"   ⚠️ Isi kosong untuk: {it['url']}")
                rows.append({
                    "judul": it["judul"],
                    "tanggal": fmt_date(it["tanggal"]),
                    "url": it["url"],
                    "gambar": it["gambar"] or gambar,
                    "content": clean_content_safety(konten),
                })

            name = _csv_name(ym)
            pd.DataFrame(rows, columns=COLUMNS).to_csv(name, index=False, encoding="utf-8", quoting=1)
            print(f"📊 {name}: {len(rows)} berita")
    finally:
        try:
            browser.close()
            pw.stop()
        except Exception:
            pass


if __name__ == "__main__":
    scrape_bintan()
