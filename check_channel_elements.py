import cloudscraper
import re
from bs4 import BeautifulSoup
from datetime import datetime

# Check channel elements in detail
def check_channel_elements():
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
        
        # Look for channel elements
        channel_elements = soup.find_all(class_=re.compile(r'channel', re.I))
        print(f"Found {len(channel_elements)} channel elements")
        
        # Check each channel element for sports content
        sports_channels = []
        for element in channel_elements:
            text_content = element.get_text()
            lower_text = text_content.lower()
            
            # Check if this element contains football or MMA/UFC
            if ('футбол' in lower_text or 'mma' in lower_text or 
                'ufc' in lower_text or 'единоборства' in lower_text or
                'прямая трансляция' in lower_text):
                sports_channels.append((element, text_content))
        
        print(f"Found {len(sports_channels)} sports channel elements")
        
        # Show first 10 sports channel elements
        for i, (element, text_content) in enumerate(sports_channels[:10]):
            print(f"\nSports Channel Element {i+1}:")
            print(f"  Classes: {element.get('class')}")
            print(f"  Text: {text_content[:300]}...")
            
            # Extract time if present
            time_pattern = re.compile(r'\d{1,2}:\d{2}')
            time_matches = time_pattern.findall(text_content)
            if time_matches:
                print(f"  Times found: {time_matches}")
            
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
    check_channel_elements()