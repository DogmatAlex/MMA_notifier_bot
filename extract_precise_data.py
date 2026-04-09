import cloudscraper
import re
import json
from bs4 import BeautifulSoup
from datetime import datetime

# Extract precise data from MatchTV script
def extract_precise_data():
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
                
                # Print a larger portion to see the exact format
                print("Script 51 content (first 2000 chars):")
                print(script_content[:2000])
                
                # Look for the exact pattern we saw in the output
                # "schedule":[{...}]
                # But we need to be more careful about matching brackets
                schedule_pattern = re.compile(r'"schedule":(\[.*?\])')
                schedule_matches = schedule_pattern.findall(script_content)
                
                print(f"\nFound {len(schedule_matches)} schedule matches with simple pattern")
                
                # Try a more sophisticated pattern that handles nested brackets
                # This is a bit tricky because we need to match balanced brackets
                schedule_pattern2 = re.compile(r'"schedule":(\[[^\[\]]*(?:\[[^\[\]]*\][^\[\]]*)*\])')
                schedule_matches2 = schedule_pattern2.findall(script_content)
                
                print(f"Found {len(schedule_matches2)} schedule matches with complex pattern")
                
                # Try another approach - look for the exact pattern we saw
                # "time":"06:00","title":"\"Чемпионат мира-2026. Обратный отсчёт\" [12+]"
                time_title_pattern = re.compile(r'\{"time":"(\d{1,2}:\d{2})","title":"([^"]+)"[^}]*"current":(true|false)')
                time_title_matches = time_title_pattern.findall(script_content)
                
                print(f"Found {len(time_title_matches)} time-title matches")
                
                # Convert to the format we want
                for time_str, title, current_str in time_title_matches:
                    current = current_str == 'true'
                    schedule_data.append({
                        'time': time_str,
                        'title': title.replace('\\"', '"'),  # Unescape quotes
                        'current': current
                    })
        
        print(f"\nTotal schedule items found: {len(schedule_data)}")
        
        # Show first 10 schedule items
        for i, item in enumerate(schedule_data[:10]):
            print(f"\nSchedule Item {i+1}:")
            print(f"  Time: {item.get('time', 'N/A')}")
            print(f"  Title: {item.get('title', 'N/A')}")
            print(f"  Current: {item.get('current', 'N/A')}")
                
        return schedule_data
                
    except Exception as e:
        print(f"Error: {e}")
        import traceback
        traceback.print_exc()
        return []

if __name__ == "__main__":
    extract_precise_data()