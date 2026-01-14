import time
import pandas as pd
from bs4 import BeautifulSoup
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from webdriver_manager.chrome import ChromeDriverManager

# SETTINGS
TEST_URL = "https://verafiles.org/articles/category/fact-check"

def run_diagnostic():
    chrome_options = Options()
    # We run VISIBLE so you can see it
    chrome_options.add_argument("--start-maximized")
    chrome_options.add_argument("--log-level=3")
    
    print("🚀 STARTING DIAGNOSTIC TEST...")
    print(f"👉 Target: {TEST_URL}")
    
    driver = webdriver.Chrome(service=Service(ChromeDriverManager().install()), options=chrome_options)
    
    try:
        driver.get(TEST_URL)
        print("⏳ Waiting 10 seconds for page to load...")
        time.sleep(10) # Fixed wait to ensure everything settles

        # 1. CAPTURE EVIDENCE
        print("\n📸 Taking Screenshot (saved as 'debug_screenshot.png')...")
        driver.save_screenshot("debug_screenshot.png")
        
        print("💾 Saving HTML Source (saved as 'debug_source.html')...")
        with open("debug_source.html", "w", encoding="utf-8") as f:
            f.write(driver.page_source)

        # 2. ANALYZE CONTENT
        soup = BeautifulSoup(driver.page_source, "html.parser")
        
        # Check Title
        print(f"\nPAGE TITLE: {driver.title}")
        
        # Check Links
        all_links = soup.find_all("a", href=True)
        article_links = [l['href'] for l in all_links if '/articles/' in l['href']]
        
        print(f"🔗 Total Links Found: {len(all_links)}")
        print(f"📰 Article Links Found: {len(article_links)}")
        
        if len(article_links) > 0:
            print("   ✅ First 3 Articles Found:")
            for l in article_links[:3]:
                print(f"      - {l}")
        else:
            print("   ❌ NO ARTICLE LINKS FOUND. The page might be empty or loading failed.")

        # 3. ANALYZE PAGINATION
        print("\n🔎 Checking Pagination...")
        pagination_ul = soup.find("ul", class_="uk-pagination")
        if pagination_ul:
            print("   ✅ Found 'uk-pagination' list.")
            print(f"   📄 Pagination HTML snippet: {str(pagination_ul)[:200]}...")
        else:
            print("   ❌ 'uk-pagination' NOT FOUND.")

        # Check specifically for Next button
        next_candidates = soup.select("[uk-pagination-next], [uk-icon*='arrow-right'], .uk-pagination-next a")
        if next_candidates:
            print(f"   ✅ Found {len(next_candidates)} potential 'Next' buttons.")
            print(f"   ➡️ First candidate HTML: {str(next_candidates[0])}")
        else:
            print("   ❌ No standard 'Next' button found.")

    except Exception as e:
        print(f"\n❌ CRITICAL ERROR: {e}")
    finally:
        print("\n✅ DIAGNOSTIC COMPLETE. Check the folder for 'debug_screenshot.png'.")
        # driver.quit() # Keep browser open so you can inspect manually

if __name__ == "__main__":
    run_diagnostic()