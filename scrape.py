import os
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from webdriver_manager.chrome import ChromeDriverManager
import time
import csv

def scrape_berita_mei():
    chrome_options = Options()
    chrome_options.add_argument("--headless") 
    chrome_options.add_argument("--no-sandbox")
    chrome_options.add_argument("--disable-dev-shm-usage")
    chrome_options.add_argument("--window-size=1920,1080")
    
    # User-Agent yang lebih baru
    chrome_options.add_argument("user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36")
    chrome_options.add_argument("--disable-blink-features=AutomationControlled")
    chrome_options.add_experimental_option("excludeSwitches", ["enable-automation"])
    chrome_options.add_experimental_option('useAutomationExtension', False)

    driver = webdriver.Chrome(service=Service(ChromeDriverManager().install()), options=chrome_options)
    
    driver.execute_cdp_cmd("Page.addScriptToEvaluateOnNewDocument", {
        "source": "Object.defineProperty(navigator, 'webdriver', {get: () => undefined})"
    })

    target_month = "05"
    target_year = "2026"
    results = []

    try:
        print("📅 START SCRAPING MEI 2026")
        # Mencoba akses URL langsung ke daftar berita
        driver.get("https://www.atrbpn.go.id/berita")
        time.sleep(5) # Beri waktu lebih lama untuk bypass filter

        # DEBUG: Cetak Judul Halaman untuk memastikan kita tidak diblokir
        print(f"🔍 Page Title: {driver.title}")

        for page in range(1, 10): # Coba 10 halaman dulu
            print(f"\n📄 PAGE {page}")
            
            # Selector alternatif jika yang lama gagal
            items = driver.find_elements(By.CSS_SELECTOR, ".col-md-3.col-6")
            if len(items) == 0:
                # Coba selector cadangan (biasanya berita dibungkus dalam tag article atau div berita)
                items = driver.find_elements(By.XPATH, "//div[contains(@class, 'card')]")
            
            print(f"ITEMS FOUND: {len(items)}")

            if len(items) == 0:
                # Jika masih 0, ambil screenshot untuk diagnosa (opsional di local, di action agak sulit dilihat)
                print("⚠️ Gagal menemukan item. Mencoba cek link berita secara umum...")
                break

            page_has_match = False
            links_data = []

            for el in items:
                try:
                    a = el.find_element(By.TAG_NAME, "a")
                    url = a.get_attribute("href")
                    title = a.text.strip() or el.text.split('\n')[0]
                    
                    # Coba cari tanggal dengan berbagai class
                    try:
                        date_text = el.find_element(By.CLASS_NAME, "text-medium").text.strip()
                    except:
                        date_text = "" # Fallback jika tanggal tidak ditemukan

                    links_data.append({"title": title, "url": url, "date": date_text})
                except:
                    continue

            for item in links_data:
                if target_month in item['date'] and target_year in item['date']:
                    page_has_match = True
                    print(f"➡️ PROSES: {item['title']}")
                    
                    # --- Bagian pengambilan detail tetap sama ---
                    driver.execute_script(f"window.open('{item['url']}', '_blank');")
                    driver.switch_to.window(driver.window_handles[1])
                    time.sleep(3)
                    ps = driver.find_elements(By.TAG_NAME, "p")
                    content = "\n\n".join([p.text.strip() for p in ps if len(p.text.strip()) > 30])
                    
                    results.append({
                        "judul": item['title'],
                        "tanggal": item['date'],
                        "url": item['url'],
                        "konten": content
                    })
                    
                    driver.close()
                    driver.switch_to.window(driver.window_handles[0])

            if not page_has_match and page > 1:
                break
            
            # Klik Next
            try:
                next_btn = driver.find_element(By.PARTIAL_LINK_TEXT, "Next")
                next_btn.click()
            except:
                break

    except Exception as e:
        print(f"💥 Error: {e}")
    finally:
        driver.quit()

    if results:
        with open('berita-mei-2026.csv', 'w', newline='', encoding='utf-8') as f:
            writer = csv.DictWriter(f, fieldnames=results[0].keys())
            writer.writeheader()
            writer.writerows(results)
        print(f"✅ Berhasil menyimpan {len(results)} data.")

if __name__ == "__main__":
    scrape_berita_mei()
