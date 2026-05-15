from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from webdriver_manager.chrome import ChromeDriverManager
import time
import csv

def scrape_berita_mei():
    # 1. Konfigurasi agar browser berjalan di background (Headless)
    chrome_options = Options()
    chrome_options.add_argument("--headless") 
    chrome_options.add_argument("--no-sandbox")
    chrome_options.add_argument("--disable-dev-shm-usage")
    chrome_options.add_argument("--window-size=1920,1080")

    # 2. Trik Penyamaran: Berpura-pura menjadi browser manusia biasa
    chrome_options.add_argument("user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36")
    chrome_options.add_argument("--disable-blink-features=AutomationControlled")
    chrome_options.add_experimental_option("excludeSwitches", ["enable-automation"])
    chrome_options.add_experimental_option('useAutomationExtension', False)

    # Inisialisasi Driver
    driver = webdriver.Chrome(service=Service(ChromeDriverManager().install()), options=chrome_options)
    
    # Sembunyikan status otomatisasi dari script deteksi internal website
    driver.execute_cdp_cmd("Page.addScriptToEvaluateOnNewDocument", {
        "source": "Object.defineProperty(navigator, 'webdriver', {get: () => undefined})"
    })

    target_month = "05"
    target_year = "2026"
    results = []

    try:
        print("📅 START SCRAPING MEI 2026")
        driver.get("https://www.atrbpn.go.id/berita")
        
        for page in range(1, 51):
            print(f"\n📄 PAGE {page}")
            time.sleep(3)  # Jeda waktu agar halaman termuat sempurna

            items = driver.find_elements(By.CSS_SELECTOR, ".col-md-3.col-6")
            print(f"ITEMS FOUND: {len(items)}")

            if len(items) == 0:
                print("⚠️ Tidak ada elemen ditemukan. Mungkin diblokir atau selector berubah.")
                break

            page_has_match = False
            links_data = []

            # Ambil data link terlebih dahulu
            for el in items:
                try:
                    a = el.find_element(By.TAG_NAME, "a")
                    title = a.text.strip()
                    url = a.get_attribute("href")
                    date_text = el.find_element(By.CLASS_NAME, "text-medium").text.strip()
                    
                    try:
                        img = el.find_element(By.TAG_NAME, "img").get_attribute("src")
                    except:
                        img = ""

                    links_data.append({"title": title, "url": url, "date": date_text, "img": img})
                except Exception as e:
                    continue

            # Proses setiap link berita
            for item in links_data:
                parts = item['date'].split("/")
                if len(parts) != 3: continue
                
                dd, mm, yyyy = parts
                if mm != target_month or yyyy != target_year: continue

                page_has_match = True
                print(f"➡️ OPENING: {item['title']}")

                try:
                    # Buka Tab Baru untuk detail berita
                    driver.execute_script(f"window.open('{item['url']}', '_blank');")
                    driver.switch_to.window(driver.window_handles[1])
                    time.sleep(3)

                    # Ambil Konten paragraf (<p>)
                    ps = driver.find_elements(By.TAG_NAME, "p")
                    content = "\n\n".join([p.text.strip() for p in ps if len(p.text.strip()) > 30])

                    results.append({
                        "judul": item['title'],
                        "tanggal": item['date'],
                        "url": item['url'],
                        "gambar": item['img'],
                        "konten": content
                    })

                    print(f"✅ SAVED: {item['title']}")
                except Exception as e:
                    print(f"❌ Gagal membuka detail: {e}")
                finally:
                    # Tutup Tab Detail dan kembali ke halaman utama
                    if len(driver.window_handles) > 1:
                        driver.close()
                        driver.switch_to.window(driver.window_handles[0])

            if not page_has_match:
                print("🛑 STOP: Tidak ada data Mei 2026 di halaman ini.")
                break

            # Navigasi ke halaman berikutnya (Klik tombol 'Next')
            try:
                next_btn = driver.find_element(By.XPATH, "//a[contains(text(), 'Next')]")
                next_btn.click()
            except:
                print("🏁 END: Tombol Next tidak ditemukan atau halaman habis.")
                break

    except Exception as global_error:
        print(f"💥 Terjadi Error Utama: {global_error}")

    finally:
        driver.quit()

    # 3. Proses penyimpanan ke CSV (hanya jika ada data yang berhasil diambil)
    if results:
        keys = results[0].keys()
        with open('berita-mei-2026.csv', 'w', newline='', encoding='utf-8') as f:
            dict_writer = csv.DictWriter(f, fieldnames=keys)
            dict_writer.writeheader()
            dict_writer.writerows(results)
        print(f"\n📊 SELESAI. File 'berita-mei-2026.csv' berhasil dibuat dengan total data: {len(results)}")
    else:
        print("\n📊 SELESAI. Tidak ada data yang disimpan karena hasil kosong.")

if __name__ == "__main__":
    scrape_berita_mei()
