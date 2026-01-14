import time
import re
import pandas as pd
from bs4 import BeautifulSoup

# Selenium Imports
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from webdriver_manager.chrome import ChromeDriverManager

# ==========================================
# 👇 CONFIGURATION 👇
# ==========================================
TARGET_SAMPLES_PER_CLASS = 3000
# ==========================================

class VeraFilesScraper:
    def __init__(self):
        chrome_options = Options()
        
        # ⭐ VISUAL MODE (Headless OFF) - Helps bypass detection
        chrome_options.add_argument("--start-maximized") 
        chrome_options.add_argument("--log-level=3")
        
        # ⭐ STEALTH SETTINGS (CRITICAL FOR BYPASSING 403)
        # 1. Disable the "AutomationControlled" flag
        chrome_options.add_argument("--disable-blink-features=AutomationControlled")
        
        # 2. Exclude the "enable-automation" switch
        chrome_options.add_experimental_option("excludeSwitches", ["enable-automation"])
        
        # 3. Turn off automation extension
        chrome_options.add_experimental_option('useAutomationExtension', False)
        
        # 4. Use a standard User-Agent
        chrome_options.add_argument("user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36")

        print("🚀 Initializing Selenium WebDriver (Stealth Mode)...")
        self.driver = webdriver.Chrome(service=Service(ChromeDriverManager().install()), options=chrome_options)
        
        # ⭐ CRITICAL: Execute CDP command to completely hide webdriver property
        self.driver.execute_cdp_cmd("Page.addScriptToEvaluateOnNewDocument", {
            "source": """
                Object.defineProperty(navigator, 'webdriver', {
                    get: () => undefined
                })
            """
        })
        
        # Long timeout for slow internet
        self.driver.set_page_load_timeout(180)
        
        self.urls = {
            "fake": ["https://verafiles.org/articles/category/fact-check"],
            "true": [
                "https://verafiles.org/articles/category/updates",
                "https://verafiles.org/articles/category/features",
                "https://verafiles.org/articles/category/profiles",
                "https://verafiles.org/articles/category/commentary"
            ]
        }

    def clean_text(self, text):
        if not text: return ""
        return re.sub(r'\s+', ' ', text).strip()

    def get_full_content(self, url):
        try:
            self.driver.execute_script("window.open('');")
            self.driver.switch_to.window(self.driver.window_handles[1])
            
            text = ""
            try:
                self.driver.get(url)
                WebDriverWait(self.driver, 30).until(
                    EC.presence_of_element_located((By.TAG_NAME, "p"))
                )
                
                soup = BeautifulSoup(self.driver.page_source, "html.parser")
                
                content = soup.find("div", class_="uk-article-content")
                if not content: content = soup.find("div", class_="entry-content")
                if not content: content = soup.find("article")
                
                if content:
                    paragraphs = content.find_all('p')
                    valid_paragraphs = [p.get_text() for p in paragraphs if len(p.get_text()) > 30]
                    text = self.clean_text(" ".join(valid_paragraphs))
                
            except Exception:
                pass 
            
            if len(self.driver.window_handles) > 1:
                self.driver.close()
                self.driver.switch_to.window(self.driver.window_handles[0])
            return text

        except Exception:
            if len(self.driver.window_handles) > 1:
                self.driver.switch_to.window(self.driver.window_handles[0])
            return ""

    def scroll_to_bottom(self):
        try:
            self.driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
            time.sleep(2)
        except:
            pass

    def scrape_section(self, category_type, target_count):
        print(f"\n🚀 Starting scrape for '{category_type.upper()}' articles...")
        collected_data = []
        url_list = self.urls[category_type]
        junk_titles = ["methodology", "previous post", "next post", "about us", "contact", "privacy policy"]
        
        for base_url in url_list:
            if len(collected_data) >= target_count: break
            print(f"   👉 Source: {base_url}")
            
            page_num = 1
            consecutive_empty = 0
            
            # Start navigation
            if "?" in base_url:
                current_url = f"{base_url}&page={page_num}"
            else:
                current_url = f"{base_url}?page={page_num}"
            
            while len(collected_data) < target_count:
                print(f"      🔄 Navigating to Page {page_num}...")
                
                # Retry loop
                success = False
                for attempt in range(3):
                    try:
                        self.driver.get(current_url)
                        WebDriverWait(self.driver, 60).until(
                            EC.presence_of_element_located((By.XPATH, "//a[contains(@href, '/articles/')]"))
                        )
                        success = True
                        break
                    except Exception:
                        print(f"      ⚠️ Page load failed (Attempt {attempt+1}). Retrying...")
                        time.sleep(5)
                
                if not success:
                    print("      ❌ Failed to pass 403 or Timeout. Trying next page...")
                    page_num += 1
                    if "?" in base_url:
                        current_url = f"{base_url}&page={page_num}"
                    else:
                        current_url = f"{base_url}?page={page_num}"
                    continue

                self.scroll_to_bottom()
                soup = BeautifulSoup(self.driver.page_source, "html.parser")
                all_links = soup.find_all("a", href=True)
                
                found_on_page = 0
                
                for link in all_links:
                    if len(collected_data) >= target_count: break
                    href = link['href']
                    title = link.get_text(strip=True)
                    
                    if '/articles/' in href:
                        full_url = href if href.startswith("http") else "https://verafiles.org" + href
                        
                        is_junk = any(junk in title.lower() for junk in junk_titles)
                        is_category = '/category/' in full_url
                        is_duplicate = any(d['url'] == full_url for d in collected_data)
                        
                        if not is_junk and not is_category and not is_duplicate:
                            label = "Fake" if category_type == "fake" else "True"
                            text = self.get_full_content(full_url)
                            
                            if text and len(text) > 50:
                                display_title = title if title else full_url.split('/')[-1]
                                print(f"      ✅ Added: {display_title[:30]}... [{label}]")
                                
                                collected_data.append({
                                    "text": text,
                                    "label": label,
                                    "category": category_type,
                                    "title": display_title,
                                    "url": full_url,
                                    "source": "Vera Files"
                                })
                                found_on_page += 1
                
                print(f"      📄 Page {page_num}: Found {found_on_page} items. Total: {len(collected_data)}")
                
                if found_on_page == 0:
                    consecutive_empty += 1
                else:
                    consecutive_empty = 0

                if consecutive_empty >= 4:
                    print("      ❌ No items found on last 4 pages. Moving to next source.")
                    break
                
                # Manual URL construction (Bypasses need for "Next" button)
                page_num += 1
                if "?" in base_url:
                    current_url = f"{base_url}&page={page_num}"
                else:
                    current_url = f"{base_url}?page={page_num}"
            
        return pd.DataFrame(collected_data)

    def run_full_scrape(self, samples_per_class):
        try:
            df_fake = self.scrape_section("fake", target_count=samples_per_class)
            df_true = self.scrape_section("true", target_count=samples_per_class)
            
            print("\n" + "="*40)
            print(f"📊 FINAL COLLECTION COUNTS:")
            print(f"   🔴 Fake: {len(df_fake)}")
            print(f"   🟢 True: {len(df_true)}")
            print("="*40)

            final_df = pd.concat([df_fake, df_true])
            final_df.to_csv("VeraFiles_Full_Dataset.csv", index=False, encoding="utf-8-sig")
            return final_df
        finally:
            try:
                self.driver.quit()
            except:
                pass

if __name__ == "__main__":
    scraper = VeraFilesScraper()
    final_dataset = scraper.run_full_scrape(samples_per_class=TARGET_SAMPLES_PER_CLASS)
    
    if final_dataset is not None and not final_dataset.empty:
        print(f"\n🎉 SUCCESS! Saved {len(final_dataset)} rows to VeraFiles_Full_Dataset.csv")
    else:
        print("\n❌ No data collected.")