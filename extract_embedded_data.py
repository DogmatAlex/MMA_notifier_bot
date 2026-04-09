import cloudscraper
import re
import json
from bs4 import BeautifulSoup
from datetime import datetime

# Extract embedded data from MatchTV script
def extract_embedded_data():
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
                
                # The data is embedded in a function call like:
                # self.__next_f.push([1,"1b:[\"$\",\"$L53\",null,{\"channel\":\"$undefined\",\"channels\":[{\"id\":10,...
                # We need to extract the JSON part
                
                # Look for the pattern that contains schedule data
                # Find the part after "schedule":[
                schedule_start = script_content.find('"schedule":[')
                if schedule_start != -1:
                    print(f"Found schedule start at position {schedule_start}")
                    
                    # Extract from schedule start to a reasonable end
                    # We'll look for the end of the schedule array
                    schedule_content = script_content[schedule_start:]
                    
                    # Find the end of the schedule array by counting brackets
                    bracket_count = 0
                    end_pos = -1
                    for i, char in enumerate(schedule_content):
                        if char == '[':
                            bracket_count += 1
                        elif char == ']':
                            bracket_count -= 1
                            if bracket_count == 0:
                                end_pos = i + 1
                                break
                    
                    if end_pos != -1:
                        schedule_json = schedule_content[:end_pos]
                        print(f"Extracted schedule JSON: {schedule_json[:200]}...")
                        
                        # Now we need to parse this JSON
                        # It's in the format "schedule":[{...},{...},...]
                        # We need to extract the array part
                        array_start = schedule_json.find('[')
                        array_end = schedule_json.rfind(']') + 1
                        
                        if array_start != -1 and array_end > array_start:
                            array_json = schedule_json[array_start:array_end]
                            print(f"Array JSON: {array_json[:100]}...")
                            
                            # Parse the array
                            try:
                                schedule_items = json.loads(array_json)
                                print(f"Successfully parsed {len(schedule_items)} schedule items")
                                
                                # Process the items
                                for item in schedule_items:
                                    # Fix escaped quotes
                                    if 'title' in item:
                                        item['title'] = item['title'].replace('\\"', '"')
                                    schedule_data.append(item)
                                    
                            except json.JSONDecodeError as e:
                                print(f"JSON decode error: {e}")
                                # Try manual parsing
                                manual_parse_schedule(array_json, schedule_data)
                    else:
                        print("Could not find end of schedule array")
                else:
                    print("Could not find schedule start")
        
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

def manual_parse_schedule(array_json, schedule_data):
    """Manually parse schedule data if JSON parsing fails"""
    print("Attempting manual parsing...")
    
    # Look for individual schedule items
    # Pattern: {"time":"HH:MM","title":"...","genre":"...","current":true|false}
    item_pattern = re.compile(r'\{"time":"(\d{1,2}:\d{2})","title":"([^"]*[^\\])","genre":"([^"]*)","current":(true|false)\}')
    matches = item_pattern.findall(array_json)
    
    print(f"Found {len(matches)} matches through manual parsing")
    
    for time_str, title, genre, current_str in matches:
        current = current_str == 'true'
        schedule_data.append({
            'time': time_str,
            'title': title.replace('\\"', '"'),  # Unescape quotes
            'genre': genre,
            'current': current
        })

if __name__ == "__main__":
    extract_embedded_data()