import time
import re
import pandas as pd
from bs4 import BeautifulSoup

# Selenium Imports
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.common.exceptions import NoSuchElementException, ElementClickInterceptedException
from webdriver_manager.chrome import ChromeDriverManager

# ==========================================
# 👇 CONFIGURATION 👇
# ==========================================
TARGET_SAMPLES_PER_CLASS = 3000
# ==========================================

class VeraFilesScraper:
    def __init__(self):
        chrome_options = Options()
        chrome_options.add_argument("--headless") 
        chrome_options.add_argument("--disable-gpu")
        chrome_options.add_argument("--window-size=1920,1080")
        chrome_options.add_argument("--log-level=3")
        chrome_options.add_argument("user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36")

        print("🚀 Initializing Selenium WebDriver...")
        self.driver = webdriver.Chrome(service=Service(ChromeDriverManager().install()), options=chrome_options)
        
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
        # Open a new tab for the article so we don't lose our place in the list
        self.driver.execute_script("window.open('');")
        self.driver.switch_to.window(self.driver.window_handles[1])
        
        text = ""
        try:
            self.driver.get(url)
            time.sleep(1) # Wait for render
            soup = BeautifulSoup(self.driver.page_source, "html.parser")
            
            # Content selectors
            content = soup.find("div", class_="uk-article-content")
            if not content: content = soup.find("div", class_="entry-content")
            if not content: content = soup.find("div", class_="article-content")
            if not content: content = soup.find("article")
            
            if content:
                paragraphs = content.find_all('p')
                text = self.clean_text(" ".join([p.get_text() for p in paragraphs]))
        except Exception as e:
            print(f"Error scraping article: {e}")
        
        # Close tab and go back
        self.driver.close()
        self.driver.switch_to.window(self.driver.window_handles[0])
        return text

    def go_to_next_page(self):
        """Finds the 'Next' button and clicks it."""
        try:
            # Try finding the specific UIkit pagination 'Next' arrow/link
            # Common in VeraFiles themes: <a href="..." rel="next"> or <li class="uk-pagination-next">
            next_buttons = self.driver.find_elements(By.XPATH, "//a[contains(@class, 'next') or contains(text(), 'Next') or contains(text(), '»')]")
            
            # Filter for visible buttons
            for btn in next_buttons:
                if btn.is_displayed():
                    self.driver.execute_script("arguments[0].click();", btn)
                    time.sleep(3) # Wait for next page load
                    return True
            
            return False
        except Exception:
            return False

    def scrape_section(self, category_type, target_count):
        print(f"\n🚀 Starting scrape for '{category_type.upper()}' articles...")
        collected_data = []
        url_list = self.urls[category_type]
        
        for base_url in url_list:
            if len(collected_data) >= target_count: break
            print(f"   👉 Source: {base_url}")
            
            self.driver.get(base_url)
            time.sleep(3)
            
            page = 1
            consecutive_empty = 0
            
            while len(collected_data) < target_count:
                soup = BeautifulSoup(self.driver.page_source, "html.parser")
                all_links = soup.find_all("a", href=True)
                
                found_on_page = 0
                
                for link in all_links:
                    if len(collected_data) >= target_count: break
                    href = link['href']
                    title = link.get_text(strip=True)
                    
                    # 1. Cleaner check: Must contain '/articles/' 
                    # 2. Must NOT be a category link
                    if '/articles/' in href and '/category/' not in href:
                        full_url = href if href.startswith("http") else "https://verafiles.org" + href
                        
                        # Deduplication
                        if any(d['url'] == full_url for d in collected_data): continue
                        
                        # REMOVED TITLE LENGTH CHECK to catch short titles in "True" category
                        label = "Fake" if category_type == "fake" else "True"
                        text = self.get_full_content(full_url)
                        
                        if text and len(text) > 50: # Basic check for empty body
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

                print(f"      📄 Page {page}: Found {found_on_page} items. (Total: {len(collected_data)})")
                
                if found_on_page == 0:
                    consecutive_empty += 1
                else:
                    consecutive_empty = 0

                if consecutive_empty >= 2:
                    print("      ❌ No items found on last 2 pages. Moving to next source.")
                    break
                
                # Try to click NEXT
                print("      🔄 Attempting to go to next page...")
                if not self.go_to_next_page():
                    print("      🛑 No 'Next' button found. End of category.")
                    break
                
                page += 1
            
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
            final_df = final_df.sample(frac=1, random_state=42).reset_index(drop=True)
            return final_df
        finally:
            self.driver.quit()

if __name__ == "__main__":
    scraper = VeraFilesScraper()
    final_dataset = scraper.run_full_scrape(samples_per_class=TARGET_SAMPLES_PER_CLASS)
    
    if final_dataset is not None and not final_dataset.empty:
        filename = "VeraFiles_Full_Dataset.csv"
        final_dataset.to_csv(filename, index=False, encoding="utf-8-sig")
        print(f"\n🎉 SUCCESS! Saved {len(final_dataset)} rows to {filename}")
    else:
        print("\n❌ No data collected.")