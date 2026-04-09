#!/usr/bin/env python3
"""
Multi-source parser for sports broadcasts with automatic switching between sources
"""

import logging
import requests
import cloudscraper
from bs4 import BeautifulSoup
from datetime import datetime
import re
import json
from config import ODDS_API_KEY

# Configure logging
logging.basicConfig(level=logging.INFO)

def get_current_time():
    """Get current time in Moscow timezone"""
    return datetime.now()

def is_future_event(event_time_str, current_time):
    """Check if event time is in the future"""
    try:
        hour, minute = map(int, event_time_str.split(':'))
        current_hour = current_time.hour
        current_minute = current_time.minute
        
        # Compare with current time - only show future or current broadcasts
        return hour > current_hour or (hour == current_hour and minute >= current_minute)
    except ValueError:
        # If we can't parse the time, assume it's valid
        return True

def extract_team_names(event_title):
    """
    Extract real team/fighter names from event title
    Returns (home_team, away_team) tuple or (None, None) if not found
    """
    # Common patterns for team/fighter names
    patterns = [
        r'(.+?)\s*[-–—]\s*(.+)',  # Team A - Team B
        r'(.+?)\s+vs\s+(.+)',     # Team A vs Team B
        r'(.+?)\s+на\s+(.+)',     # Fighter на Fighter
        r'(.+?)\s+против\s+(.+)', # Fighter против Fighter
    ]
    
    for pattern in patterns:
        match = re.search(pattern, event_title, re.IGNORECASE)
        if match:
            home_team = match.group(1).strip()
            away_team = match.group(2).strip()
            
            # Clean up team names
            home_team = re.sub(r'\s*\(.*?\)\s*', '', home_team)  # Remove parentheses
            away_team = re.sub(r'\s*\(.*?\)\s*', '', away_team)
            
            # Remove common prefixes/suffixes
            home_team = re.sub(r'^(футбол|mma|ufc|бокс):\s*', '', home_team, flags=re.IGNORECASE)
            away_team = re.sub(r'^(футбол|mma|ufc|бокс):\s*', '', away_team, flags=re.IGNORECASE)
            
            home_team = home_team.strip()
            away_team = away_team.strip()
            
            # If we still have meaningful names
            if home_team and away_team and len(home_team) > 2 and len(away_team) > 2:
                return home_team, away_team
    
    return None, None

def get_odds(home_team, away_team):
    """
    Get odds for a match from The Odds API
    Returns formatted odds string or None if not found/error
    """
    if not ODDS_API_KEY:
        logging.warning("ODDS_API_KEY not found in config")
        return None
    
    try:
        # Make request to The Odds API
        url = "https://api.the-odds-api.com/v4/sports/upcoming/odds"
        params = {
            'apiKey': ODDS_API_KEY,
            'regions': 'eu',  # European odds
            'markets': 'h2h',  # Head to head market
            'oddsFormat': 'decimal'
        }
        
        response = requests.get(url, params=params, timeout=10)
        
        # Check if we've hit the rate limit
        if response.status_code == 429:
            logging.warning("Odds API rate limit reached")
            return None
            
        if response.status_code != 200:
            logging.error(f"Odds API error: {response.status_code} - {response.text}")
            return None
            
        data = response.json()
        
        # Search for matching events
        for event in data:
            event_home_team = event.get('home_team', '').lower()
            event_away_team = event.get('away_team', '').lower()
            
            # Check if teams match (allowing for partial matches)
            if (home_team.lower() in event_home_team or event_home_team in home_team.lower()) and \
               (away_team.lower() in event_away_team or event_away_team in away_team.lower()):
                
                # Get the first bookmaker's odds
                bookmakers = event.get('bookmakers', [])
                if bookmakers:
                    # Get the first market (h2h)
                    markets = bookmakers[0].get('markets', [])
                    if markets:
                        outcomes = markets[0].get('outcomes', [])
                        if len(outcomes) >= 2:
                            # Format odds string
                            home_price = outcomes[0].get('price', 'N/A')
                            away_price = outcomes[1].get('price', 'N/A')
                            
                            # Handle draw if it exists
                            if len(outcomes) > 2:
                                draw_price = outcomes[2].get('price', 'N/A')
                                return f"📊 Коэффициенты: П1: {home_price} | Х: {draw_price} | П2: {away_price}"
                            else:
                                return f"📊 Коэффициенты: П1: {home_price} | П2: {away_price}"
        
        # No matching event found
        return None

    except Exception as e:
        logging.error(f"Error getting odds for {home_team} vs {away_team}: {e}")
        return None

def parse_matchtv_source():
    """
    Parse sports broadcasts from matchtv.ru (Source #1)
    Returns a list of dictionaries with time and event information
    """
    logging.info("Attempting to fetch data from Source #1: matchtv.ru")
    
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
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
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
        
        # Try the main URL for parsing
        url = "https://matchtv.ru/tvguide"
        
        logging.info(f"Trying to fetch {url}")
        response = scraper.get(url, headers=headers, timeout=15)
        
        # Check for 403 error (blocked)
        if response.status_code == 403:
            logging.warning("matchtv.ru returned 403 error - source blocked")
            return None
            
        if response.status_code != 200:
            logging.warning(f"Failed to fetch {url}, status code: {response.status_code}")
            return None
            
        response_text = response.text
        logging.info(f"Successfully fetched {url}")
        
        # Look for sports events in the embedded JSON data
        broadcasts = []
        
        # Get current time for filtering
        current_time = get_current_time()
        
        # Extract schedule data from JavaScript
        logging.info("Extracting schedule data from JavaScript...")
        
        # Look for the channels data in the JavaScript code
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
                            # Only process Match TV channel
                            if 'матч' in channel_name.lower() and 'тв' in channel_name.lower():
                                schedule = channel.get('schedule', [])
                                
                                logging.info(f"Processing {len(schedule)} schedule items for {channel_name}")
                                
                                for item in schedule:
                                    time_str = item.get('time', 'N/A')
                                    title = item.get('title', '')
                                    genre = item.get('genre', '')
                                    current = item.get('current', False)
                                    
                                    # Fix escaped quotes
                                    title = title.replace('\\"', '"')
                                    
                                    # Check for sports content
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
                                    
                                    # Filter for live broadcasts (containing 'Прямая трансляция' or 'LIVE')
                                    is_live = 'прямая трансляция' in lower_title.lower() or 'live' in lower_title.lower()
                                    
                                    # Only include sports events that are live and in the future
                                    if is_sports and is_live and is_future_event(time_str, current_time):
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
                                        
                                        broadcast = {
                                            "time": time_str,
                                            "sport": sport_type,
                                            "event": title,
                                            "link": "https://matchtv.ru/on-air"
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
        
        if unique_broadcasts:
            logging.info(f"Successfully parsed {len(unique_broadcasts)} broadcasts from matchtv.ru")
            return unique_broadcasts
        else:
            logging.info("No broadcasts found from matchtv.ru")
            return []
            
    except Exception as e:
        logging.error(f"Error parsing matchtv.ru: {e}")
        return None

def parse_championat_source():
    """
    Parse sports broadcasts from championat.com (Source #2)
    Returns a list of dictionaries with time and event information
    """
    logging.info("Attempting to fetch data from Source #2: championat.com")
    
    try:
        # Use requests with headers to avoid being blocked
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
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
        
        url = "https://www.championat.com/tv/"
        logging.info(f"Trying to fetch {url}")
        
        response = requests.get(url, headers=headers, timeout=15)
        
        if response.status_code != 200:
            logging.warning(f"Failed to fetch {url}, status code: {response.status_code}")
            return None
            
        soup = BeautifulSoup(response.text, 'html.parser')
        broadcasts = []
        
        # Get current time for filtering
        current_time = get_current_time()
        
        # Look for TV schedule items
        # Championat has a specific structure for TV listings
        schedule_items = soup.find_all('div', class_=['tv-programme__item', 'tv-schedule__item'])
        
        if not schedule_items:
            # Try alternative selectors
            schedule_items = soup.find_all('div', class_=re.compile(r'tv.*item', re.I))
        
        logging.info(f"Found {len(schedule_items)} schedule items on championat.com")
        
        for item in schedule_items:
            try:
                # Extract time
                time_elem = item.find(['time', 'div'], class_=re.compile(r'time', re.I))
                time_str = "N/A"
                if time_elem:
                    time_text = time_elem.get_text(strip=True)
                    # Extract time in format HH:MM
                    time_match = re.search(r'(\d{1,2}:\d{2})', time_text)
                    if time_match:
                        time_str = time_match.group(1)
                
                # Extract title
                title_elem = item.find(['h3', 'div'], class_=re.compile(r'title|name', re.I))
                if not title_elem:
                    title_elem = item.find('a')
                
                title = ""
                if title_elem:
                    title = title_elem.get_text(strip=True)
                
                # Extract channel
                channel_elem = item.find(['div', 'span'], class_=re.compile(r'channel', re.I))
                if not channel_elem:
                    # Try to find channel in other elements
                    channel_elem = item.find(string=re.compile(r'Матч\s*ТВ', re.I))
                
                channel_name = ""
                if channel_elem:
                    if hasattr(channel_elem, 'get_text'):
                        channel_name = channel_elem.get_text(strip=True)
                    else:
                        channel_name = str(channel_elem).strip()
                
                # Check if this is for Match TV
                is_match_tv = (
                    'матч' in channel_name.lower() and 'тв' in channel_name.lower()
                ) or (
                    'match' in channel_name.lower() and 'tv' in channel_name.lower()
                )
                
                # Check for sports content
                lower_title = title.lower()
                is_sports = (
                    'футбол' in lower_title or
                    'mma' in lower_title or
                    'ufc' in lower_title or
                    'единоборства' in lower_title or
                    'бокс' in lower_title or
                    'хоккей' in lower_title or
                    'волейбол' in lower_title or
                    'баскетбол' in lower_title
                )
                
                # Filter for live broadcasts
                is_live = 'прямая трансляция' in lower_title.lower() or 'live' in lower_title.lower()
                
                # Only include Match TV sports events that are live and in the future
                if is_match_tv and is_sports and is_live and is_future_event(time_str, current_time):
                    # Determine sport type
                    sport_type = "Unknown"
                    if 'футбол' in lower_title:
                        sport_type = "Football"
                    elif 'mma' in lower_title or 'ufc' in lower_title or 'единоборства' in lower_title or 'бокс' in lower_title:
                        sport_type = "MMA"
                    elif 'хоккей' in lower_title:
                        sport_type = "Hockey"
                    elif 'волейбол' in lower_title:
                        sport_type = "Volleyball"
                    elif 'баскетбол' in lower_title:
                        sport_type = "Basketball"
                    
                    broadcast = {
                        "time": time_str,
                        "sport": sport_type,
                        "event": title,
                        "link": "https://matchtv.ru/on-air"
                    }
                    broadcasts.append(broadcast)
                    logging.info(f"Found broadcast: {time_str} - {sport_type} - {title[:50]}...")
                    
            except Exception as e:
                logging.warning(f"Error processing championat item: {e}")
                continue
        
        # Remove duplicates
        seen = set()
        unique_broadcasts = []
        for broadcast in broadcasts:
            identifier = (broadcast['time'], broadcast['event'])
            if identifier not in seen:
                seen.add(identifier)
                unique_broadcasts.append(broadcast)
        
        # Sort by time
        unique_broadcasts.sort(key=lambda x: x['time'])
        
        if unique_broadcasts:
            logging.info(f"Successfully parsed {len(unique_broadcasts)} broadcasts from championat.com")
            return unique_broadcasts
        else:
            logging.info("No broadcasts found from championat.com")
            return []
            
    except Exception as e:
        logging.error(f"Error parsing championat.com: {e}")
        return None

def parse_liveresult_source():
    """
    Parse sports broadcasts from liveresult.ru (Source #3)
    Returns a list of dictionaries with time and event information
    """
    logging.info("Attempting to fetch data from Source #3: liveresult.ru")
    
    try:
        # Use requests with headers to avoid being blocked
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
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
        
        url = "https://www.liveresult.ru/tv/"
        logging.info(f"Trying to fetch {url}")
        
        response = requests.get(url, headers=headers, timeout=15)
        
        if response.status_code != 200:
            logging.warning(f"Failed to fetch {url}, status code: {response.status_code}")
            return None
            
        soup = BeautifulSoup(response.text, 'html.parser')
        broadcasts = []
        
        # Get current time for filtering
        current_time = get_current_time()
        
        # Look for TV schedule items
        # Liveresult has a specific structure for TV listings
        schedule_items = soup.find_all('div', class_=re.compile(r'event|match|broadcast', re.I))
        
        if not schedule_items:
            # Try alternative selectors
            schedule_items = soup.find_all('div', class_=re.compile(r'item|row', re.I))
        
        logging.info(f"Found {len(schedule_items)} schedule items on liveresult.ru")
        
        for item in schedule_items:
            try:
                # Extract time
                time_elem = item.find(['time', 'div'], class_=re.compile(r'time', re.I))
                time_str = "N/A"
                if time_elem:
                    time_text = time_elem.get_text(strip=True)
                    # Extract time in format HH:MM
                    time_match = re.search(r'(\d{1,2}:\d{2})', time_text)
                    if time_match:
                        time_str = time_match.group(1)
                
                # Extract title
                title_elem = item.find(['h3', 'div'], class_=re.compile(r'title|name|event', re.I))
                if not title_elem:
                    title_elem = item.find('a')
                
                title = ""
                if title_elem:
                    title = title_elem.get_text(strip=True)
                
                # Extract channel
                channel_elem = item.find(['div', 'span'], class_=re.compile(r'channel|tv', re.I))
                if not channel_elem:
                    # Try to find channel in other elements
                    channel_elem = item.find(string=re.compile(r'Матч\s*ТВ', re.I))
                
                channel_name = ""
                if channel_elem:
                    if hasattr(channel_elem, 'get_text'):
                        channel_name = channel_elem.get_text(strip=True)
                    else:
                        channel_name = str(channel_elem).strip()
                
                # Check if this is for Match TV
                is_match_tv = (
                    'матч' in channel_name.lower() and 'тв' in channel_name.lower()
                ) or (
                    'match' in channel_name.lower() and 'tv' in channel_name.lower()
                )
                
                # Check for sports content
                lower_title = title.lower()
                is_sports = (
                    'футбол' in lower_title or
                    'mma' in lower_title or
                    'ufc' in lower_title or
                    'единоборства' in lower_title or
                    'бокс' in lower_title or
                    'хоккей' in lower_title or
                    'волейбол' in lower_title or
                    'баскетбол' in lower_title
                )
                
                # Filter for live broadcasts
                is_live = 'прямая трансляция' in lower_title.lower() or 'live' in lower_title.lower() or 'онлайн' in lower_title.lower()
                
                # Only include Match TV sports events that are live and in the future
                if is_match_tv and is_sports and is_live and is_future_event(time_str, current_time):
                    # Determine sport type
                    sport_type = "Unknown"
                    if 'футбол' in lower_title:
                        sport_type = "Football"
                    elif 'mma' in lower_title or 'ufc' in lower_title or 'единоборства' in lower_title or 'бокс' in lower_title:
                        sport_type = "MMA"
                    elif 'хоккей' in lower_title:
                        sport_type = "Hockey"
                    elif 'волейбол' in lower_title:
                        sport_type = "Volleyball"
                    elif 'баскетбол' in lower_title:
                        sport_type = "Basketball"
                    
                    broadcast = {
                        "time": time_str,
                        "sport": sport_type,
                        "event": title,
                        "link": "https://matchtv.ru/on-air"
                    }
                    broadcasts.append(broadcast)
                    logging.info(f"Found broadcast: {time_str} - {sport_type} - {title[:50]}...")
                    
            except Exception as e:
                logging.warning(f"Error processing liveresult item: {e}")
                continue
        
        # Remove duplicates
        seen = set()
        unique_broadcasts = []
        for broadcast in broadcasts:
            identifier = (broadcast['time'], broadcast['event'])
            if identifier not in seen:
                seen.add(identifier)
                unique_broadcasts.append(broadcast)
        
        # Sort by time
        unique_broadcasts.sort(key=lambda x: x['time'])
        
        if unique_broadcasts:
            logging.info(f"Successfully parsed {len(unique_broadcasts)} broadcasts from liveresult.ru")
            return unique_broadcasts
        else:
            logging.info("No broadcasts found from liveresult.ru")
            return []
            
    except Exception as e:
        logging.error(f"Error parsing liveresult.ru: {e}")
        return None

def parse_fight_source():
    """
    Parse sports broadcasts from fight.ru (Source #4, Priority for MMA/UFC)
    Returns a list of dictionaries with time and event information
    """
    logging.info("Attempting to fetch data from Source #4: fight.ru")
    
    try:
        # Use requests with headers to avoid being blocked
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
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
        
        url = "https://fight.ru"
        logging.info(f"Trying to fetch {url}")
        
        response = requests.get(url, headers=headers, timeout=15)
        
        if response.status_code != 200:
            logging.warning(f"Failed to fetch {url}, status code: {response.status_code}")
            return None
            
        soup = BeautifulSoup(response.text, 'html.parser')
        broadcasts = []
        
        # Get current time for filtering
        current_time = get_current_time()
        
        # Look for TV schedule items or events
        # Fight.ru may have different structures, try multiple selectors
        schedule_items = soup.find_all('div', class_=re.compile(r'event|match|broadcast|fight', re.I))
        
        if not schedule_items:
            # Try alternative selectors
            schedule_items = soup.find_all('div', class_=re.compile(r'item|row|card', re.I))
        
        logging.info(f"Found {len(schedule_items)} schedule items on fight.ru")
        
        for item in schedule_items:
            try:
                # Extract time
                time_elem = item.find(['time', 'div'], class_=re.compile(r'time|date', re.I))
                time_str = "N/A"
                if time_elem:
                    time_text = time_elem.get_text(strip=True)
                    # Extract time in format HH:MM
                    time_match = re.search(r'(\d{1,2}:\d{2})', time_text)
                    if time_match:
                        time_str = time_match.group(1)
                
                # Extract title
                title_elem = item.find(['h3', 'h2', 'h1', 'div'], class_=re.compile(r'title|name|event', re.I))
                if not title_elem:
                    title_elem = item.find('a')
                
                title = ""
                if title_elem:
                    title = title_elem.get_text(strip=True)
                
                # Check for sports content (focus on MMA/UFC/Бокс)
                lower_title = title.lower()
                is_sports = (
                    'mma' in lower_title or
                    'ufc' in lower_title or
                    'единоборства' in lower_title or
                    'бокс' in lower_title or
                    'файтинг' in lower_title
                )
                
                # Filter for live broadcasts or TV transmissions
                is_live = (
                    'прямая трансляция' in lower_title.lower() or
                    'live' in lower_title.lower() or
                    'онлайн' in lower_title.lower() or
                    'тв' in lower_title.lower() or
                    'трансляци' in lower_title.lower() or
                    'video' in lower_title.lower()
                )
                
                # Only include sports events that are live and in the future
                if is_sports and is_live and is_future_event(time_str, current_time):
                    # Determine sport type
                    sport_type = "MMA"
                    if 'бокс' in lower_title:
                        sport_type = "Boxing"
                    elif 'ufc' in lower_title:
                        sport_type = "UFC"
                    
                    broadcast = {
                        "time": time_str,
                        "sport": sport_type,
                        "event": title,
                        "link": "https://matchtv.ru/on-air",  # Default link
                        "source": "fight.ru"
                    }
                    broadcasts.append(broadcast)
                    logging.info(f"Found broadcast: {time_str} - {sport_type} - {title[:50]}...")
                    
            except Exception as e:
                logging.warning(f"Error processing fight.ru item: {e}")
                continue
        
        # Remove duplicates
        seen = set()
        unique_broadcasts = []
        for broadcast in broadcasts:
            identifier = (broadcast['time'], broadcast['event'])
            if identifier not in seen:
                seen.add(identifier)
                unique_broadcasts.append(broadcast)
        
        # Sort by time
        unique_broadcasts.sort(key=lambda x: x['time'])
        
        if unique_broadcasts:
            logging.info(f"Successfully parsed {len(unique_broadcasts)} broadcasts from fight.ru")
            return unique_broadcasts
        else:
            logging.info("No broadcasts found from fight.ru")
            return []
            
    except Exception as e:
        logging.error(f"Error parsing fight.ru: {e}")
        return None

def parse_sports_source():
    """
    Parse sports broadcasts from sports.ru (Source #5)
    Returns a list of dictionaries with time and event information
    """
    logging.info("Attempting to fetch data from Source #5: sports.ru")
    
    try:
        # Use requests with headers to avoid being blocked
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
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
        
        url = "https://sports.ru/tv/"
        logging.info(f"Trying to fetch {url}")
        
        response = requests.get(url, headers=headers, timeout=15)
        
        if response.status_code != 200:
            logging.warning(f"Failed to fetch {url}, status code: {response.status_code}")
            return None
            
        soup = BeautifulSoup(response.text, 'html.parser')
        broadcasts = []
        
        # Get current time for filtering
        current_time = get_current_time()
        
        # Look for TV schedule items
        schedule_items = soup.find_all('div', class_=re.compile(r'tv|schedule|broadcast', re.I))
        
        if not schedule_items:
            # Try alternative selectors
            schedule_items = soup.find_all('div', class_=re.compile(r'item|row', re.I))
        
        logging.info(f"Found {len(schedule_items)} schedule items on sports.ru")
        
        for item in schedule_items:
            try:
                # Extract time
                time_elem = item.find(['time', 'div'], class_=re.compile(r'time', re.I))
                time_str = "N/A"
                if time_elem:
                    time_text = time_elem.get_text(strip=True)
                    # Extract time in format HH:MM
                    time_match = re.search(r'(\d{1,2}:\d{2})', time_text)
                    if time_match:
                        time_str = time_match.group(1)
                
                # Extract title
                title_elem = item.find(['h3', 'h2', 'div'], class_=re.compile(r'title|name|event', re.I))
                if not title_elem:
                    title_elem = item.find('a')
                
                title = ""
                if title_elem:
                    title = title_elem.get_text(strip=True)
                
                # Check for sports content (Футбол and UFC/MMA/Бокс)
                lower_title = title.lower()
                is_sports = (
                    'футбол' in lower_title or
                    'mma' in lower_title or
                    'ufc' in lower_title or
                    'единоборства' in lower_title or
                    'бокс' in lower_title
                )
                
                # Filter for live broadcasts or TV transmissions
                is_live = (
                    'прямая трансляция' in lower_title.lower() or
                    'live' in lower_title.lower() or
                    'онлайн' in lower_title.lower() or
                    'тв' in lower_title.lower() or
                    'трансляци' in lower_title.lower() or
                    'video' in lower_title.lower()
                )
                
                # Only include sports events that are live and in the future
                if is_sports and is_live and is_future_event(time_str, current_time):
                    # Determine sport type
                    sport_type = "Unknown"
                    if 'футбол' in lower_title:
                        sport_type = "Football"
                    elif 'mma' in lower_title or 'ufc' in lower_title or 'единоборства' in lower_title or 'бокс' in lower_title:
                        sport_type = "MMA"
                    
                    broadcast = {
                        "time": time_str,
                        "sport": sport_type,
                        "event": title,
                        "link": "https://matchtv.ru/on-air",  # Default link
                        "source": "sports.ru"
                    }
                    broadcasts.append(broadcast)
                    logging.info(f"Found broadcast: {time_str} - {sport_type} - {title[:50]}...")
                    
            except Exception as e:
                logging.warning(f"Error processing sports.ru item: {e}")
                continue
        
        # Remove duplicates
        seen = set()
        unique_broadcasts = []
        for broadcast in broadcasts:
            identifier = (broadcast['time'], broadcast['event'])
            if identifier not in seen:
                seen.add(identifier)
                unique_broadcasts.append(broadcast)
        
        # Sort by time
        unique_broadcasts.sort(key=lambda x: x['time'])
        
        if unique_broadcasts:
            logging.info(f"Successfully parsed {len(unique_broadcasts)} broadcasts from sports.ru")
            return unique_broadcasts
        else:
            logging.info("No broadcasts found from sports.ru")
            return []
            
    except Exception as e:
        logging.error(f"Error parsing sports.ru: {e}")
        return None

def parse_sport_express_source():
    """
    Parse sports broadcasts from sport-express.ru (Source #6)
    Returns a list of dictionaries with time and event information
    """
    logging.info("Attempting to fetch data from Source #6: sport-express.ru")
    
    try:
        # Use requests with headers to avoid being blocked
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
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
        
        url = "https://sport-express.ru/tv/"
        logging.info(f"Trying to fetch {url}")
        
        response = requests.get(url, headers=headers, timeout=15)
        
        if response.status_code != 200:
            logging.warning(f"Failed to fetch {url}, status code: {response.status_code}")
            return None
            
        soup = BeautifulSoup(response.text, 'html.parser')
        broadcasts = []
        
        # Get current time for filtering
        current_time = get_current_time()
        
        # Look for TV schedule items
        schedule_items = soup.find_all('div', class_=re.compile(r'tv|schedule|broadcast', re.I))
        
        if not schedule_items:
            # Try alternative selectors
            schedule_items = soup.find_all('div', class_=re.compile(r'item|row', re.I))
        
        logging.info(f"Found {len(schedule_items)} schedule items on sport-express.ru")
        
        for item in schedule_items:
            try:
                # Extract time
                time_elem = item.find(['time', 'div'], class_=re.compile(r'time', re.I))
                time_str = "N/A"
                if time_elem:
                    time_text = time_elem.get_text(strip=True)
                    # Extract time in format HH:MM
                    time_match = re.search(r'(\d{1,2}:\d{2})', time_text)
                    if time_match:
                        time_str = time_match.group(1)
                
                # Extract title
                title_elem = item.find(['h3', 'h2', 'div'], class_=re.compile(r'title|name|event', re.I))
                if not title_elem:
                    title_elem = item.find('a')
                
                title = ""
                if title_elem:
                    title = title_elem.get_text(strip=True)
                
                # Check for sports content (Футбол and UFC/MMA/Бокс)
                lower_title = title.lower()
                is_sports = (
                    'футбол' in lower_title or
                    'mma' in lower_title or
                    'ufc' in lower_title or
                    'единоборства' in lower_title or
                    'бокс' in lower_title
                )
                
                # Filter for live broadcasts or TV transmissions
                is_live = (
                    'прямая трансляция' in lower_title.lower() or
                    'live' in lower_title.lower() or
                    'онлайн' in lower_title.lower() or
                    'тв' in lower_title.lower() or
                    'трансляци' in lower_title.lower() or
                    'video' in lower_title.lower()
                )
                
                # Only include sports events that are live and in the future
                if is_sports and is_live and is_future_event(time_str, current_time):
                    # Determine sport type
                    sport_type = "Unknown"
                    if 'футбол' in lower_title:
                        sport_type = "Football"
                    elif 'mma' in lower_title or 'ufc' in lower_title or 'единоборства' in lower_title or 'бокс' in lower_title:
                        sport_type = "MMA"
                    
                    broadcast = {
                        "time": time_str,
                        "sport": sport_type,
                        "event": title,
                        "link": "https://matchtv.ru/on-air",  # Default link
                        "source": "sport-express.ru"
                    }
                    broadcasts.append(broadcast)
                    logging.info(f"Found broadcast: {time_str} - {sport_type} - {title[:50]}...")
                    
            except Exception as e:
                logging.warning(f"Error processing sport-express.ru item: {e}")
                continue
        
        # Remove duplicates
        seen = set()
        unique_broadcasts = []
        for broadcast in broadcasts:
            identifier = (broadcast['time'], broadcast['event'])
            if identifier not in seen:
                seen.add(identifier)
                unique_broadcasts.append(broadcast)
        
        # Sort by time
        unique_broadcasts.sort(key=lambda x: x['time'])
        
        if unique_broadcasts:
            logging.info(f"Successfully parsed {len(unique_broadcasts)} broadcasts from sport-express.ru")
            return unique_broadcasts
        else:
            logging.info("No broadcasts found from sport-express.ru")
            return []
            
    except Exception as e:
        logging.error(f"Error parsing sport-express.ru: {e}")
        return None

def deduplicate_broadcasts(broadcasts):
    """
    Remove duplicate broadcasts based on event name and time similarity
    Returns a list of unique broadcasts
    """
    if not broadcasts:
        return []
    
    # Normalize event names for comparison
    def normalize_event_name(event):
        # Remove extra spaces and convert to lowercase
        normalized = re.sub(r'\s+', ' ', event.lower().strip())
        # Remove common prefixes/suffixes
        normalized = re.sub(r'^(футбол|mma|ufc|бокс|единоборства):\s*', '', normalized)
        normalized = re.sub(r'\s*(прямая трансляция|live|онлайн|тв).*$', '', normalized)
        # Remove extra punctuation
        normalized = re.sub(r'[^\w\sа-яё]', '', normalized)
        return normalized.strip()
    
    # Group broadcasts by normalized event name
    event_groups = {}
    for broadcast in broadcasts:
        normalized_name = normalize_event_name(broadcast['event'])
        
        # Try to find existing group with similar name
        found_group = False
        for group_name in event_groups:
            # Check if names are similar (using simple string similarity)
            if normalized_name in group_name or group_name in normalized_name or \
               len(set(normalized_name.split()) & set(group_name.split())) > 1:
                event_groups[group_name].append(broadcast)
                found_group = True
                break
        
        # If no similar group found, create new one
        if not found_group:
            event_groups[normalized_name] = [broadcast]
    
    # For each group, keep the broadcast with the most complete information
    unique_broadcasts = []
    for group_name, group_broadcasts in event_groups.items():
        if len(group_broadcasts) == 1:
            unique_broadcasts.append(group_broadcasts[0])
        else:
            # Multiple broadcasts for the same event, choose the best one
            # Prefer broadcasts with more complete information
            best_broadcast = group_broadcasts[0]
            for broadcast in group_broadcasts[1:]:
                # Prefer broadcasts with actual time vs "N/A"
                if broadcast['time'] != "N/A" and best_broadcast['time'] == "N/A":
                    best_broadcast = broadcast
                # Prefer broadcasts with specific sport type vs "Unknown"
                elif broadcast['sport'] != "Unknown" and best_broadcast['sport'] == "Unknown":
                    best_broadcast = broadcast
                # Prefer broadcasts from sources with higher priority
                elif 'source' in broadcast and 'source' in best_broadcast:
                    source_priority = {
                        'fight.ru': 1,  # Highest priority for MMA/UFC
                        'matchtv.ru': 2,
                        'championat.com': 3,
                        'sports.ru': 4,
                        'sport-express.ru': 5,
                        'liveresult.ru': 6
                    }
                    broadcast_priority = source_priority.get(broadcast['source'], 10)
                    best_priority = source_priority.get(best_broadcast['source'], 10)
                    if broadcast_priority < best_priority:
                        best_broadcast = broadcast
            
            unique_broadcasts.append(best_broadcast)
    
    # Sort by time
    unique_broadcasts.sort(key=lambda x: x['time'])
    return unique_broadcasts

def get_broadcasts_multi_source():
    """
    Get sports broadcasts using multi-source approach with automatic switching
    Returns a list of broadcast dictionaries or empty list if no data found
    """
    logging.info("Starting multi-source broadcast fetching")
    
    # Try sources in priority order
    sources = [
        ("matchtv.ru", parse_matchtv_source),
        ("fight.ru", parse_fight_source),  # Priority for MMA/UFC
        ("championat.com", parse_championat_source),
        ("sports.ru", parse_sports_source),
        ("sport-express.ru", parse_sport_express_source),
        ("liveresult.ru", parse_liveresult_source)
    ]
    
    all_broadcasts = []
    
    # Collect data from all sources
    for source_name, source_function in sources:
        try:
            logging.info(f"Trying source: {source_name}")
            broadcasts = source_function()
            
            # If we got a valid result (not None), add it to our collection
            if broadcasts is not None:
                logging.info(f"Successfully got {len(broadcasts)} broadcasts from {source_name}")
                all_broadcasts.extend(broadcasts)
            else:
                logging.info(f"No data returned from {source_name}")
                
        except Exception as e:
            logging.error(f"Error with source {source_name}: {e}")
            continue
    
    # Remove duplicates
    unique_broadcasts = deduplicate_broadcasts(all_broadcasts)
    
    # Get odds for each unique broadcast
    for broadcast in unique_broadcasts:
        home_team, away_team = extract_team_names(broadcast['event'])
        if home_team and away_team:
            odds = get_odds(home_team, away_team)
            if odds:
                broadcast['odds'] = odds
    
    if unique_broadcasts:
        logging.info(f"Successfully got {len(unique_broadcasts)} unique broadcasts from all sources")
        return unique_broadcasts
    else:
        logging.warning("No broadcasts found from any source")
        return []

def format_broadcast_message(broadcasts):
    """
    Format broadcasts into a message string with proper emojis and odds
    """
    if not broadcasts:
        return "Трансляций на сегодня не найдено"
    
    message_text = "📺 Расписание прямых трансляций на сегодня:\n\n"
    
    for broadcast in broadcasts:
        # Determine emoji based on sport type
        emoji = "📺"
        if broadcast['sport'] == "Football":
            emoji = "⚽"
        elif broadcast['sport'] in ["MMA", "Boxing", "UFC"]:
            emoji = "🥊"
        
        message_text += f"⏰ {broadcast['time']}\n"
        message_text += f"{emoji} {broadcast['sport']}: {broadcast['event']}\n"
        
        # Add source information
        if 'source' in broadcast:
            message_text += f"Источник данных: {broadcast['source']}\n"
        
        # Add odds if available
        if 'odds' in broadcast and broadcast['odds']:
            message_text += f"{broadcast['odds']}\n"
        else:
            # Try to extract team names and get odds
            home_team, away_team = extract_team_names(broadcast['event'])
            if home_team and away_team:
                odds = get_odds(home_team, away_team)
                if odds:
                    message_text += f"{odds}\n"
        
        message_text += f"🔗 [Смотреть онлайн]({broadcast['link']})\n\n"
    
    return message_text

# Test function
def test_multi_source_parser():
    """Test the multi-source parser"""
    print("Testing multi-source parser...")
    
    try:
        broadcasts = get_broadcasts_multi_source()
        
        if broadcasts:
            print(f"\nFound {len(broadcasts)} unique broadcasts:")
            for i, broadcast in enumerate(broadcasts[:10]):  # Show first 10
                source = broadcast.get('source', 'Unknown')
                print(f"  {i+1}. {broadcast['time']} - {broadcast['sport']} - {broadcast['event'][:50]}... (from {source})")
        else:
            print("No broadcasts found")
            
        # Test formatting
        message = format_broadcast_message(broadcasts)
        print(f"\nFormatted message preview (first 1000 chars):\n{message[:1000]}...")
        
    except Exception as e:
        print(f"Error testing parser: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    test_multi_source_parser()