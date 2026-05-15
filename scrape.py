import os
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from webdriver_manager.chrome import ChromeDriverManager
import time
import csv

def scrape_berita_mei():
    # Hapus file lama jika ada agar tidak terjadi konflik data lama
    if os.path.exists('berita-mei-2026.csv'):
        os.remove('berita-mei-2026.csv')

    chrome_options = Options()
    chrome_options.add_argument("--headless=new") 
    chrome_options.add_argument("--no-sandbox")
    chrome_options.add_argument("--disable-dev-shm-usage")
    chrome_options.add_argument("--window-size=1920,1080")
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
        driver.get("https://www.atrbpn.go.id/publikasi/berita")
        time.sleep(8)

        for page in range(1, 6):
            print(f"\n📄 PAGE {page}")
            time.sleep(5)
            
            items = driver.find_elements(By.CSS_SELECTOR, ".col-md-3.col-6, .card")
            if len(items) == 0: break

            links_data = []
            for el in items:
                try:
                    a = el.find_element(By.TAG_NAME, "a")
                    url = a.get_attribute("href")
                    title = a.text.strip()
                    date_text = el.text
                    links_data.append({"title": title, "url": url, "date": date_text})
                except: continue

            page_has_match = False
            for item in links_data:
                if target_month in item['date'] and target_year in item['date']:
                    page_has_match = True
                    print(f"➡️ DETAIL: {item['title'][:50]}...")
                    
                    try:
                        driver.execute_script(f"window.open('{item['url']}', '_blank');")
                        driver.switch_to.window(driver.window_handles[-1])
                        time.sleep(6)

                        ps = driver.find_elements(By.TAG_NAME, "p")
                        content = "\n\n".join([p.text.strip() for p in ps if len(p.text.strip()) > 30])
                        
                        if len(content) < 100:
                            content = "Konten tidak ditemukan atau struktur halaman berbeda."

                        results.append({
                            "judul": item['title'],
                            "tanggal": item['date'].split('\n')[0] if '\n' in item['date'] else item['date'],
                            "url": item['url'],
                            "konten": content.replace('"', '""')
                        })
                        print(f"   ✅ BERHASIL ({len(content)} karakter)")

                        driver.close()
                        driver.switch_to.window(driver.window_handles[0])
                    except:
                        if len(driver.window_handles) > 1:
                            driver.close()
                            driver.switch_to.window(driver.window_handles[0])

            if not page_has_match and page > 1: break
            
            try:
                next_btn = driver.find_element(By.PARTIAL_LINK_TEXT, "Next")
                driver.execute_script("arguments[0].click();", next_btn)
            except: break

    except Exception as e:
        print(f"💥 ERROR: {e}")
    finally:
        driver.quit()

    if results:
        with open('berita-mei-2026.csv', 'w', newline='', encoding='utf-8') as f:
            writer = csv.DictWriter(f, fieldnames=results[0].keys(), quoting=csv.QUOTE_ALL)
            writer.writeheader()
            writer.writerows(results)
        print(f"\n📊 SELESAI: {len(results)} data.")

if __name__ == "__main__":
    scrape_berita_mei()
