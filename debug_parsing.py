#!/usr/bin/env python3
"""
Debug script to check parsing functionality
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

def debug_matchtv_parsing():
    """Debug the MatchTV parsing functionality"""
    print("Debugging MatchTV parsing...")
    
    # Test URLs
    urls = [
        "https://matchtv.ru/tvguide",
        "https://matchtv.ru/on-air",
        "https://matchtv.ru/vtoroj-kanal"
    ]
    
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
    
    for url in urls:
        print(f"\nTesting URL: {url}")
        try:
            response = scraper.get(url, headers=headers, timeout=15)
            
            if response.status_code != 200:
                print(f"  Failed to fetch {url}, status code: {response.status_code}")
                continue
            
            # Parse the HTML content
            soup = BeautifulSoup(response.content, 'html.parser')
            
            # Print page title
            title = soup.find('title')
            print(f"  Page title: {title.get_text().strip() if title else 'No title'}")
            
            # Look for elements containing "Прямая трансляция"
            print("  Searching for elements containing 'Прямая трансляция'...")
            
            # Method 1: Search all text nodes
            text_elements = soup.find_all(text=lambda text: text and 'прямая трансляция' in text.lower())
            print(f"  Found {len(text_elements)} text elements with 'прямая трансляция'")
            
            # Method 2: Search all div elements
            div_elements = soup.find_all('div')
            live_elements = []
            for element in div_elements:
                text_content = element.get_text()
                if 'прямая трансляция' in text_content.lower():
                    live_elements.append(element)
            
            print(f"  Found {len(live_elements)} div elements with 'прямая трансляция'")
            
            # Show first few elements
            for i, element in enumerate(live_elements[:3]):
                print(f"    Element {i+1}: {element.get_text().strip()[:100]}...")
                
            # Method 3: Try to find schedule elements with different class names
            class_patterns = [
                'schedule', 'transmission', 'broadcast', 'event', 'guide', 'tv',
                'channel', 'program', 'match', 'game', 'sport'
            ]
            
            print("  Searching for elements with schedule-related classes...")
            for pattern in class_patterns:
                elements = soup.find_all(class_=lambda x: x and pattern in x.lower())
                if elements:
                    print(f"    Found {len(elements)} elements with class containing '{pattern}'")
                    # Show first element text
                    if elements:
                        print(f"      First element text: {elements[0].get_text().strip()[:100]}...")
                        
        except Exception as e:
            print(f"  Error fetching {url}: {e}")

if __name__ == "__main__":
    debug_matchtv_parsing()