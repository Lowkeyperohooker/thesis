import requests
from bs4 import BeautifulSoup
import pandas as pd
import time
import re
import datetime

# ==========================================
# 👇 CONFIGURATION 👇
# ==========================================
# This is now the "Max Limit" per category. 
# It will try to get this many, but if it finds less, it keeps what it found.
TARGET_SAMPLES_PER_CLASS = 200 
# ==========================================

class VeraFilesScraper:
    def __init__(self):
        self.headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        }
        self.session = requests.Session()
        
        self.urls = {
            "fake": ["https://verafiles.org/articles/category/fact-check"],
            "true": [
                "https://verafiles.org/articles/category/updates",
                "https://verafiles.org/articles/category/features",
                "https://verafiles.org/articles/category/profiles",
                "https://verafiles.org/articles/category/commentary"
            ]
        }

    def get_soup(self, url):
        for i in range(3):
            try:
                time.sleep(1)
                response = self.session.get(url, headers=self.headers, timeout=20)
                if response.status_code == 200:
                    return BeautifulSoup(response.text, "html.parser")
                elif response.status_code == 404:
                    print(f"      ❌ Page not found: {url}")
                    return None
            except Exception:
                time.sleep(1)
        return None

    def clean_text(self, text):
        if not text: return ""
        return re.sub(r'\s+', ' ', text).strip()

    def get_full_content(self, url):
        soup = self.get_soup(url)
        if not soup: return ""
        
        content = soup.find("div", class_="uk-article-content")
        if not content: content = soup.find("div", class_="entry-content")
        if not content: content = soup.find("div", class_="article-content")
        
        if content:
            paragraphs = content.find_all('p')
            return self.clean_text(" ".join([p.get_text() for p in paragraphs]))
        return ""

    def scrape_section(self, category_type, target_count):
        print(f"\n🚀 Starting scrape for '{category_type.upper()}' articles...")
        collected_data = []
        url_list = self.urls[category_type]
        
        for base_url in url_list:
            if len(collected_data) >= target_count: break
            print(f"   👉 Source: {base_url}")
            page = 1
            consecutive_empty = 0
            
            while len(collected_data) < target_count:
                separator = "&" if "?" in base_url else "?"
                current_url = f"{base_url}{separator}page={page}"
                soup = self.get_soup(current_url)
                if not soup: break
                
                all_links = soup.find_all("a", href=True)
                found_on_page = 0
                
                for link in all_links:
                    if len(collected_data) >= target_count: break
                    href = link['href']
                    title = link.get_text(strip=True)
                    
                    is_article = '/articles/' in href and '/category/' not in href
                    
                    if is_article and len(title) > 20:
                        full_url = href if href.startswith("http") else "https://verafiles.org" + href
                        if any(d['url'] == full_url for d in collected_data): continue
                        
                        label = "Fake" if category_type == "fake" else "True"
                        text = self.get_full_content(full_url)
                        
                        if text and len(text) > 100:
                            print(f"      ✅ Added: {title[:40]}... [{label}]")
                            collected_data.append({
                                "text": text,
                                "label": label,
                                "category": category_type,
                                "title": title,
                                "url": full_url,
                                "source": "Vera Files"
                            })
                            found_on_page += 1
                            time.sleep(0.2) 

                print(f"      📄 Page {page}: Found {found_on_page} items. (Total: {len(collected_data)}/{target_count})")
                
                if found_on_page == 0:
                    consecutive_empty += 1
                else:
                    consecutive_empty = 0

                if consecutive_empty >= 3:
                    print("      ❌ Source exhausted. Switching URL...")
                    break
                page += 1
                if page > 100: break 
            
        return pd.DataFrame(collected_data)

    def run_full_scrape(self, samples_per_class):
        # 1. Scrape Fake
        df_fake = self.scrape_section("fake", target_count=samples_per_class)
        # 2. Scrape True
        df_true = self.scrape_section("true", target_count=samples_per_class)
        
        print("\n" + "="*40)
        print(f"📊 FINAL COLLECTION COUNTS:")
        print(f"   🔴 Fake: {len(df_fake)}")
        print(f"   🟢 True: {len(df_true)}")
        print("="*40)

        # NO BALANCING - Just Merge
        final_df = pd.concat([df_fake, df_true])
        # Shuffle rows just so they aren't ordered by class
        final_df = final_df.sample(frac=1, random_state=42).reset_index(drop=True)
        
        return final_df

if __name__ == "__main__":
    scraper = VeraFilesScraper()
    final_dataset = scraper.run_full_scrape(samples_per_class=TARGET_SAMPLES_PER_CLASS)
    
    if final_dataset is not None and not final_dataset.empty:
        filename = "VeraFiles_Full_Dataset.csv"
        final_dataset.to_csv(filename, index=False, encoding="utf-8-sig")
        print(f"\n🎉 SUCCESS! Saved {len(final_dataset)} rows to {filename}")
        print(final_dataset['label'].value_counts())
    else:
        print("\n❌ No data collected.")