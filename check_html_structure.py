import cloudscraper
import re
from bs4 import BeautifulSoup

# Check the HTML structure
def check_html_structure():
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
        
        # Print first 2000 characters of the HTML to understand structure
        html_str = str(soup)
        print("First 2000 characters of HTML:")
        print(html_str[:2000])
        
        # Look for script tags that might contain JSON data
        scripts = soup.find_all('script')
        print(f"\nFound {len(scripts)} script tags")
        
        # Look for scripts with sports data
        for i, script in enumerate(scripts):
            if script.string:
                script_content = script.string
                if ('футбол' in script_content.lower() or 'mma' in script_content.lower() or 
                    'ufc' in script_content.lower() or 'единоборства' in script_content.lower()):
                    print(f"\nScript {i} contains sports keywords:")
                    print(f"  Content length: {len(script_content)}")
                    # Print first 500 characters
                    print(f"  First 500 chars: {script_content[:500]}...")
                    
    except Exception as e:
        print(f"Error: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    check_html_structure()