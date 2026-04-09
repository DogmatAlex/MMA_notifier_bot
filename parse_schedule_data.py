import cloudscraper
import re
import json
from bs4 import BeautifulSoup
from datetime import datetime

# Parse schedule data from MatchTV
def parse_schedule_data():
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
            return []
        
        # Parse the HTML content
        soup = BeautifulSoup(response.content, 'html.parser')
        
        # Look for script tags that might contain JSON data
        scripts = soup.find_all('script')
        print(f"Found {len(scripts)} script tags")
        
        # Focus on script 51 which seemed to contain schedule data
        schedule_data = []
        if len(scripts) > 51:
            script_51 = scripts[51]
            if script_51.string:
                script_content = script_51.string
                print(f"Script 51 content length: {len(script_content)}")
                
                # Extract the JSON data using a more precise pattern
                # The data is in a format like: "schedule":[{...}]
                schedule_pattern = re.compile(r'"schedule":(\[\{.*?\}\])')
                schedule_matches = schedule_pattern.findall(script_content)
                
                print(f"Found {len(schedule_matches)} schedule matches")
                
                for i, schedule_json in enumerate(schedule_matches):
                    try:
                        # Try to parse the schedule JSON
                        schedule_items = json.loads(schedule_json)
                        print(f"Schedule {i+1} has {len(schedule_items)} items")
                        
                        # Add items to our schedule data
                        for item in schedule_items:
                            schedule_data.append(item)
                    except json.JSONDecodeError as e:
                        print(f"JSON decode error for schedule {i+1}: {e}")
                        # Try to fix common issues
                        # Remove escaped quotes
                        fixed_json = schedule_json.replace('\\"', '"')
                        try:
                            schedule_items = json.loads(fixed_json)
                            print(f"Fixed JSON for schedule {i+1}, has {len(schedule_items)} items")
                            for item in schedule_items:
                                schedule_data.append(item)
                        except json.JSONDecodeError:
                            print(f"Still couldn't parse schedule {i+1}")
        
        print(f"\nTotal schedule items found: {len(schedule_data)}")
        
        # Show first 10 schedule items
        for i, item in enumerate(schedule_data[:10]):
            print(f"\nSchedule Item {i+1}:")
            print(f"  Time: {item.get('time', 'N/A')}")
            print(f"  Title: {item.get('title', 'N/A')}")
            print(f"  Current: {item.get('current', 'N/A')}")
            if 'genre' in item:
                print(f"  Genre: {item['genre']}")
                
        return schedule_data
                
    except Exception as e:
        print(f"Error: {e}")
        import traceback
        traceback.print_exc()
        return []

if __name__ == "__main__":
    parse_schedule_data()