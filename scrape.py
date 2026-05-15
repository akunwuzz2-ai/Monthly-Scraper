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
    
    # Penyamaran agar tidak dianggap bot
    chrome_options.add_argument("user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36")
    chrome_options.add_argument("--disable-blink-features=AutomationControlled")
    chrome_options.add_experimental_option("excludeSwitches", ["enable-automation"])

    driver = webdriver.Chrome(service=Service(ChromeDriverManager().install()), options=chrome_options)
    
    driver.execute_cdp_cmd("Page.addScriptToEvaluateOnNewDocument", {
        "source": "Object.defineProperty(navigator, 'webdriver', {get: () => undefined})"
    })

    target_month = "05"
    target_year = "2026"
    results = []

    try:
        print("📅 START SCRAPING MEI 2026")
        driver.get("https://www.atrbpn.go.id/berita")
        time.sleep(6)

        for page in range(1, 6): # Cek 5 halaman awal
            print(f"\n📄 PAGE {page}")
            items = driver.find_elements(By.CSS_SELECTOR, ".col-md-3.col-6, .card, .post-item")
            print(f"ITEMS FOUND: {len(items)}")

            if len(items) == 0: break

            links_data = []
            for el in items:
                try:
                    a = el.find_element(By.TAG_NAME, "a")
                    url = a.get_attribute("href")
                    title = a.text.strip() or "Tanpa Judul"
                    try:
                        date_text = el.find_element(By.XPATH, ".//*[contains(@class, 'text') or contains(@class, 'date')]").text.strip()
                    except:
                        date_text = ""
                    
                    if url and url not in [l['url'] for l in links_data]:
                        links_data.append({"title": title, "url": url, "date": date_text})
                except: continue

            page_has_match = False
            for item in links_data:
                if target_month in item['date'] and target_year in item['date']:
                    page_has_match = True
                    print(f"➡️ OPENING: {item['title'][:50]}...")
                    
                    try:
                        driver.execute_script(f"window.open('{item['url']}', '_blank');")
                        driver.switch_to.window(driver.window_handles[1])
                        
                        # Tunggu dan Scroll agar konten load
                        time.sleep(5)
                        driver.execute_script("window.scrollBy(0, 500);")
                        time.sleep(1)

                        # AMBIL KONTEN (Multi-Selector)
                        content_elements = driver.find_elements(By.XPATH, "//div[contains(@class, 'content')]//p | //article//p | //div[contains(@id, 'content')]//p")
                        
                        if not content_elements:
                             # Jika tidak ada <p>, ambil teks dari container utama
                             content = driver.find_element(By.TAG_NAME, "body").text.split("Bagikan :")[0] # Potong bagian sosmed
                             # Bersihkan teks agar tidak terlalu panjang/kotor
                             content = ' '.join(content.split()[:300]) # Ambil 300 kata pertama saja
                        else:
                             content = "\n\n".join([p.text.strip() for p in content_elements if len(p.text.strip()) > 30])

                        results.append({
                            "judul": item['title'],
                            "tanggal": item['date'],
                            "url": item['url'],
                            "konten": content.replace('"', '""') # Escaping untuk CSV
                        })
                        print(f"   ✅ BERHASIL: {len(content)} karakter")

                    except:
                        print("   ❌ Gagal mengambil detail")
                    finally:
                        if len(driver.window_handles) > 1:
                            driver.close()
                            driver.switch_to.window(driver.window_handles[0])

            if not page_has_match and page > 1: break
            
            try:
                next_btn = driver.find_element(By.PARTIAL_LINK_TEXT, "Next")
                next_btn.click()
                time.sleep(4)
            except: break

    finally:
        driver.quit()

    if results:
        with open('berita-mei-2026.csv', 'w', newline='', encoding='utf-8') as f:
            writer = csv.DictWriter(f, fieldnames=results[0].keys(), quoting=csv.QUOTE_ALL)
            writer.writeheader()
            writer.writerows(results)
        print(f"\n📊 SELESAI: {len(results)} data tersimpan.")

if __name__ == "__main__":
    scrape_berita_mei()
