import cloudscraper
from bs4 import BeautifulSoup
import pandas as pd
import time
import re
from urllib.parse import urlparse

# ==========================================
# 👇 CONFIGURATION 👇
# ==========================================
TARGET_SAMPLES_PER_CLASS = 1500
# ==========================================

class PressOneHarvester:
    def __init__(self):
        self.scraper = cloudscraper.create_scraper(
            browser={'browser': 'chrome', 'platform': 'windows', 'desktop': True}
        )
        self.base_domain = "https://pressone.ph"
        self.seen_urls = set()
        
        # We define "Fake" and "True" sources clearly
        self.config = {
            "fake": {
                "start_urls": ["https://pressone.ph/fact-check/"],
                "must_contain": "/fact-check/" # Links must have this to be valid
            },
            "true": {
                "start_urls": ["https://pressone.ph/news/", "https://pressone.ph/opinion/"],
                "must_contain": "" # News often has varied structure, so we are looser here
            }
        }

    def get_soup(self, url):
        for i in range(3):
            try:
                time.sleep(2) 
                response = self.scraper.get(url, timeout=30)
                if response.status_code == 200:
                    return BeautifulSoup(response.text, "html.parser"), response.url
                elif response.status_code == 404:
                    return None, None
            except Exception as e:
                print(f"      ❌ Error: {e}")
                time.sleep(2)
        return None, None

    def clean_text(self, text):
        if not text: return ""
        text = re.sub(r'Follow us on.*', '', text, flags=re.IGNORECASE)
        text = re.sub(r'Editor’s Note:.*', '', text, flags=re.IGNORECASE)
        return re.sub(r'\s+', ' ', text).strip()

    def get_full_content(self, url):
        soup, _ = self.get_soup(url)
        if not soup: return ""
        
        # Try finding the content body
        content = soup.find("div", class_="entry-content")
        if not content: content = soup.find("div", class_="post-content")
        if not content: content = soup.find("article")
        
        if content:
            # Clean junk
            for junk in content.find_all(['script', 'style', 'div.sharedaddy', 'div.jp-relatedposts']):
                junk.decompose()
            return self.clean_text(" ".join([p.get_text() for p in content.find_all('p')]))
        return ""

    def scrape_category(self, category_type, target_count):
        print(f"\n🚀 Starting scrape for PRESSONE '{category_type.upper()}'...")
        collected_data = []
        cfg = self.config[category_type]
        
        for base_url in cfg['start_urls']:
            if len(collected_data) >= target_count: break
            print(f"   👉 Source: {base_url}")
            
            page = 1
            consecutive_empty = 0
            
            while len(collected_data) < target_count:
                # Construct pagination URL
                url_to_fetch = base_url if page == 1 else f"{base_url}page/{page}/"
                
                soup, final_url = self.get_soup(url_to_fetch)
                if not soup: break
                
                # Check for redirects (End of pagination)
                if page > 1 and final_url.rstrip('/') == base_url.rstrip('/'):
                    print("      🛑 Redirected to home. End of list.")
                    break

                # === 🔍 HARVESTER LOGIC ===
                # Instead of looking for <article>, we look for ALL links
                all_links = soup.find_all("a", href=True)
                found_on_page = 0
                
                for link in all_links:
                    if len(collected_data) >= target_count: break
                    
                    href = link['href']
                    title = link.get_text(strip=True)
                    
                    # 1. Deduplication
                    if href in self.seen_urls: continue
                    
                    # 2. Strict Filter: Link must be an article, not a category/tag page
                    # It must NOT contain 'page', 'category', 'tag', 'author'
                    if any(x in href for x in ['/page/', '/category/', '/tag/', '/author/', '#']):
                        continue
                        
                    # 3. Content Filter: Must match the category type (e.g., /fact-check/)
                    if cfg['must_contain'] and cfg['must_contain'] not in href:
                        continue
                        
                    # 4. Heuristic: Real headlines are usually 25+ characters
                    if len(title) < 25: 
                        continue

                    # 5. Fetch Content
                    # Optimization: Only scrape if we are sure it's a new link
                    self.seen_urls.add(href)
                    text = self.get_full_content(href)
                    
                    if text and len(text) > 150:
                        print(f"      ✅ Added: {title[:35]}... [{category_type}]")
                        collected_data.append({
                            "text": text,
                            "label": "Fake" if category_type == "fake" else "True",
                            "category": category_type,
                            "title": title,
                            "url": href,
                            "source": "PressOne.PH"
                        })
                        found_on_page += 1
                        time.sleep(0.5) # Be nice
                
                print(f"      📄 Page {page}: Found {found_on_page} items. (Total: {len(collected_data)}/{target_count})")
                
                if found_on_page == 0:
                    consecutive_empty += 1
                else:
                    consecutive_empty = 0

                if consecutive_empty >= 4:
                    print("      ❌ No valid links found for 4 pages. Moving on...")
                    break
                    
                page += 1
                if page > 150: break

        return pd.DataFrame(collected_data)

    def run(self):
        df_fake = self.scrape_category("fake", TARGET_SAMPLES_PER_CLASS)
        df_true = self.scrape_category("true", TARGET_SAMPLES_PER_CLASS)
        
        print("\n" + "="*40)
        print(f"📊 FINAL COUNTS:")
        print(f"   🔴 Fake: {len(df_fake)}")
        print(f"   🟢 True: {len(df_true)}")
        print("="*40)
        
        final_df = pd.concat([df_fake, df_true])
        if not final_df.empty:
            final_df.to_csv("PressOne_Harvester_Dataset.csv", index=False, encoding="utf-8-sig")
            print("🎉 Saved to PressOne_Harvester_Dataset.csv")

if __name__ == "__main__":
    scraper = PressOneHarvester()
    scraper.run()