import requests
from bs4 import BeautifulSoup
import pandas as pd
import time
import re
import datetime

# ==========================================
# 👇 CONFIGURATION 👇
# ==========================================
TARGET_SAMPLES_PER_CLASS = 3000
# ==========================================

class RapplerScraper:
    def __init__(self):
        self.headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8"
        }
        self.session = requests.Session()
        
        self.urls = {
            "fake": ["https://www.rappler.com/section/newsbreak/fact-check/"],
            "true": [
                "https://www.rappler.com/section/nation/",
                "https://www.rappler.com/section/business/",
                "https://www.rappler.com/section/life-and-style/"
            ]
        }

    def get_soup(self, url):
        for i in range(3):
            try:
                time.sleep(2) # Rappler needs slow requests
                response = self.session.get(url, headers=self.headers, timeout=25)
                if response.status_code == 200:
                    return BeautifulSoup(response.text, "html.parser")
            except Exception:
                time.sleep(2)
        return None

    def clean_text(self, text):
        if not text: return ""
        return re.sub(r'\s+', ' ', text).strip()

    def get_full_content(self, url):
        soup = self.get_soup(url)
        if not soup: return ""
        
        content = soup.find("div", class_="post-content")
        if not content: content = soup.find("div", class_="entry-content")
        if not content: content = soup.find("article")
        
        if content:
            for junk in content.find_all(['script', 'style', 'div.share-bar']):
                junk.decompose()
            paragraphs = content.find_all('p')
            return self.clean_text(" ".join([p.get_text() for p in paragraphs]))
        return ""

    def scrape_section(self, category_type, target_count):
        print(f"\n🚀 Starting scrape for RAPPLER '{category_type.upper()}'...")
        collected_data = []
        url_list = self.urls[category_type]
        
        for base_url in url_list:
            if len(collected_data) >= target_count: break
            print(f"   👉 Source: {base_url}")
            page = 1
            consecutive_empty = 0
            
            while len(collected_data) < target_count:
                if page == 1: current_url = base_url
                else: current_url = f"{base_url}page/{page}/"

                soup = self.get_soup(current_url)
                if not soup: break
                
                article_headers = soup.find_all("h3")
                found_on_page = 0
                
                for header in article_headers:
                    if len(collected_data) >= target_count: break
                    link = header.find("a", href=True)
                    if not link: continue

                    href = link['href']
                    title = link.get_text(strip=True)
                    
                    if len(title) > 20 and href.startswith("https://www.rappler.com/"):
                        if any(d['url'] == href for d in collected_data): continue
                        
                        label = "Fake" if category_type == "fake" else "True"
                        text = self.get_full_content(href)
                        
                        if text and len(text) > 150: 
                            print(f"      ✅ Added: {title[:40]}... [{label}]")
                            collected_data.append({
                                "text": text,
                                "label": label,
                                "category": category_type,
                                "title": title,
                                "url": href,
                                "source": "Rappler"
                            })
                            found_on_page += 1
                            time.sleep(0.5) 

                print(f"      📄 Page {page}: Found {found_on_page} items. (Total: {len(collected_data)}/{target_count})")
                
                if found_on_page == 0:
                    consecutive_empty += 1
                else:
                    consecutive_empty = 0

                if consecutive_empty >= 3:
                    print("      ❌ Source exhausted. Switching URL...")
                    break
                page += 1
                if page > 50: break 
            
        return pd.DataFrame(collected_data)

    def run_full_scrape(self, samples_per_class):
        df_fake = self.scrape_section("fake", target_count=samples_per_class)
        df_true = self.scrape_section("true", target_count=samples_per_class)
        
        print("\n" + "="*40)
        print(f"📊 FINAL RAPPLER COUNTS:")
        print(f"   🔴 Fake: {len(df_fake)}")
        print(f"   🟢 True: {len(df_true)}")
        print("="*40)

        # NO BALANCING - Just Merge
        final_df = pd.concat([df_fake, df_true])
        final_df = final_df.sample(frac=1, random_state=42).reset_index(drop=True)
        
        return final_df

if __name__ == "__main__":
    scraper = RapplerScraper()
    final_dataset = scraper.run_full_scrape(samples_per_class=TARGET_SAMPLES_PER_CLASS)
    
    if final_dataset is not None and not final_dataset.empty:
        filename = "Rappler_Full_Dataset.csv"
        final_dataset.to_csv(filename, index=False, encoding="utf-8-sig")
        print(f"\n🎉 SUCCESS! Saved {len(final_dataset)} rows to {filename}")
        print(final_dataset['label'].value_counts())
    else:
        print("\n❌ No data collected.")