#!/usr/bin/env python3
"""
Extract schedule data by pattern matching
"""

import logging
import cloudscraper
import re
import json
from datetime import datetime

# Configure logging
logging.basicConfig(level=logging.INFO)

def extract_by_pattern():
    """Extract schedule data by pattern matching"""
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
        
        # Look for the specific pattern we saw in the HTML
        # Pattern: self.__next_f.push([1,"1b:[\"$\",\"$L53\",null,{...}]])
        pattern = r'self\.__next_f\.push\(\[1,"1b:(.*?)(\]\])'
        
        # Find all matches
        for match in re.finditer(pattern, response_text):
            matched_text = match.group(1)
            logging.info(f"Found pattern match: {matched_text[:100]}...")
            
            # Try to parse the JSON data
            try:
                # The matched text is a JSON array string, but it's escaped
                # We need to decode it properly
                # First, let's add the closing brackets back
                full_json_str = matched_text + "]]"
                
                # Replace escaped quotes
                full_json_str = full_json_str.replace('\\"', '"')
                
                # Parse the JSON
                data = json.loads(full_json_str)
                logging.info(f"Successfully parsed JSON data with {len(data)} elements")
                
                # The data structure we're looking for is in the last element
                if data and isinstance(data[-1], str):
                    # The last element contains the data we need
                    data_str = data[-1]
                    logging.info(f"Data string: {data_str[:100]}...")
                    
                    # Extract the JSON part from the data string
                    # The string looks like: "$","$L53",null,{...}
                    # We need to extract the {...} part
                    json_start = data_str.find('{')
                    json_end = data_str.rfind('}') + 1
                    
                    if json_start != -1 and json_end > json_start:
                        json_part = data_str[json_start:json_end]
                        logging.info(f"JSON part: {json_part[:100]}...")
                        
                        # Parse the JSON part
                        schedule_data = json.loads(json_part)
                        logging.info(f"Schedule data keys: {list(schedule_data.keys())}")
                        
                        # Extract channels
                        channels = schedule_data.get('channels', [])
                        logging.info(f"Found {len(channels)} channels")
                        
                        # Process channels
                        for channel in channels:
                            channel_name = channel.get('name', 'Unknown')
                            schedule = channel.get('schedule', [])
                            logging.info(f"Channel {channel_name} has {len(schedule)} schedule items")
                            
                            # Show first few schedule items
                            for item in schedule[:3]:
                                logging.info(f"  Schedule item: {item}")
                        
                        # Return the data for further processing
                        return channels
                    else:
                        logging.error("Could not extract JSON part from data string")
                else:
                    logging.error("Unexpected data structure")
                    
            except json.JSONDecodeError as e:
                logging.error(f"Error parsing JSON: {e}")
                continue
            except Exception as e:
                logging.error(f"Error processing match: {e}")
                continue
        
        logging.error("Could not find or parse schedule data")
        return []
        
    except Exception as e:
        logging.error(f"Error in pattern extraction: {e}")
        import traceback
        traceback.print_exc()
        return []

def test_extraction():
    """Test the pattern extraction"""
    print("Testing pattern extraction...")
    
    try:
        channels = extract_by_pattern()
        
        print(f"\nFound {len(channels)} channels:")
        for i, channel in enumerate(channels[:3]):  # Show first 3
            print(f"  Channel {i}: {channel.get('name', 'Unknown')}")
            schedule = channel.get('schedule', [])
            print(f"    Schedule items: {len(schedule)}")
            for item in schedule[:2]:
                print(f"      {item.get('time', 'N/A')}: {item.get('title', '')[:50]}...")
                
    except Exception as e:
        print(f"Error testing extraction: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    test_extraction()