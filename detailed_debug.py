#!/usr/bin/env python3
"""
Detailed debug script to check parsing functionality
"""

import os
import sys
import logging
import cloudscraper
from bs4 import BeautifulSoup

# Add project directory to path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

# Configure logging
logging.basicConfig(level=logging.INFO)

def detailed_debug():
    """Detailed debug of the MatchTV parsing functionality"""
    print("Detailed debugging MatchTV parsing...")
    
    url = "https://matchtv.ru/tvguide"
    
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
    
    print(f"\nTesting URL: {url}")
    try:
        response = scraper.get(url, headers=headers, timeout=15)
        
        if response.status_code != 200:
            print(f"  Failed to fetch {url}, status code: {response.status_code}")
            return
        
        # Parse the HTML content
        soup = BeautifulSoup(response.content, 'html.parser')
        
        # Print page title
        title = soup.find('title')
        print(f"  Page title: {title.get_text().strip() if title else 'No title'}")
        
        # Look for elements containing "Прямая трансляция"
        print("  Searching for elements containing 'Прямая трансляция'...")
        
        # Method 1: Search all div elements
        div_elements = soup.find_all('div')
        live_elements = []
        for element in div_elements:
            text_content = element.get_text()
            if 'прямая трансляция' in text_content.lower():
                live_elements.append((element, text_content))
        
        print(f"  Found {len(live_elements)} div elements with 'прямая трансляция'")
        
        # Show first few elements with more details
        for i, (element, text_content) in enumerate(live_elements[:5]):
            print(f"\n    Element {i+1}:")
            print(f"      Text: {text_content.strip()[:200]}...")
            print(f"      Class: {element.get('class', 'No class')}")
            print(f"      ID: {element.get('id', 'No ID')}")
            print(f"      Parent tag: {element.parent.name if element.parent else 'No parent'}")
            
            # Show parent structure
            parent = element.parent
            level = 0
            while parent and level < 3:
                print(f"        Parent {level+1}: {parent.name} - Class: {parent.get('class', 'No class')}")
                parent = parent.parent
                level += 1
                
    except Exception as e:
        print(f"  Error fetching {url}: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    detailed_debug()