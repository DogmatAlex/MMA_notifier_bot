#!/usr/bin/env python3
"""
Multi-source parser for sports broadcasts with automatic switching between sources
"""

import logging
import requests
import cloudscraper
from bs4 import BeautifulSoup
from datetime import datetime, timedelta
import re
import json
import time
import random
from config import ODDS_API_KEY
from fuzzywuzzy import fuzz

# Configure logging
logging.basicConfig(level=logging.INFO)

def get_current_time():
    """Get current time in Moscow timezone"""
    return datetime.now()

def is_future_event(event_time_str, current_time):
    """Check if event time is in the future or within the past 2 hours, up to 48 hours ahead"""
    # If event_time_str is "N/A" or doesn't parse, consider it valid if within 24 hours
    if event_time_str == "N/A" or not event_time_str:
        # If no time specified, consider it valid for the next 24 hours
        return True
        
    try:
        hour, minute = map(int, event_time_str.split(':'))
        # Create event time for today
        event_time_today = current_time.replace(hour=hour, minute=minute, second=0, microsecond=0)
        
        # If event time (час:минута) меньше чем current_time минус 2 часа, значит это событие СЛЕДУЮЩЕГО дня
        if hour < current_time.hour - 2:
            # Event is for tomorrow
            event_time_today += timedelta(days=1)
        
        # Allow events from 2 hours ago to 48 hours ahead
        past_threshold = current_time - timedelta(hours=2)
        future_threshold = current_time + timedelta(hours=48)
        
        # Check if event time is within the valid range
        return past_threshold <= event_time_today <= future_threshold
    except ValueError:
        # If we can't parse the time, consider it valid
        logging.debug(f"Accepting event with unparsable time: {event_time_str}")
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
        
        # Check if we have data
        if not data:
            logging.warning(f"No data returned from Odds API for teams: {home_team} vs {away_team}")
            return None
            
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
            logging.warning(f"Failed to fetch {url}, status code: {response.status_code}")
            return None
        
        # Parse the HTML content
        soup = BeautifulSoup(response.content, 'html.parser')
        
        # Look for script tags that might contain JSON data
        scripts = soup.find_all('script')
        logging.info(f"Found {len(scripts)} script tags")
        
        # Look for schedule data in script tags using the improved method
        schedule_data = []
        broadcasts = []
        
        # Get current time for filtering
        current_time = get_current_time()
        
        # Process all script tags to find schedule data
        for i, script in enumerate(scripts):
            if script.string:
                script_content = script.string
                # Extract the JSON data using a more precise pattern
                # The data is in a format like: "schedule":[{...}]
                schedule_pattern = re.compile(r'"schedule":(\[\{.*?\}\])')
                schedule_matches = schedule_pattern.findall(script_content)
                
                logging.info(f"Script {i} has {len(schedule_matches)} schedule matches")
                
                for j, schedule_json in enumerate(schedule_matches):
                    try:
                        # Try to parse the schedule JSON
                        schedule_items = json.loads(schedule_json)
                        logging.info(f"Schedule {j+1} in script {i} has {len(schedule_items)} items")
                        
                        # Add items to our schedule data
                        for item in schedule_items:
                            schedule_data.append(item)
                    except json.JSONDecodeError as e:
                        logging.warning(f"JSON decode error for schedule {j+1} in script {i}: {e}")
                        # Try to fix common issues
                        # Remove escaped quotes
                        fixed_json = schedule_json.replace('\\"', '"')
                        try:
                            schedule_items = json.loads(fixed_json)
                            logging.info(f"Fixed JSON for schedule {j+1} in script {i}, has {len(schedule_items)} items")
                            for item in schedule_items:
                                schedule_data.append(item)
                        except json.JSONDecodeError:
                            logging.warning(f"Still couldn't parse schedule {j+1} in script {i}")
        
        logging.info(f"\nTotal schedule items found: {len(schedule_data)}")
        
        # Process schedule data
        for item in schedule_data:
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
                'bellator' in lower_title or 'bellator' in lower_genre or
                'aca' in lower_title or 'aca' in lower_genre or
                'fight night' in lower_title or 'fight night' in lower_genre or
                'бой' in lower_title or 'бой' in lower_genre or
                'единоборства' in lower_title or 'единоборства' in lower_genre or
                'бокс' in lower_title or 'бокс' in lower_genre or
                'хоккей' in lower_title or 'хоккей' in lower_genre or
                'волейбол' in lower_title or 'волейбол' in lower_genre or
                'баскетбол' in lower_title or 'баскетбол' in lower_genre or
                'матч! боец' in lower_title or 'матч! боец' in lower_genre or
                'матч! футбол' in lower_title or 'матч! футбол' in lower_genre or
                'match! боец' in lower_title or 'match! боец' in lower_genre or
                'match! футбол' in lower_title or 'match! футбол' in lower_genre
            )
            
            # Only include sports events that are in the future
            # If title contains specific sports keywords, consider it valid even without live requirement
            has_sports_keywords = re.search(r'UFC|MMA|Футбол|Бокс', title, re.I)
            if is_sports and (is_live or has_sports_keywords) and is_future_event(time_str, current_time):
                # Determine sport type
                sport_type = "Unknown"
                if 'футбол' in lower_title or 'футбол' in lower_genre:
                    sport_type = "Football"
                elif ('mma' in lower_title or 'mma' in lower_genre or
                      'ufc' in lower_title or 'ufc' in lower_genre or
                      'bellator' in lower_title or 'bellator' in lower_genre or
                      'aca' in lower_title or 'aca' in lower_genre or
                      'fight night' in lower_title or 'fight night' in lower_genre or
                      'бой' in lower_title or 'бой' in lower_genre or
                      'единоборства' in lower_title or 'единоборства' in lower_genre or
                      'бокс' in lower_title or 'бокс' in lower_genre):
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
        
        # If we didn't find any broadcasts from JSON, try alternative parsing method
        if not broadcasts:
            logging.info("Trying alternative parsing method for matchtv.ru")
            # Look for all <a> or <div> tags containing "Прямой"
            # Find all elements containing "Прямой" text
            direct_elements = soup.find_all(string=re.compile(r'Прямой', re.I))
            logging.info(f"Found {len(direct_elements)} elements containing 'Прямой'")
            
            # Process each element
            for element in direct_elements:
                try:
                    # Get the parent element to get more context
                    parent = element.parent
                    # Look for time information in nearby elements
                    time_elements = parent.find_all_previous(string=re.compile(r'\d{1,2}:\d{2}', re.I))
                    time_str = "N/A"
                    if time_elements:
                        # Get the first time match
                        time_match = re.search(r'(\d{1,2}:\d{2})', time_elements[0])
                        if time_match:
                            time_str = time_match.group(1)
                
                    # Skip if time is not available
                    if time_str == "N/A":
                        continue
                
                    # Get the text content of the parent and siblings
                    full_text = ' '.join([t.strip() for t in parent.find_all(string=True) if t.strip()])
                    
                    # Validate title
                    title = full_text.strip()
                    if not title or len(title) < 5:
                        continue
                    # Skip obvious JavaScript/code
                    if re.search(r'\b(self\.|window\.|function\s|[\[\]{}])\b', title, re.I):
                        continue
                    # If title contains specific sports keywords, consider it valid
                    if re.search(r'UFC|MMA|Футбол|Бокс', title, re.I):
                        # This is 100% valid event
                        pass
                    # Trim title to 150 characters
                    title = title[:150].strip()
                    
                    # Check if this is a sports event
                    lower_text = title.lower()
                    is_sports = (
                        'футбол' in lower_text or
                        'mma' in lower_text or
                        'ufc' in lower_text or
                        'bellator' in lower_text or
                        'aca' in lower_text or
                        'fight night' in lower_text or
                        'бой' in lower_text or
                        'единоборства' in lower_text or
                        'бокс' in lower_text or
                        'хоккей' in lower_text or
                        'волейбол' in lower_text or
                        'баскетбол' in lower_text
                    )
                    
                    if is_sports and is_future_event(time_str, current_time):
                        # Determine sport type
                        sport_type = "Unknown"
                        if 'футбол' in lower_text:
                            sport_type = "Football"
                        elif ('mma' in lower_text or
                              'ufc' in lower_text or
                              'bellator' in lower_text or
                              'aca' in lower_text or
                              'fight night' in lower_text or
                              'бой' in lower_text or
                              'единоборства' in lower_text or
                              'бокс' in lower_text):
                            sport_type = "MMA"
                        elif 'хоккей' in lower_text:
                            sport_type = "Hockey"
                        elif 'волейбол' in lower_text:
                            sport_type = "Volleyball"
                        elif 'баскетбол' in lower_text:
                            sport_type = "Basketball"
                        
                        broadcast = {
                            "time": time_str,
                            "sport": sport_type,
                            "event": full_text[:100],  # Limit length
                            "link": "https://matchtv.ru/on-air"
                        }
                        broadcasts.append(broadcast)
                        logging.info(f"Found broadcast with alternative method: {time_str} - {sport_type} - {full_text[:50]}...")
                except Exception as e:
                    logging.warning(f"Error processing alternative element: {e}")
                    continue
                        
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
        # Use cloudscraper to avoid being blocked by the website
        scraper = cloudscraper.create_scraper(
            browser={
                'browser': 'chrome',
                'platform': 'darwin',
                'mobile': False
            }
        )
        
        # Use headers to avoid being blocked by the website
        headers = {
            'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0.0.0 Safari/537.36',
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
        
        response = scraper.get(url, headers=headers, timeout=15)
        
        logging.info(f"championat.com returned status code: {response.status_code}")
        
        if response.status_code != 200:
            logging.warning(f"Failed to fetch {url}, status code: {response.status_code}")
            # Log first 500 characters of response for debugging
            logging.info(f"Response preview (first 500 chars): {response.text[:500]}")
            return None
            
        # Check if response is empty or suspiciously short
        if len(response.text) < 1000:
            logging.warning(f"Response from championat.com is suspiciously short ({len(response.text)} chars)")
            logging.info(f"Response preview: {response.text[:500]}")
            
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
                ) or (
                    'матч! боец' in channel_name.lower()
                ) or (
                    'матч! футбол' in channel_name.lower()
                )
                
                # Check for sports content
                lower_title = title.lower()
                is_sports = (
                    'футбол' in lower_title or
                    'mma' in lower_title or
                    'ufc' in lower_title or
                    'bellator' in lower_title or
                    'aca' in lower_title or
                    'fight night' in lower_title or
                    'бой' in lower_title or
                    'единоборства' in lower_title or
                    'бокс' in lower_title or
                    'хоккей' in lower_title or
                    'волейбол' in lower_title or
                    'баскетбол' in lower_title
                )
                
                
                # Only include Match TV sports events that are in the future
                # If title contains specific sports keywords, consider it valid even without live requirement
                has_sports_keywords = re.search(r'UFC|MMA|Футбол|Бокс', title, re.I)
                if is_match_tv and is_sports and (is_live or has_sports_keywords) and is_future_event(time_str, current_time):
                    # Determine sport type
                    sport_type = "Unknown"
                    if 'футбол' in lower_title:
                        sport_type = "Football"
                    elif ('mma' in lower_title or 'ufc' in lower_title or
                          'bellator' in lower_title or 'aca' in lower_title or
                          'fight night' in lower_title or 'бой' in lower_title or
                          'единоборства' in lower_title or 'бокс' in lower_title):
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

        # If we didn't find any broadcasts, try alternative parsing method
        if not broadcasts:
            logging.info("Trying alternative parsing method for championat.com")
            # Look for all <a> or <div> tags containing "Прямой"
            # Find all elements containing "Прямой" text
            direct_elements = soup.find_all(string=re.compile(r'Прямой', re.I))
            logging.info(f"Found {len(direct_elements)} elements containing 'Прямой'")
            
            # Process each element
            for element in direct_elements:
                try:
                    # Get the parent element to get more context
                    parent = element.parent
                    # Look for time information in nearby elements
                    time_elements = parent.find_all_previous(string=re.compile(r'\d{1,2}:\d{2}', re.I))
                    time_str = "N/A"
                    if time_elements:
                        # Get the first time match
                        time_match = re.search(r'(\d{1,2}:\d{2})', time_elements[0])
                        if time_match:
                            time_str = time_match.group(1)
             
                    # Get the text content of the parent and siblings
                    full_text = ' '.join([t.strip() for t in parent.find_all(string=True) if t.strip()])
                     
                    # Check if this is a sports event
                    lower_text = full_text.lower()
                    is_sports = (
                        'футбол' in lower_text or
                        'mma' in lower_text or
                        'ufc' in lower_text or
                        'bellator' in lower_text or
                        'aca' in lower_text or
                        'fight night' in lower_text or
                        'бой' in lower_text or
                        'единоборства' in lower_text or
                        'бокс' in lower_text or
                        'хоккей' in lower_text or
                        'волейбол' in lower_text or
                        'баскетбол' in lower_text
                    )
                     
                    # Check if this is for Match TV
                    is_match_tv = (
                        'матч' in full_text.lower() and 'тв' in full_text.lower()
                    ) or (
                        'match' in full_text.lower() and 'tv' in full_text.lower()
                    )
                     
                    if is_match_tv and is_sports and is_future_event(time_str, current_time):
                        # Determine sport type
                        sport_type = "Unknown"
                        if 'футбол' in lower_text:
                            sport_type = "Football"
                        elif ('mma' in lower_text or
                              'ufc' in lower_text or
                              'bellator' in lower_text or
                              'aca' in lower_text or
                              'fight night' in lower_text or
                              'бой' in lower_text or
                              'единоборства' in lower_text or
                              'бокс' in lower_text):
                            sport_type = "MMA"
                        elif 'хоккей' in lower_text:
                            sport_type = "Hockey"
                        elif 'волейбол' in lower_text:
                            sport_type = "Volleyball"
                        elif 'баскетбол' in lower_text:
                            sport_type = "Basketball"
                         
                        broadcast = {
                            "time": time_str,
                            "sport": sport_type,
                            "event": full_text[:100],  # Limit length
                            "link": "https://matchtv.ru/on-air"
                        }
                        broadcasts.append(broadcast)
                        logging.info(f"Found broadcast with alternative method: {time_str} - {sport_type} - {full_text[:50]}...")
                except Exception as e:
                    logging.warning(f"Error processing alternative element: {e}")
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
        # Use cloudscraper to avoid being blocked by the website
        scraper = cloudscraper.create_scraper(
            browser={
                'browser': 'chrome',
                'platform': 'darwin',
                'mobile': False
            }
        )
        
        # Use headers to avoid being blocked by the website
        headers = {
            'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0.0.0 Safari/537.36',
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
        
        response = scraper.get(url, headers=headers, timeout=15)
        
        logging.info(f"liveresult.ru returned status code: {response.status_code}")
        
        if response.status_code != 200:
            logging.warning(f"Failed to fetch {url}, status code: {response.status_code}")
            # Log first 500 characters of response for debugging
            logging.info(f"Response preview (first 500 chars): {response.text[:500]}")
            return None
            
        # Check if response is empty or suspiciously short
        if len(response.text) < 1000:
            logging.warning(f"Response from liveresult.ru is suspiciously short ({len(response.text)} chars)")
            logging.info(f"Response preview: {response.text[:500]}")
            
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
                ) or (
                    'матч! боец' in channel_name.lower()
                ) or (
                    'матч! футбол' in channel_name.lower()
                )
                
                # Check for sports content
                lower_title = title.lower()
                is_sports = (
                    'футбол' in lower_title or
                    'mma' in lower_title or
                    'ufc' in lower_title or
                    'bellator' in lower_title or
                    'aca' in lower_title or
                    'fight night' in lower_title or
                    'бой' in lower_title or
                    'единоборства' in lower_title or
                    'бокс' in lower_title or
                    'хоккей' in lower_title or
                    'волейбол' in lower_title or
                    'баскетбол' in lower_title
                )
                
                
                # Only include Match TV sports events that are in the future
                # If title contains specific sports keywords, consider it valid even without live requirement
                has_sports_keywords = re.search(r'UFC|MMA|Футбол|Бокс', title, re.I)
                if is_match_tv and is_sports and (is_live or has_sports_keywords) and is_future_event(time_str, current_time):
                    # Determine sport type
                    sport_type = "Unknown"
                    if 'футбол' in lower_title:
                        sport_type = "Football"
                    elif ('mma' in lower_title or 'ufc' in lower_title or
                          'bellator' in lower_title or 'aca' in lower_title or
                          'fight night' in lower_title or 'бой' in lower_title or
                          'единоборства' in lower_title or 'бокс' in lower_title):
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
        # Use cloudscraper to avoid being blocked by the website
        scraper = cloudscraper.create_scraper(
            browser={
                'browser': 'chrome',
                'platform': 'darwin',
                'mobile': False
            }
        )
        
        # Use headers to avoid being blocked by the website
        headers = {
            'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0.0.0 Safari/537.36',
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
        
        response = scraper.get(url, headers=headers, timeout=15)
        
        logging.info(f"fight.ru returned status code: {response.status_code}")
        
        if response.status_code != 200:
            logging.warning(f"Failed to fetch {url}, status code: {response.status_code}")
            # Log first 500 characters of response for debugging
            logging.info(f"Response preview (first 500 chars): {response.text[:500]}")
            return None
            
        # Check if response is empty or suspiciously short
        if len(response.text) < 1000:
            logging.warning(f"Response from fight.ru is suspiciously short ({len(response.text)} chars)")
            logging.info(f"Response preview: {response.text[:500]}")
            
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
                    'bellator' in lower_title or
                    'aca' in lower_title or
                    'fight night' in lower_title or
                    'бой' in lower_title or
                    'единоборства' in lower_title or
                    'бокс' in lower_title or
                    'файтинг' in lower_title
                )
                
                # Filter for live broadcasts or TV transmissions - less strict
                # Consider event if title contains any of these keywords
                keywords = ['ufc', 'mma', 'bellator', 'aca', 'fight night', 'бой', 'единоборства', 'бокс', 'live', 'прямая трансляция', 'трансляци', 'твит', 'tv']
                has_keywords = any(keyword in lower_title for keyword in keywords)
                
                # Only include sports events that are in the future (relax live requirement)
                if is_sports and has_keywords and is_future_event(time_str, current_time):
                    # Determine sport type
                    sport_type = "MMA"
                    if 'бокс' in lower_title:
                        sport_type = "Boxing"
                    elif 'ufc' in lower_title:
                        sport_type = "UFC"
                    elif 'bellator' in lower_title:
                        sport_type = "Bellator"
                    elif 'aca' in lower_title:
                        sport_type = "ACA"
                    
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
        # Use cloudscraper to avoid being blocked by the website
        scraper = cloudscraper.create_scraper(
            browser={
                'browser': 'chrome',
                'platform': 'darwin',
                'mobile': False
            }
        )
        
        # Use headers to avoid being blocked by the website
        headers = {
            'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0.0.0 Safari/537.36',
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
        
        response = scraper.get(url, headers=headers, timeout=15)
        
        logging.info(f"sports.ru returned status code: {response.status_code}")
        
        if response.status_code != 200:
            logging.warning(f"Failed to fetch {url}, status code: {response.status_code}")
            # Log first 500 characters of response for debugging
            logging.info(f"Response preview (first 500 chars): {response.text[:500]}")
            return None
            
        # Check if response is empty or suspiciously short
        if len(response.text) < 1000:
            logging.warning(f"Response from sports.ru is suspiciously short ({len(response.text)} chars)")
            logging.info(f"Response preview: {response.text[:500]}")
            
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
                    'bellator' in lower_title or
                    'aca' in lower_title or
                    'fight night' in lower_title or
                    'бой' in lower_title or
                    'единоборства' in lower_title or
                    'бокс' in lower_title
                )
                
                # Filter for live broadcasts or TV transmissions - less strict
                # Consider event if title contains any of these keywords
                keywords = ['ufc', 'mma', 'bellator', 'aca', 'fight night', 'бой', 'единоборства', 'бокс', 'live', 'прямая трансляция', 'трансляци', 'твит', 'tv']
                has_keywords = any(keyword in lower_title for keyword in keywords)
                
                # Only include sports events that are in the future (relax live requirement)
                if is_sports and has_keywords and is_future_event(time_str, current_time):
                    # Determine sport type
                    sport_type = "Unknown"
                    if 'футбол' in lower_title:
                        sport_type = "Football"
                    elif ('mma' in lower_title or 'ufc' in lower_title or
                          'bellator' in lower_title or 'aca' in lower_title or
                          'fight night' in lower_title or 'бой' in lower_title or
                          'единоборства' in lower_title or 'бокс' in lower_title):
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
        # Use cloudscraper to avoid being blocked by the website
        scraper = cloudscraper.create_scraper(
            browser={
                'browser': 'chrome',
                'platform': 'darwin',
                'mobile': False
            }
        )
        
        # Use headers to avoid being blocked by the website
        headers = {
            'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0.0.0 Safari/537.36',
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
        
        url = "https://www.sport-express.ru/live/"
        logging.info(f"Trying to fetch {url}")
        
        response = scraper.get(url, headers=headers, timeout=15)
        
        logging.info(f"sport-express.ru returned status code: {response.status_code}")
        
        if response.status_code != 200:
            logging.warning(f"Failed to fetch {url}, status code: {response.status_code}")
            # Log first 500 characters of response for debugging
            logging.info(f"Response preview (first 500 chars): {response.text[:500]}")
            return None
            
        # Check if response is empty or suspiciously short
        if len(response.text) < 1000:
            logging.warning(f"Response from sport-express.ru is suspiciously short ({len(response.text)} chars)")
            logging.info(f"Response preview: {response.text[:500]}")
            
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
                    'bellator' in lower_title or
                    'aca' in lower_title or
                    'fight night' in lower_title or
                    'бой' in lower_title or
                    'единоборства' in lower_title or
                    'бокс' in lower_title
                )
                
                # Filter for live broadcasts or TV transmissions - less strict
                is_live = (
                    'прямая трансляция' in lower_title or
                    'live' in lower_title or
                    'прямой эфир' in lower_title or
                    'онлайн' in lower_title or
                    'тв' in lower_title or
                    'трансляци' in lower_title or
                    'video' in lower_title or
                    'ufc' in lower_title or
                    'матч тв' in lower_title or
                    'match tv' in lower_title
                )
                
                # Only include sports events that are in the future (relax live requirement)
                # If title contains UFC, Match TV, Live or TV - consider it our match
                has_keywords = (
                    'ufc' in lower_title or
                    'матч тв' in lower_title or
                    'match tv' in lower_title or
                    'live' in lower_title or
                    'тв' in lower_title
                )
                
                if is_sports and (is_live or has_keywords) and is_future_event(time_str, current_time):
                    # Determine sport type
                    sport_type = "Unknown"
                    if 'футбол' in lower_title:
                        sport_type = "Football"
                    elif ('mma' in lower_title or 'ufc' in lower_title or
                          'bellator' in lower_title or 'aca' in lower_title or
                          'fight night' in lower_title or 'бой' in lower_title or
                          'единоборства' in lower_title or 'бокс' in lower_title):
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
    
    # Save debug snapshot of all parsed text before filtering
    try:
        with open('last_parse_debug.txt', 'w', encoding='utf-8') as f:
            f.write("=== DEBUG SNAPSHOT OF ALL PARSED BROADCASTS ===\n")
            f.write(f"Total broadcasts before deduplication: {len(broadcasts)}\n\n")
            for i, broadcast in enumerate(broadcasts):
                f.write(f"{i+1}. Time: {broadcast['time']}, Sport: {broadcast['sport']}, Event: {broadcast['event']}")
                if 'source' in broadcast:
                    f.write(f", Source: {broadcast['source']}")
                f.write("\n")
        logging.info("Debug snapshot saved to last_parse_debug.txt")
    except Exception as e:
        logging.error(f"Error saving debug snapshot: {e}")
    
    # If we have very few broadcasts, just return them all (no deduplication needed)
    if len(broadcasts) <= 3:
        print(f"DEBUG: После дедупликации осталось событий: {len(broadcasts)}")
        return broadcasts
    
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
            # Check if names are similar (using fuzzy string matching)
            similarity = fuzz.ratio(normalized_name, group_name)
            # Also check partial similarity for cases like "UFC 327" vs "ЮФС 327: Прохазка"
            partial_similarity = fuzz.partial_ratio(normalized_name, group_name)
            
            # If similarity is high enough, consider them the same event
            if similarity >= 80 or partial_similarity >= 90:
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
    print(f"DEBUG: После дедупликации осталось событий: {len(unique_broadcasts)}")
    return unique_broadcasts

def get_broadcasts_multi_source():
    """
    Get sports broadcasts using multi-source approach with automatic switching
    Returns a list of broadcast dictionaries or empty list if no data found
    """
    logging.info("Starting multi-source broadcast fetching")
    
    # Try sources in priority order (only reliable sources)
    sources = [
        ("matchtv.ru", parse_matchtv_source),
        ("fight.ru", parse_fight_source),  # Priority for MMA/UFC
        ("championat.com", parse_championat_source),
        ("sports.ru", parse_sports_source),
        ("liveresult.ru", parse_liveresult_source)
        # Temporarily disabled due to 404 errors:
        # ("sport-express.ru", parse_sport_express_source),
    ]
    
    all_broadcasts = []
    
    # Collect data from all sources
    source_results = {}  # To store results for final report
    for source_name, source_function in sources:
        try:
            logging.info(f"Trying source: {source_name}")
            broadcasts = source_function()
            
            # Store results for final report
            source_results[source_name] = len(broadcasts) if broadcasts is not None else 0
            
            # If we got a valid result (not None), add it to our collection
            if broadcasts is not None:
                logging.info(f"Successfully got {len(broadcasts)} broadcasts from {source_name}")
                all_broadcasts.extend(broadcasts)
            else:
                logging.info(f"No data returned from {source_name}")
                
            # Add random delay between requests (2-5 seconds)
            delay = random.uniform(2, 5)
            logging.info(f"Waiting {delay:.2f} seconds before next request...")
            time.sleep(delay)
                
        except Exception as e:
            logging.error(f"Error with source {source_name}: {e}")
            source_results[source_name] = 0
            continue
    
    # Print final report
    logging.info("=== FINAL REPORT ===")
    for source, count in source_results.items():
        logging.info(f"{source}: {count} matches found")
    logging.info("====================")
    
    # Debug output - show all raw data before deduplication
    logging.info(f"!!! RAW DATA BEFORE FILTERS: {[(b['time'], b['event']) for b in all_broadcasts]}")
    
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
    
    try:
        # Simple markdown escape function
        def escape_md(text):
            if not text:
                return ""
            # Escape special markdown characters
            special_chars = ['_', '*', '[', ']', '(', ')', '~', '`', '>', '#', '+', '-', '=', '|', '{', '}', '.', '!']
            for char in special_chars:
                text = text.replace(char, '\\' + char)
            return text
        message_text = "📺 Расписание прямых трансляций на сегодня:\n\n"
        
        for broadcast in broadcasts:
            # Determine emoji based on sport type
            emoji = "📺"
            if broadcast['sport'] == "Football":
                emoji = "⚽"
            elif broadcast['sport'] in ["MMA", "Boxing", "UFC"]:
                emoji = "🥊"
            
            # Escape markdown and limit length
            safe_time = escape_md(broadcast['time'])
            safe_event = escape_md(broadcast['event'])
            safe_event = (safe_event[:200] + '…') if len(safe_event) > 200 else safe_event
            
            message_text += f"⏰ {safe_time}\n"
            message_text += f"{emoji} {broadcast['sport']}: {safe_event}\n"
            
            # Add source information
            if 'source' in broadcast:
                safe_source = escape_md(broadcast['source'])
                message_text += f"Источник данных: {safe_source}\n"
            
            # Add odds if available
            if 'odds' in broadcast and broadcast['odds']:
                safe_odds = escape_md(broadcast['odds'])
                message_text += f"{safe_odds}\n"
            else:
                # Try to extract team names and get odds
                home_team, away_team = extract_team_names(broadcast['event'])
                if home_team and away_team:
                    odds = get_odds(home_team, away_team)
                    if odds:
                        safe_odds = escape_md(odds)
                        message_text += f"{safe_odds}\n"
            
            safe_link = escape_md(broadcast['link'])
            message_text += f"🔗 [Смотреть онлайн]({safe_link})\n\n"
        
        # Additional markdown protection
        message_text = message_text.replace("_", "\\_").replace("*", "\\*").replace("[", "\\[").replace("]", "\\]").replace("(", "\\(").replace(")", "\\)")
        
        return message_text
    except Exception as e:
        logging.error(f"Error formatting broadcast message: {e}")
        # Return a simple message even if formatting fails
        return f"📺 Найдено {len(broadcasts)} трансляций. Подробности смотрите на сайте."

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