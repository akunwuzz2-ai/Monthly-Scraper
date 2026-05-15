import os
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from webdriver_manager.chrome import ChromeDriverManager
import time
import csv

def scrape_berita_mei():
    # 1. Konfigurasi Headless Browser untuk GitHub Actions
    chrome_options = Options()
    chrome_options.add_argument("--headless") 
    chrome_options.add_argument("--no-sandbox")
    chrome_options.add_argument("--disable-dev-shm-usage")
    chrome_options.add_argument("--window-size=1920,1080")
    
    # Penyamaran User-Agent agar tidak terdeteksi sebagai bot data center
    chrome_options.add_argument("user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36")
    chrome_options.add_argument("--disable-blink-features=AutomationControlled")
    chrome_options.add_experimental_option("excludeSwitches", ["enable-automation"])
    chrome_options.add_experimental_option('useAutomationExtension', False)

    driver = webdriver.Chrome(service=Service(ChromeDriverManager().install()), options=chrome_options)
    
    # Injeksi skrip untuk menyembunyikan status otomatisasi driver
    driver.execute_cdp_cmd("Page.addScriptToEvaluateOnNewDocument", {
        "source": "Object.defineProperty(navigator, 'webdriver', {get: () => undefined})"
    })

    target_month = "05"
    target_year = "2026"
    results = []

    try:
        print("📅 START SCRAPING MEI 2026")
        driver.get("https://www.atrbpn.go.id/berita")
        time.sleep(5)  # Menunggu bypass filter halaman utama

        print(f"🔍 Page Title: {driver.title}")

        for page in range(1, 11):  # Batasi sampai 10 halaman pencarian
            print(f"\n📄 PAGE {page}")
            
            # Deteksi elemen berita utama
            items = driver.find_elements(By.CSS_SELECTOR, ".col-md-3.col-6")
            if len(items) == 0:
                # Selector cadangan jika struktur grid dinamis
                items = driver.find_elements(By.XPATH, "//div[contains(@class, 'card')]")
            
            print(f"ITEMS FOUND: {len(items)}")

            if len(items) == 0:
                print("⚠️ Tidak ada elemen ditemukan pada halaman ini.")
                break

            page_has_match = False
            links_data = []

            # Koleksi link dan metadata di halaman list
            for el in items:
                try:
                    a = el.find_element(By.TAG_NAME, "a")
                    url = a.get_attribute("href")
                    title = a.text.strip() or el.text.split('\n')[0]
                    
                    # Cari tanggal berita
                    try:
                        date_text = el.find_element(By.CLASS_NAME, "text-medium").text.strip()
                    except:
                        date_text = ""

                    # Jika class tanggal kosong, kita coba deteksi teks di dalam elemen yang mirip format tanggal
                    if not date_text and "/" in el.text:
                        for word in el.text.split():
                            if word.count("/") == 2:
                                date_text = word
                                break

                    links_data.append({"title": title, "url": url, "date": date_text})
                except:
                    continue

            # Buka satu per satu detail berita yang sesuai bulan target
            for item in links_data:
                # Validasi kecocokan bulan dan tahun (Mei 2026)
                if target_month in item['date'] and target_year in item['date']:
                    page_has_match = True
                    print(f"➡️ PROSES: {item['title']}")
                    
                    try:
                        # Buka detail berita di Tab Baru
                        driver.execute_script(f"window.open('{item['url']}', '_blank');")
                        driver.switch_to.window(driver.window_handles[1])
                        
                        # Beri waktu lebih lama agar konten AJAX/skrip artikel termuat penuh
                        time.sleep(5) 

                        # Ambil konten teks berdasarkan tag paragraf (<p>)
                        ps = driver.find_elements(By.TAG_NAME, "p")
                        content = "\n\n".join([p.text.strip() for p in ps if len(p.text.strip()) > 30])
                        
                        # Robustness Fallback: Jika tag <p> tidak menghasilkan teks yang cukup
                        if len(content) < 150:
                            for class_name in ["entry-content", "post-content", "content-berita", "detail-berita"]:
                                try:
                                    fallback_element = driver.find_element(By.CLASS_NAME, class_name)
                                    content = fallback_element.text.strip()
                                    if len(content) > 150:
                                        break
                                except:
                                    pass

                        results.append({
                            "judul": item['title'],
                            "tanggal": item['date'],
                            "url": item['url'],
                            "konten": content
                        })
                        
                        print(f"   ✅ DETAIL BERHASIL DISALAN ({len(content)} karakter)")

                    except Exception as e:
                        print(f"   ❌ Gagal membuka detail: {e}")
                    finally:
                        # Pastikan tab detail ditutup dan kembali ke halaman utama list berita
                        if len(driver.window_handles) > 1:
                            driver.close()
                            driver.switch_to.window(driver.window_handles[0])

            # Jika di halaman ini sudah tidak ada satupun berita bulan Mei, hentikan loop pagination
            if not page_has_match and page > 1:
                print("🛑 STOP: Sudah melewati rentang tanggal Mei 2026.")
                break
            
            # Navigasi klik tombol 'Next'
            try:
                next_btn = driver.find_element(By.PARTIAL_LINK_TEXT, "Next")
                next_btn.click()
            except:
                print("🏁 END: Tombol Next tidak ditemukan atau halaman habis.")
                break

    except Exception as e:
        print(f"💥 Terjadi Error Sistem: {e}")
    finally:
        driver.quit()

    # 3. Penyimpanan Data ke File CSV
    if results:
        with open('berita-mei-2026.csv', 'w', newline='', encoding='utf-8') as f:
            writer = csv.DictWriter(f, fieldnames=results[0].keys())
            writer.writeheader()
            writer.writerows(results)
        print(f"\n📊 SELESAI. File 'berita-mei-2026.csv' berhasil diperbarui dengan {len(results)} data lengkap.")
    else:
        print("\n📊 SELESAI. Tidak ada data yang disimpan karena hasil kosong.")

if __name__ == "__main__":
    scrape_berita_mei()
