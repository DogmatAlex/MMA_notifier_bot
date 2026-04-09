import cloudscraper
import re
from bs4 import BeautifulSoup

# Check what classes are available in the HTML
def check_classes():
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
        
        # Look for div elements and their classes
        div_elements = soup.find_all('div')
        print(f"Found {len(div_elements)} div elements")
        
        # Collect all class names
        all_classes = set()
        for element in div_elements:
            classes = element.get('class')
            if classes:
                for cls in classes:
                    all_classes.add(cls)
        
        print(f"Total unique class names: {len(all_classes)}")
        
        # Look for classes that might be related to schedule/broadcast
        schedule_classes = [cls for cls in all_classes if 'schedule' in cls.lower() or 'broadcast' in cls.lower() or 'transmission' in cls.lower()]
        print(f"Schedule-related classes: {schedule_classes}")
        
        # Look for classes with 'time' in them
        time_classes = [cls for cls in all_classes if 'time' in cls.lower()]
        print(f"Time-related classes: {time_classes}")
        
        # Look for any elements containing sports keywords
        all_text = soup.get_text().lower()
        if 'футбол' in all_text:
            print("Found 'футбол' in page content")
        if 'mma' in all_text:
            print("Found 'mma' in page content")
        if 'ufc' in all_text:
            print("Found 'ufc' in page content")
        if 'единоборства' in all_text:
            print("Found 'единоборства' in page content")
        if 'прямая трансляция' in all_text:
            print("Found 'прямая трансляция' in page content")
        if 'live' in all_text:
            print("Found 'live' in page content")
        
    except Exception as e:
        print(f"Error: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    check_classes()