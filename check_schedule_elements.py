import cloudscraper
import re
from bs4 import BeautifulSoup
from datetime import datetime

# Check for schedule elements
def check_schedule_elements():
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
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:89.0) Gecko/20100101 Firefox/89.0',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
            'Accept-Language': 'ru-RU,ru;q=0.8,en-US;q=0.5,en;q=0.3',
            'Accept-Encoding': 'gzip, deflate',
            'Connection': 'keep-alive',
            'Upgrade-Insecure-Requests': '1',
        }
        
        # Try to get the schedule page
        url = "https://matchtv.ru/tvguide"
        response = scraper.get(url, headers=headers, timeout=15)
        
        if response.status_code != 200:
            print(f"Failed to fetch {url}, status code: {response.status_code}")
            return
        
        # Parse the HTML content
        soup = BeautifulSoup(response.content, 'html.parser')
        
        # Look for schedule-related elements
        schedule_elements = soup.find_all(class_=re.compile(r'p-tv-guide-schedule', re.I))
        print(f"Found {len(schedule_elements)} schedule elements")
        
        # Look for channel elements
        channel_elements = soup.find_all(class_=re.compile(r'channel', re.I))
        print(f"Found {len(channel_elements)} channel elements")
        
        # Look for transmission elements specifically
        transmission_elements = soup.find_all(class_=re.compile(r'transmission', re.I))
        print(f"Found {len(transmission_elements)} transmission elements")
        
        # Look for carcass elements (might contain schedule info)
        carcass_elements = soup.find_all(class_=re.compile(r'carcass', re.I))
        print(f"Found {len(carcass_elements)} carcass elements")
        
        # Check carcass elements for sports content
        sports_carcass = []
        for element in carcass_elements:
            text_content = element.get_text()
            lower_text = text_content.lower()
            
            # Check if this element contains football or MMA/UFC
            if ('футбол' in lower_text or 'mma' in lower_text or 
                'ufc' in lower_text or 'единоборства' in lower_text or
                'прямая трансляция' in lower_text):
                sports_carcass.append((element, text_content))
        
        print(f"Found {len(sports_carcass)} sports carcass elements")
        
        # Show first 5 sports carcass elements
        for i, (element, text_content) in enumerate(sports_carcass[:5]):
            print(f"\nSports Carcass Element {i+1}:")
            print(f"  Classes: {element.get('class')}")
            print(f"  Text: {text_content[:200]}...")
            
            # Extract time if present
            time_pattern = re.compile(r'\d{1,2}:\d{2}')
            time_match = time_pattern.search(text_content)
            if time_match:
                print(f"  Time: {time_match.group()}")
            
            # Check for live indicators
            if 'прямая трансляция' in text_content.lower():
                print(f"  -> Contains 'прямая трансляция'")
            if 'live' in text_content.lower():
                print(f"  -> Contains 'live'")
                
    except Exception as e:
        print(f"Error: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    check_schedule_elements()