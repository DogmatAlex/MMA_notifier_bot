#!/usr/bin/env python3
"""
Simple extraction of schedule data from MatchTV
"""

import logging
import cloudscraper
import re
import json
from datetime import datetime

# Configure logging
logging.basicConfig(level=logging.INFO)

def simple_extract():
    """Simple extraction of schedule data"""
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
        with open("matchtv_response.txt", "w", encoding="utf-8") as f:
            f.write(response_text)
        
        logging.info(f"Saved response to matchtv_response.txt, length: {len(response_text)}")
        
        # Look for the channels data using a more flexible pattern
        # The data is in a format like: {"channel":"$undefined","channels":[{...}]}
        pattern = r'"channels":\s*(\[[^\]]*\])'
        matches = re.findall(pattern, response_text)
        
        if matches:
            logging.info(f"Found {len(matches)} matches for channels data")
            
            # Process each match
            for i, match in enumerate(matches):
                try:
                    # Add closing brackets if needed
                    channels_json = match
                    if not channels_json.startswith('['):
                        channels_json = '[' + channels_json
                    if not channels_json.endswith(']'):
                        channels_json = channels_json + ']'
                    
                    # Parse the JSON
                    channels_data = json.loads(channels_json)
                    logging.info(f"Match {i}: Successfully parsed {len(channels_data)} channels")
                    
                    # Print first channel info for debugging
                    if channels_data:
                        first_channel = channels_data[0]
                        logging.info(f"First channel: {first_channel.get('name', 'Unknown')}")
                        if 'schedule' in first_channel:
                            logging.info(f"First channel has {len(first_channel['schedule'])} schedule items")
                            if first_channel['schedule']:
                                logging.info(f"First schedule item: {first_channel['schedule'][0]}")
                except json.JSONDecodeError as e:
                    logging.error(f"Match {i}: Error parsing JSON: {e}")
                    continue
                except Exception as e:
                    logging.error(f"Match {i}: Error processing: {e}")
                    continue
        else:
            logging.error("Could not find channels data using simple pattern")
            
            # Try a more complex pattern
            logging.info("Trying more complex pattern...")
            # Look for the data that contains channel information
            complex_pattern = r'(\{"id":\d+,"tvChannelId":\d+,"alias":"[^"]+","name":"[^"]+"[^}]*"schedule":\[[^\]]*\][^\}]*\})'
            complex_matches = re.findall(complex_pattern, response_text)
            
            if complex_matches:
                logging.info(f"Found {len(complex_matches)} matches with complex pattern")
                for i, match in enumerate(complex_matches[:3]):  # Show first 3
                    logging.info(f"Complex match {i}: {match[:200]}...")
            else:
                logging.error("Could not find channels data using complex pattern")
        
        # Try to find any data that contains "прямая трансляция"
        live_pattern = r'([^{]*"title":"[^"]*прямая трансляция[^"]*"[^}]*)'
        live_matches = re.findall(live_pattern, response_text, re.IGNORECASE)
        
        if live_matches:
            logging.info(f"Found {len(live_matches)} matches with live broadcasts")
            for i, match in enumerate(live_matches[:5]):  # Show first 5
                logging.info(f"Live match {i}: {match[:100]}...")
        else:
            logging.info("No live broadcasts found in response")
            
    except Exception as e:
        logging.error(f"Error in simple extraction: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    simple_extract()