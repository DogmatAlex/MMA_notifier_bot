import cloudscraper
import re
from bs4 import BeautifulSoup
from datetime import datetime

# Check the full page structure
def check_full_page():
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
        
        # Get the full text content
        full_text = soup.get_text()
        print(f"Full text length: {len(full_text)}")
        
        # Look for sports-related sections
        sports_sections = []
        
        # Split text into lines and look for patterns
        lines = full_text.split('\n')
        for i, line in enumerate(lines):
            lower_line = line.lower().strip()
            if lower_line and ('футбол' in lower_line or 'mma' in lower_line or 
                              'ufc' in lower_line or 'единоборства' in lower_line):
                # Check if this line contains time information
                time_pattern = re.compile(r'\d{1,2}:\d{2}')
                if time_pattern.search(line):
                    sports_sections.append((i, line))
        
        print(f"Found {len(sports_sections)} sports lines with time")
        
        # Show first 20 sports lines with time
        for i, (line_num, line) in enumerate(sports_sections[:20]):
            print(f"\nSports Line {i+1} (Line {line_num}):")
            print(f"  {line[:200]}...")
            
            # Check for live indicators
            if 'прямая трансляция' in line.lower():
                print(f"  -> Contains 'прямая трансляция'")
            if 'live' in line.lower():
                print(f"  -> Contains 'live'")
                
    except Exception as e:
        print(f"Error: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    check_full_page()