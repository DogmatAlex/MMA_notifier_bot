#!/usr/bin/env python3
"""
Save HTML content for analysis
"""

import logging
import cloudscraper

# Configure logging
logging.basicConfig(level=logging.INFO)

def save_html():
    """Save HTML content for analysis"""
    try:
        # Use cloudscraper to avoid being blocked by the website
        scraper = cloudscraper.create_scraper(
            browser={
                'browser': 'firefox',
                'platform': 'windows',
                'mobile': False
            }
        )
        
        # Use headers to avoid being blocked by the website
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
            'Accept-Language': 'ru-RU,ru;q=0.9,en-US;q=0.8,en;q=0.7',
            'Accept-Encoding': 'gzip, deflate, br',
            'Connection': 'keep-alive',
            'Upgrade-Insecure-Requests': '1',
            'Sec-Fetch-Dest': 'document',
            'Sec-Fetch-Mode': 'navigate',
            'Sec-Fetch-Site': 'none',
            'Cache-Control': 'max-age=0'
        }
        
        # Try different URLs for parsing
        urls = [
            "https://matchtv.ru/tvguide",
            "https://matchtv.ru/on-air"
        ]
        
        response_text = ""
        
        for url in urls:
            try:
                logging.info(f"Trying to fetch {url}")
                response = scraper.get(url, headers=headers, timeout=15)
                
                if response.status_code == 200:
                    response_text = response.text
                    logging.info(f"Successfully fetched {url}")
                    break
                else:
                    logging.warning(f"Failed to fetch {url}, status code: {response.status_code}")
            except Exception as e:
                logging.warning(f"Error fetching {url}: {e}")
                continue
        
        if not response_text:
            raise Exception("Failed to fetch any URL")
        
        # Save the HTML content to a file
        with open("matchtv_page.html", "w", encoding="utf-8") as f:
            f.write(response_text)
        
        logging.info(f"Saved HTML content to matchtv_page.html, length: {len(response_text)}")
        
        # Also save a truncated version for easier viewing
        with open("matchtv_page_truncated.html", "w", encoding="utf-8") as f:
            f.write(response_text[:50000])  # First 50KB should be enough for analysis
        
        logging.info("Saved truncated HTML content to matchtv_page_truncated.html")
        
    except Exception as e:
        logging.error(f"Error saving HTML: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    save_html()