import cloudscraper
import re
from bs4 import BeautifulSoup
from datetime import datetime

# Check the structure of MatchTV website to identify live broadcasts
def check_live_broadcasts():
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
        
        # Find channel transmission elements
        channel_elements = soup.find_all('div', class_='p-tv-guide-schedule-channel-transmission')
        
        print(f"Found {len(channel_elements)} channel transmission elements")
        
        # Check for live indicators
        live_elements = []
        future_elements = []
        
        current_time = datetime.now()
        current_hour = current_time.hour
        current_minute = current_time.minute
        
        print(f"Current time: {current_hour:02d}:{current_minute:02d}")
        
        for i, element in enumerate(channel_elements[:10]):  # Check first 10 elements
            text_content = element.get_text()
            lower_text = text_content.lower()
            
            # Extract time
            time_elem = element.find(class_='p-tv-guide-schedule-channel-transmission__time-block')
            time_str = time_elem.get_text().strip() if time_elem else "N/A"
            
            print(f"\nElement {i+1}:")
            print(f"  Time: {time_str}")
            print(f"  Content: {text_content[:100]}...")
            
            # Check for live indicators
            if 'live' in lower_text or 'прямая' in lower_text or 'онлайн' in lower_text:
                print(f"  -> Contains live indicators")
                live_elements.append(element)
            else:
                print(f"  -> No live indicators")
                
            # Check time comparison
            if time_str != "N/A" and ':' in time_str:
                try:
                    hour, minute = map(int, time_str.split(':'))
                    # Compare with current time
                    if hour > current_hour or (hour == current_hour and minute >= current_minute):
                        print(f"  -> Future or current broadcast")
                        future_elements.append(element)
                    else:
                        print(f"  -> Past broadcast")
                except ValueError:
                    print(f"  -> Could not parse time")
        
        print(f"\nLive elements found: {len(live_elements)}")
        print(f"Future elements found: {len(future_elements)}")
        
    except Exception as e:
        print(f"Error: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    check_live_broadcasts()