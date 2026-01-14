import cloudscraper
from bs4 import BeautifulSoup
import pandas as pd
import time
import re

# ==========================================
# 👇 CONFIGURATION 👇
# ==========================================
TARGET_SAMPLES_PER_CLASS = 1500  # Adjusted slightly as MindaNews has high quality but specific volume
# ==========================================

class MindaNewsScraper:
    def __init__(self):
        # Use CloudScraper to be safe, though MindaNews is usually less strict than VeraFiles
        self.scraper = cloudscraper.create_scraper(
            browser={
                'browser': 'chrome',
                'platform': 'windows',
                'desktop': True
            }
        )
        self.base_domain = "https://mindanews.com"
        
        self.urls = {
            "fake": [
                "https://mindanews.com/category/fact-check/"
            ],
            "true": [
                "https://mindanews.com/category/top-stories/",
                "https://mindanews.com/category/peace-process/",
                "https://mindanews.com/category/environment/",
                "https://mindanews.com/category/business/"
            ]
        }

    def get_soup(self, url):
        for i in range(3):
            try:
                # Random sleep to act human
                time.sleep(3) 
                response = self.scraper.get(url, timeout=30)
                
                if response.status_code == 200:
                    return BeautifulSoup(response.text, "html.parser")
                elif response.status_code == 403:
                    print(f"      ⚠️  Blocked (403) at {url}. Waiting...")
                    time.sleep(10)
                else:
                    print(f"      ⚠️  Status {response.status_code} at {url}")
            except Exception as e:
                print(f"      ❌ Connection Error: {e}")
                time.sleep(2)
        return None

    def clean_text(self, text):
        if not text: return ""
        # Remove common MindaNews footer text
        text = re.sub(r'MindaNews is the news service arm.*', '', text, flags=re.IGNORECASE)
        text = re.sub(r'READ ALSO.*', '', text, flags=re.IGNORECASE)
        return re.sub(r'\s+', ' ', text).strip()

    def get_full_content(self, url):
        soup = self.get_soup(url)
        if not soup: return ""
        
        # MindaNews typically uses 'entry-content'
        content = soup.find("div", class_="entry-content")
        
        if content:
            # Remove junk
            for junk in content.find_all(['script', 'style', 'div.sharedaddy', 'div.jp-relatedposts']):
                junk.decompose()
            
            # Get text
            paragraphs = content.find_all('p')
            full_text = " ".join([p.get_text() for p in paragraphs])
            return self.clean_text(full_text)
        return ""

    def scrape_section(self, category_type, target_count):
        print(f"\n🚀 Starting scrape for MINDANEWS '{category_type.upper()}'...")
        collected_data = []
        url_list = self.urls[category_type]
        
        for base_url in url_list:
            if len(collected_data) >= target_count: break
            print(f"   👉 Source: {base_url}")
            page = 1
            consecutive_empty = 0
            
            while len(collected_data) < target_count:
                # WordPress pagination structure: /page/2/
                url_to_fetch = base_url if page == 1 else f"{base_url}page/{page}/"
                
                soup = self.get_soup(url_to_fetch)
                if not soup: break
                
                # MindaNews article headers are usually h2.entry-title
                article_headers = soup.find_all("h2", class_="entry-title")
                
                found_on_page = 0
                
                for header in article_headers:
                    if len(collected_data) >= target_count: break
                    link = header.find("a", href=True)
                    if not link: continue

                    href = link['href']
                    title = link.get_text(strip=True)
                    
                    # Filter valid links
                    if len(title) > 10:
                        if any(d['url'] == href for d in collected_data): continue
                        
                        label = "Fake" if category_type == "fake" else "True"
                        
                        # Optimization: Don't scrape content if title clearly indicates it's just a photo/caption
                        if "photo" in title.lower() and len(title) < 20:
                             continue

                        text = self.get_full_content(href)
                        
                        if text and len(text) > 150: 
                            print(f"      ✅ Added: {title[:40]}... [{label}]")
                            collected_data.append({
                                "text": text,
                                "label": label,
                                "category": category_type,
                                "title": title,
                                "url": href,
                                "source": "MindaNews"
                            })
                            found_on_page += 1
                            time.sleep(1) 

                print(f"      📄 Page {page}: Found {found_on_page} items. (Total: {len(collected_data)}/{target_count})")
                
                if found_on_page == 0:
                    consecutive_empty += 1
                else:
                    consecutive_empty = 0

                if consecutive_empty >= 3:
                    print("      ❌ Source exhausted. Moving to next URL...")
                    break
                page += 1
                if page > 30: break 
            
        return pd.DataFrame(collected_data)

    def run_full_scrape(self, samples_per_class):
        df_fake = self.scrape_section("fake", target_count=samples_per_class)
        df_true = self.scrape_section("true", target_count=samples_per_class)
        
        print("\n" + "="*40)
        print(f"📊 FINAL MINDANEWS COUNTS:")
        print(f"   🔴 Fake (Fact Checks): {len(df_fake)}")
        print(f"   🟢 True (News): {len(df_true)}")
        print("="*40)

        final_df = pd.concat([df_fake, df_true])
        if not final_df.empty:
            final_df = final_df.sample(frac=1, random_state=42).reset_index(drop=True)
        
        return final_df

if __name__ == "__main__":
    scraper = MindaNewsScraper()
    final_dataset = scraper.run_full_scrape(samples_per_class=TARGET_SAMPLES_PER_CLASS)
    
    if final_dataset is not None and not final_dataset.empty:
        filename = "MindaNews_Full_Dataset.csv"
        final_dataset.to_csv(filename, index=False, encoding="utf-8-sig")
        print(f"\n🎉 SUCCESS! Saved {len(final_dataset)} rows to {filename}")
    else:
        print("\n❌ No data collected.")