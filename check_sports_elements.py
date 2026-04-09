import cloudscraper
import re
from bs4 import BeautifulSoup

# Check for sports elements
def check_sports_elements():
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
        
        # Look for elements containing sports keywords
        all_divs = soup.find_all('div')
        sports_elements = []
        
        for element in all_divs:
            text_content = element.get_text()
            lower_text = text_content.lower()
            
            # Check if this element contains football or MMA/UFC
            if ('футбол' in lower_text or 'mma' in lower_text or 
                'ufc' in lower_text or 'единоборства' in lower_text):
                sports_elements.append((element, text_content))
        
        print(f"Found {len(sports_elements)} sports elements")
        
        # Show first 10 sports elements
        for i, (element, text_content) in enumerate(sports_elements[:10]):
            print(f"\nSports Element {i+1}:")
            print(f"  Classes: {element.get('class')}")
            print(f"  Text: {text_content[:150]}...")
            
            # Check for live indicators
            if 'прямая трансляция' in text_content.lower():
                print(f"  -> Contains 'прямая трансляция'")
            if 'live' in text_content.lower():
                print(f"  -> Contains 'live'")
                
        # Look for elements with time information
        time_pattern = re.compile(r'\d{1,2}:\d{2}')
        time_elements = []
        
        for element in all_divs:
            text_content = element.get_text()
            if time_pattern.search(text_content):
                time_elements.append((element, text_content))
        
        print(f"\nFound {len(time_elements)} elements with time information")
        
        # Show first 10 time elements
        for i, (element, text_content) in enumerate(time_elements[:10]):
            print(f"\nTime Element {i+1}:")
            print(f"  Classes: {element.get('class')}")
            print(f"  Text: {text_content[:100]}...")
        
    except Exception as e:
        print(f"Error: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    check_sports_elements()