from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from webdriver_manager.chrome import ChromeDriverManager
import time
import csv

def scrape_berita_mei():
    # Konfigurasi agar browser berjalan di background (Headless)
    chrome_options = Options()
    chrome_options.add_argument("--headless") 
    chrome_options.add_argument("--no-sandbox")
    chrome_options.add_argument("--disable-dev-shm-usage") # Penting untuk lingkungan Docker/Actions
    chrome_options.add_argument("--window-size=1920,1080")
    
    driver = webdriver.Chrome(service=Service(ChromeDriverManager().install()), options=chrome_options)
    
    target_month = "05"
    target_year = "2026"
    results = []

    try:
        driver.get("https://www.atrbpn.go.id/berita") # Ganti dengan URL asal
        
        for page in range(1, 51):
            print(f"\n📄 PAGE {page}")
            time.sleep(2) # Sleep seperti skrip JS kamu

            items = driver.find_elements(By.CSS_SELECTOR, ".col-md-3.col-6")
            print(f"ITEMS FOUND: {len(items)}")

            page_has_match = False

            # Kita ambil link-nya dulu karena jika pindah page, elemen lama akan 'stale'
            links_data = []
            for el in items:
                try:
                    a = el.find_element(By.TAG_NAME, "a")
                    title = a.text.strip()
                    url = a.get_attribute("href")
                    date_text = el.find_element(By.CLASS_NAME, "text-medium").text.strip()
                    img = el.find_element(By.TAG_NAME, "img").get_attribute("src")
                    links_data.append({"title": title, "url": url, "date": date_text, "img": img})
                except:
                    continue

            for item in links_data:
                parts = item['date'].split("/")
                if len(parts) != 3: continue
                
                dd, mm, yyyy = parts
                if mm != target_month or yyyy != target_year: continue

                page_has_match = True
                print(f"➡️ OPENING: {item['title']}")

                # Buka Tab Baru (Simulasi window.open)
                driver.execute_script(f"window.open('{item['url']}', '_blank');")
                driver.switch_to.window(driver.window_handles[1])
                time.sleep(2.5)

                # Ambil Konten <p>
                ps = driver.find_elements(By.TAG_NAME, "p")
                content = "\n\n".join([p.text.strip() for p in ps if len(p.text.strip()) > 30])

                results.append({
                    "judul": item['title'],
                    "tanggal": item['date'],
                    "url": item['url'],
                    "gambar": item['img'],
                    "konten": content
                })

                # Tutup Tab Detail, kembali ke list utama
                driver.close()
                driver.switch_to.window(driver.window_handles[0])
                print(f"✅ SAVED: {item['title']}")

            if not page_has_match:
                print("🛑 STOP: Tidak ada data Mei di halaman ini.")
                break

            # Navigasi ke halaman berikutnya
            try:
                next_btn = driver.find_element(By.XPATH, "//a[contains(text(), 'Next')]")
                next_btn.click()
            except:
                print("🏁 END: Tombol Next tidak ditemukan.")
                break

    finally:
        driver.quit()

    # Simpan ke CSV
    keys = results[0].keys() if results else []
    with open('berita-mei-2026.csv', 'w', newline='', encoding='utf-8') as f:
        dict_writer = csv.DictWriter(f, fieldnames=keys)
        dict_writer.writeheader()
        dict_writer.writerows(results)
    
    print(f"\n📊 SELESAI. Total data: {len(results)}")

if __name__ == "__main__":
    scrape_berita_mei()
