#!/usr/bin/env python3
"""
Extract JSON data from MatchTV HTML
"""

import logging
import cloudscraper
import re
import json
from datetime import datetime

# Configure logging
logging.basicConfig(level=logging.INFO)

def extract_json_data():
    """Extract JSON data from MatchTV HTML"""
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
        
        # Save the response for analysis
        with open("matchtv_current.html", "w", encoding="utf-8") as f:
            f.write(response_text)
        
        logging.info(f"Saved response to matchtv_current.html, length: {len(response_text)}")
        
        # Look for the specific pattern we saw in the HTML
        # The data is embedded in a script tag with self.__next_f.push
        # Pattern: self.__next_f.push([1,"1b:...])
        
        # Find all script tags that contain schedule data
        pattern = r'self\.__next_f\.push\(\[1,"1b:(.*?)(\]\])'
        
        # Find all matches
        matches = re.findall(pattern, response_text)
        
        if matches:
            logging.info(f"Found {len(matches)} matches for schedule data")
            
            # Process each match
            for i, (matched_text, closing_brackets) in enumerate(matches):
                try:
                    # Combine the matched text with closing brackets
                    full_json_str = matched_text + closing_brackets
                    
                    # Replace escaped quotes and other escape sequences
                    full_json_str = full_json_str.replace('\\"', '"')
                    full_json_str = full_json_str.replace('\\\\', '\\')
                    
                    logging.info(f"Match {i}: Processing JSON string of length: {len(full_json_str)}")
                    
                    # Parse the JSON
                    data = json.loads(full_json_str)
                    logging.info(f"Match {i}: Successfully parsed JSON data with {len(data)} elements")
                    
                    # The data structure we're looking for is in the last element
                    if data and isinstance(data[-1], str):
                        # The last element contains the data we need
                        data_str = data[-1]
                        logging.info(f"Match {i}: Data string length: {len(data_str)}")
                        
                        # Extract the JSON part from the data string
                        # The string looks like: "$","$L53",null,{...}
                        # We need to extract the {...} part
                        # Find the position of the opening brace after "null,"
                        null_pos = data_str.find('null,')
                        if null_pos != -1:
                            json_start = data_str.find('{', null_pos)
                            json_end = data_str.rfind('}') + 1
                            
                            if json_start != -1 and json_end > json_start:
                                json_part = data_str[json_start:json_end]
                                logging.info(f"Match {i}: JSON part length: {len(json_part)}")
                                
                                # Try to parse the JSON part
                                try:
                                    schedule_data = json.loads(json_part)
                                    logging.info(f"Match {i}: Schedule data keys: {list(schedule_data.keys())}")
                                    
                                    # Extract channels
                                    channels = schedule_data.get('channels', [])
                                    logging.info(f"Match {i}: Found {len(channels)} channels")
                                    
                                    # Process channels
                                    for j, channel in enumerate(channels[:3]):  # Show first 3
                                        channel_name = channel.get('name', 'Unknown')
                                        schedule = channel.get('schedule', [])
                                        logging.info(f"Match {i}: Channel {j} {channel_name} has {len(schedule)} schedule items")
                                        
                                        # Show first few schedule items
                                        for item in schedule[:2]:
                                            logging.info(f"Match {i}:   {item.get('time', 'N/A')}: {item.get('title', '')[:50]}...")
                                    
                                    # Return the data for further processing
                                    return channels
                                except json.JSONDecodeError as e:
                                    logging.error(f"Match {i}: Error parsing schedule JSON: {e}")
                                    logging.error(f"Match {i}: JSON part preview: {json_part[:200]}...")
                            else:
                                logging.error(f"Match {i}: Could not extract JSON part from data string")
                        else:
                            logging.error(f"Match {i}: Could not find 'null,' in data string")
                    else:
                        logging.error(f"Match {i}: Unexpected data structure")
                        
                except json.JSONDecodeError as e:
                    logging.error(f"Match {i}: Error parsing main JSON: {e}")
                    logging.error(f"Match {i}: JSON string preview: {full_json_str[:200]}...")
                    continue
                except Exception as e:
                    logging.error(f"Match {i}: Error processing match: {e}")
                    import traceback
                    traceback.print_exc()
                    continue
        
        logging.error("Could not find or parse schedule data")
        return []
        
    except Exception as e:
        logging.error(f"Error in JSON extraction: {e}")
        import traceback
        traceback.print_exc()
        return []

def test_extraction():
    """Test the JSON extraction"""
    print("Testing JSON extraction...")
    
    try:
        channels = extract_json_data()
        
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