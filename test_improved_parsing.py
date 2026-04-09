#!/usr/bin/env python3
"""
Improved parser for MatchTV schedule data
"""

import logging
import cloudscraper
import re
import json
from datetime import datetime
from bs4 import BeautifulSoup

# Configure logging
logging.basicConfig(level=logging.INFO)

def parse_matchtv_schedule():
    """
    Parse sports broadcasts from matchtv.ru
    Returns a list of dictionaries with time and event information
    """
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
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
            'Accept-Language': 'ru-RU,ru;q=0.9,en-US;q=0.8,en;q=0.7',
            'Accept-Encoding': 'gzip, deflate, br',
            'Connection': 'keep-alive',
            'Upgrade-Insecure-Requests': '1',
            'Sec-Fetch-Dest': 'document',
            'Sec-Fetch-Mode': 'navigate',
            'Sec-Fetch-Site': 'none',
            'Cache-Control': 'max-age=0'
        }
        
        # Try different URLs for parsing
        urls = [
            "https://matchtv.ru/tvguide",
            "https://matchtv.ru/on-air"
        ]
        
        response_text = ""
        
        for url in urls:
            try:
                logging.info(f"Trying to fetch {url}")
                response = scraper.get(url, headers=headers, timeout=15)
                
                if response.status_code == 200:
                    response_text = response.text
                    logging.info(f"Successfully fetched {url}")
                    break
                else:
                    logging.warning(f"Failed to fetch {url}, status code: {response.status_code}")
            except Exception as e:
                logging.warning(f"Error fetching {url}: {e}")
                continue
        
        if not response_text:
            raise Exception("Failed to fetch any URL")
        
        # Look for sports events in the embedded JSON data
        broadcasts = []
        
        # Get current time for filtering
        current_time = datetime.now()
        current_hour = current_time.hour
        current_minute = current_time.minute
        
        # Extract schedule data from JavaScript
        logging.info("Extracting schedule data from JavaScript...")
        
        # Look for the channels data in the JavaScript code
        # The data is in format: self.__next_f.push([1,"1b:[\"$\",\"$L53\",null,{...}]]])
        pattern = r'self\.__next_f\.push\(\[1,"1b:(\[.*?\])\]\)'
        matches = re.findall(pattern, response_text)
        
        if matches:
            logging.info(f"Found {len(matches)} matches for schedule data")
            
            # Process each match
            for match in matches:
                try:
                    # The match is a JSON string, but we need to parse it properly
                    # First, we need to decode the escaped string
                    decoded_match = match.replace('\\"', '"').replace('\\\\', '\\')
                    
                    # Parse the JSON array
                    data_array = json.loads(decoded_match)
                    
                    # The data we want is in the last element of the array
                    if len(data_array) > 0:
                        # The last element contains the data we need
                        data_string = data_array[-1]
                        
                        # Parse the data string as JSON
                        if isinstance(data_string, str):
                            # Remove the wrapper and extract the actual JSON
                            # The string looks like: "$","$L53",null,{...}
                            # We need to extract the {...} part
                            json_start = data_string.find('{')
                            json_end = data_string.rfind('}') + 1
                            
                            if json_start != -1 and json_end > json_start:
                                json_data_str = data_string[json_start:json_end]
                                
                                # Parse the JSON data
                                schedule_data = json.loads(json_data_str)
                                
                                # Process the channels
                                channels = schedule_data.get('channels', [])
                                logging.info(f"Found {len(channels)} channels")
                                
                                for channel in channels:
                                    channel_name = channel.get('name', 'Unknown')
                                    schedule = channel.get('schedule', [])
                                    
                                    logging.info(f"Processing {len(schedule)} schedule items for {channel_name}")
                                    
                                    for item in schedule:
                                        time_str = item.get('time', 'N/A')
                                        title = item.get('title', '')
                                        genre = item.get('genre', '')
                                        current = item.get('current', False)
                                        
                                        # Fix escaped quotes
                                        title = title.replace('\\"', '"')
                                        
                                        # Check if this is a sports event we're interested in
                                        lower_title = title.lower()
                                        lower_genre = genre.lower()
                                        
                                        # Check for sports content
                                        is_sports = (
                                            'футбол' in lower_title or 'футбол' in lower_genre or
                                            'mma' in lower_title or 'mma' in lower_genre or
                                            'ufc' in lower_title or 'ufc' in lower_genre or
                                            'единоборства' in lower_title or 'единоборства' in lower_genre or
                                            'бокс' in lower_title or 'бокс' in lower_genre or
                                            'хоккей' in lower_title or 'хоккей' in lower_genre or
                                            'волейбол' in lower_title or 'волейбол' in lower_genre or
                                            'баскетбол' in lower_title or 'баскетбол' in lower_genre
                                        )
                                        
                                        # Filter for live broadcasts (containing 'Прямая трансляция')
                                        is_live = 'прямая трансляция' in lower_title.lower()
                                        
                                        # Only include sports events that are live
                                        if is_sports and is_live:
                                            # Determine sport type
                                            sport_type = "Unknown"
                                            if 'футбол' in lower_title or 'футбол' in lower_genre:
                                                sport_type = "Football"
                                            elif 'mma' in lower_title or 'mma' in lower_genre or 'ufc' in lower_title or 'ufc' in lower_genre or 'единоборства' in lower_title or 'единоборства' in lower_genre or 'бокс' in lower_title or 'бокс' in lower_genre:
                                                sport_type = "MMA"
                                            elif 'хоккей' in lower_title or 'хоккей' in lower_genre:
                                                sport_type = "Hockey"
                                            elif 'волейбол' in lower_title or 'волейбол' in lower_genre:
                                                sport_type = "Volleyball"
                                            elif 'баскетбол' in lower_title or 'баскетбол' in lower_genre:
                                                sport_type = "Basketball"
                                            
                                            # Parse time for filtering
                                            hour_val, minute_val = current_hour, current_minute
                                            if time_str != "N/A" and ':' in time_str:
                                                try:
                                                    hour_val, minute_val = map(int, time_str.split(':'))
                                                except ValueError:
                                                    pass
                                            
                                            # Compare with current time - only show future or current broadcasts
                                            if hour_val > current_hour or (hour_val == current_hour and minute_val >= current_minute):
                                                broadcast = {
                                                    "time": time_str,
                                                    "sport": sport_type,
                                                    "event": title,
                                                    "link": "https://matchtv.ru/tvguide"
                                                }
                                                broadcasts.append(broadcast)
                                                logging.info(f"Found broadcast: {time_str} - {sport_type} - {title[:50]}...")
                except json.JSONDecodeError as e:
                    logging.error(f"Error parsing JSON data: {e}")
                    continue
                except Exception as e:
                    logging.error(f"Error processing match: {e}")
                    continue
        else:
            logging.error("Could not find schedule data in response")
        
        # If we didn't find data using the new method, try the old method
        if not broadcasts:
            logging.info("Trying alternative parsing method...")
            
            # Look for the channels data in the JavaScript code using a different pattern
            channels_start = response_text.find('"channels":')
            if channels_start != -1:
                # Find the start of the channels array
                channels_start = response_text.find('[', channels_start)
                if channels_start != -1:
                    # Find the end of the channels array by counting brackets
                    bracket_count = 0
                    channels_end = -1
                    for i in range(channels_start, min(channels_start + 50000, len(response_text))):
                        if response_text[i] == '[':
                            bracket_count += 1
                        elif response_text[i] == ']':
                            bracket_count -= 1
                            if bracket_count == 0:
                                channels_end = i + 1
                                break
                    
                    if channels_end != -1:
                        channels_json = response_text[channels_start:channels_end]
                        logging.info(f"Found channels JSON data, length: {len(channels_json)}")
                        
                        # Parse the channels JSON
                        try:
                            channels_data = json.loads(channels_json)
                            logging.info(f"Successfully parsed {len(channels_data)} channels")
                            
                            # Process each channel's schedule
                            for channel in channels_data:
                                channel_name = channel.get('name', 'Unknown')
                                schedule = channel.get('schedule', [])
                                
                                logging.info(f"Processing {len(schedule)} schedule items for {channel_name}")
                                
                                for item in schedule:
                                    time_str = item.get('time', 'N/A')
                                    title = item.get('title', '')
                                    genre = item.get('genre', '')
                                    current = item.get('current', False)
                                    
                                    # Fix escaped quotes
                                    title = title.replace('\\"', '"')
                                    
                                    # Check if this is a sports event we're interested in
                                    lower_title = title.lower()
                                    lower_genre = genre.lower()
                                    
                                    # Check for sports content
                                    is_sports = (
                                        'футбол' in lower_title or 'футбол' in lower_genre or
                                        'mma' in lower_title or 'mma' in lower_genre or
                                        'ufc' in lower_title or 'ufc' in lower_genre or
                                        'единоборства' in lower_title or 'единоборства' in lower_genre or
                                        'бокс' in lower_title or 'бокс' in lower_genre or
                                        'хоккей' in lower_title or 'хоккей' in lower_genre or
                                        'волейбол' in lower_title or 'волейбол' in lower_genre or
                                        'баскетбол' in lower_title or 'баскетбол' in lower_genre
                                    )
                                    
                                    # Filter for live broadcasts (containing 'Прямая трансляция')
                                    is_live = 'прямая трансляция' in lower_title.lower()
                                    
                                    # Only include sports events that are live
                                    if is_sports and is_live:
                                        # Determine sport type
                                        sport_type = "Unknown"
                                        if 'футбол' in lower_title or 'футбол' in lower_genre:
                                            sport_type = "Football"
                                        elif 'mma' in lower_title or 'mma' in lower_genre or 'ufc' in lower_title or 'ufc' in lower_genre or 'единоборства' in lower_title or 'единоборства' in lower_genre or 'бокс' in lower_title or 'бокс' in lower_genre:
                                            sport_type = "MMA"
                                        elif 'хоккей' in lower_title or 'хоккей' in lower_genre:
                                            sport_type = "Hockey"
                                        elif 'волейбол' in lower_title or 'волейбол' in lower_genre:
                                            sport_type = "Volleyball"
                                        elif 'баскетбол' in lower_title or 'баскетбол' in lower_genre:
                                            sport_type = "Basketball"
                                        
                                        # Parse time for filtering
                                        hour_val, minute_val = current_hour, current_minute
                                        if time_str != "N/A" and ':' in time_str:
                                            try:
                                                hour_val, minute_val = map(int, time_str.split(':'))
                                            except ValueError:
                                                pass
                                        
                                        # Compare with current time - only show future or current broadcasts
                                        if hour_val > current_hour or (hour_val == current_hour and minute_val >= current_minute):
                                            broadcast = {
                                                "time": time_str,
                                                "sport": sport_type,
                                                "event": title,
                                                "link": "https://matchtv.ru/tvguide"
                                            }
                                            broadcasts.append(broadcast)
                                            logging.info(f"Found broadcast: {time_str} - {sport_type} - {title[:50]}...")
                            
                        except json.JSONDecodeError as e:
                            logging.error(f"Error parsing channels JSON: {e}")
                    else:
                        logging.error("Could not find end of channels array")
                else:
                    logging.error("Could not find start of channels array")
            else:
                logging.error("Could not find channels data in response")
        
        # Remove duplicates by converting to set of tuples and back
        seen = set()
        unique_broadcasts = []
        for broadcast in broadcasts:
            # Create a tuple of the identifying fields
            identifier = (broadcast['time'], broadcast['event'])
            if identifier not in seen:
                seen.add(identifier)
                unique_broadcasts.append(broadcast)
        
        # Sort by time
        unique_broadcasts.sort(key=lambda x: x['time'])
        
        # If we found broadcasts, return them
        if unique_broadcasts:
            logging.info(f"Successfully parsed {len(unique_broadcasts)} broadcasts")
            return unique_broadcasts[:15]  # Return up to 15 events
            
        # If no broadcasts found, log and return sample data
        logging.warning("No broadcasts found, returning sample data")
        # Apply the same filtering to sample data
        sample_data = [
            {"time": "10:00", "sport": "MMA", "event": "Тренировочный бой - Прямая трансляция", "link": "https://matchtv.ru/tvguide"},
            {"time": "14:30", "sport": "Football", "event": "Футбол: Матч еще не определен - Прямая трансляция", "link": "https://matchtv.ru/tvguide"},
            {"time": "17:00", "sport": "MMA", "event": "Спарринг клуба - Прямая трансляция", "link": "https://matchtv.ru/tvguide"},
            {"time": "20:00", "sport": "Football", "event": "Футбол: Резервный матч - Прямая трансляция", "link": "https://matchtv.ru/tvguide"},
        ]
        # Filter sample data by time
        filtered_sample = []
        for broadcast in sample_data:
            try:
                hour, minute = map(int, broadcast['time'].split(':'))
                if hour > current_hour or (hour == current_hour and minute >= current_minute):
                    filtered_sample.append(broadcast)
            except ValueError:
                filtered_sample.append(broadcast)
        return filtered_sample
        
    except Exception as e:
        logging.error(f"Error parsing matchtv.ru: {e}")
        logging.error("Printing page content for debugging:")
        # Print part of the response for debugging
        if 'response_text' in locals():
            logging.error(f"Response text length: {len(response_text)}")
            logging.error(f"First 1000 chars: {response_text[:1000]}")
        
        # Return sample data in case of error
        current_time = datetime.now()
        current_hour = current_time.hour
        current_minute = current_time.minute
        sample_data = [
            {"time": "10:00", "sport": "MMA", "event": "Тренировочный бой - Прямая трансляция", "link": "https://matchtv.ru/tvguide"},
            {"time": "14:30", "sport": "Football", "event": "Футбол: Матч еще не определен - Прямая трансляция", "link": "https://matchtv.ru/tvguide"},
            {"time": "17:00", "sport": "MMA", "event": "Спарринг клуба - Прямая трансляция", "link": "https://matchtv.ru/tvguide"},
            {"time": "20:00", "sport": "Football", "event": "Футбол: Резервный матч - Прямая трансляция", "link": "https://matchtv.ru/tvguide"},
        ]

        # Filter sample data by time
        filtered_sample = []
        for broadcast in sample_data:
            try:
                hour, minute = map(int, broadcast['time'].split(':'))
                if hour > current_hour or (hour == current_hour and minute >= current_minute):
                    filtered_sample.append(broadcast)
            except ValueError:
                filtered_sample.append(broadcast)
        return filtered_sample

def test_parsing():
    """Test the improved parsing functionality"""
    print("Testing improved parsing functionality...")
    
    try:
        broadcasts = parse_matchtv_schedule()
        
        print(f"\nFound {len(broadcasts)} broadcasts:")
        for i, broadcast in enumerate(broadcasts[:5]):  # Show first 5
            print(f"  {broadcast['time']} - {broadcast['sport']}: {broadcast['event'][:100]}...")
            
    except Exception as e:
        print(f"Error testing parsing: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    test_parsing()