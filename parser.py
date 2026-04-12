import logging
import requests
import cloudscraper
from bs4 import BeautifulSoup
from datetime import datetime, timedelta
import re
import json
from config import ODDS_API_KEY
from fuzzywuzzy import fuzz
import asyncio
import aiohttp

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Expanded sports keywords
FOOTBALL_KEYWORDS = [
    'футбол', 'рпл', 'апл', 'серия а', 'ла лига', 'бундеслига',
    'лига чемпионов', 'лига европы', 'кубок', 'чемпионат'
]
MMA_KEYWORDS = [
    'mma', 'ufc', 'юфс', 'аса', 'bellator', 'fight night',
    'прохазка', 'бой', 'единоборства', 'бокс'
]

# Stop words that indicate non-sports events
STOP_WORDS = [
    'плавание', 'баскетбол', 'волейбол', 'хоккей', 'теннис', 'биатлон',
    'лыжи', 'боулинг', 'кубок мира', 'гарри поттер'
]

# Trash keywords to remove (soft cleaning)
TRASH_KEYWORDS = [
    'войти на сайт', 'выход', 'эфир', 'телепрограмма',
    'смотри в ultra hd с', 'переключай камеры', 'трансляция в ultra hd 4k',
    'сегодня,', 'завтра,', 'футбол хоккей единоборства',
    'сегодня', 'завтра', 'переключай камеры', 'смотри в ultra hd',
    'Переключай камеры', 'Завтра,', 'Сегодня,'
]

# Date patterns to remove
DATE_PATTERNS = [
    r'\d{1,2} апр,', r'\d{1,2} мая,', r'\d{1,2} июн,', r'\d{1,2} июл,',
    r'\d{1,2} авг,', r'\d{1,2} сен,', r'\d{1,2} окт,', r'\d{1,2} ноя,',
    r'\d{1,2} дек,', r'\d{1,2} янв,', r'\d{1,2} фев,', r'\d{1,2} мар,'
]

def get_current_time():
    """Get current time in Moscow timezone"""
    return datetime.now()

def is_future_event(event_time_str, event_date_str, current_time):
    """Check if event time is in the future or within the past 2 hours, up to 48 hours ahead"""
    try:
        hour, minute = map(int, event_time_str.split(':'))
        # Create event time for the specified date or today
        if event_date_str:
            # Parse the date string (format: YYYY-MM-DD)
            event_date = datetime.strptime(event_date_str, "%Y-%m-%d")
            event_time = event_date.replace(hour=hour, minute=minute, second=0, microsecond=0)
        else:
            # Create event time for today
            event_time = current_time.replace(hour=hour, minute=minute, second=0, microsecond=0)
        
        # Allow events from 2 hours ago to 48 hours ahead
        past_threshold = current_time - timedelta(hours=2)
        future_threshold = current_time + timedelta(hours=48)
        
        # Check if event time is within the valid range
        return past_threshold <= event_time <= future_threshold
    except ValueError:
        # If we can't parse the time, consider it valid
        logger.debug(f"Accepting event with unparsable time: {event_time_str}")
        return True

def clean_event_title(text):
    """Clean event title by removing advertising phrases and limiting length"""
    if not text:
        return text
    
    # Remove extra whitespace
    text = text.strip()
    
    # Remove time at the beginning (e.g., "21:40")
    text = re.sub(r'^\d{1,2}:\d{2}\s*', '', text)
    
    # Aggressive cleaning: remove specific advertising phrases
    for keyword in TRASH_KEYWORDS:
        text = text.replace(keyword, '')
    
    # Remove date patterns
    for pattern in DATE_PATTERNS:
        text = re.sub(pattern, '', text, flags=re.IGNORECASE)
    
    # Remove extra whitespace again
    text = re.sub(r'\s+', ' ', text).strip()
    
    # Limit length to 150 characters
    if len(text) > 150:
        text = text[:150].strip()
    
    return text

def extract_team_names(event_title):
    """Extract real team/fighter names from event title"""
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

async def get_odds(home_team, away_team):
    """Get odds for a match from The Odds API"""
    if not ODDS_API_KEY:
        logger.warning("ODDS_API_KEY not found in config")
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
        
        async with aiohttp.ClientSession() as session:
            async with session.get(url, params=params, timeout=10) as response:
                if response.status == 429:
                    logger.warning("Odds API rate limit reached")
                    return None
                    
                if response.status != 200:
                    logger.error(f"Odds API error: {response.status} - {await response.text()}")
                    return None
                    
                data = await response.json()
                
                # Check if we have data
                if not data:
                    logger.warning(f"No data returned from Odds API for teams: {home_team} vs {away_team}")
                    return None
                    
                # Search for matching events
                best_match_score = 0
                best_odds = None
                
                for event in data:
                    event_home_team = event.get('home_team', '').lower()
                    event_away_team = event.get('away_team', '').lower()
                    
                    # Calculate similarity scores
                    home_score = max(
                        fuzz.ratio(home_team.lower(), event_home_team),
                        fuzz.ratio(home_team.lower(), event_away_team)
                    )
                    away_score = max(
                        fuzz.ratio(away_team.lower(), event_home_team),
                        fuzz.ratio(away_team.lower(), event_away_team)
                    )
                    
                    # Average score
                    avg_score = (home_score + away_score) / 2
                    
                    # If this is a better match
                    if avg_score > best_match_score and avg_score > 70:  # Threshold for good match
                        best_match_score = avg_score
                        
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
                                        best_odds = f"📊 Коэффициенты: П1: {home_price} | Х: {draw_price} | П2: {away_price}"
                                    else:
                                        best_odds = f"📊 Коэффициенты: П1: {home_price} | П2: {away_price}"
                
                return best_odds
                
    except Exception as e:
        logger.error(f"Error getting odds for {home_team} vs {away_team}: {e}")
        return None

def is_sports_event(title, genre=""):
    """Check if the event is a sports event we're interested in"""
    # First check if we should ignore this event
    if should_ignore_event(title):
        return False
    
    lower_title = title.lower()
    lower_genre = genre.lower() if genre else ""
    
    # Check for football keywords
    is_football = any(keyword in lower_title or keyword in lower_genre for keyword in FOOTBALL_KEYWORDS)
    
    # Check for MMA keywords
    is_mma = any(keyword in lower_title or keyword in lower_genre for keyword in MMA_KEYWORDS)
    
    return is_football or is_mma

def should_ignore_event(title):
    """Check if event should be ignored based on stop words"""
    lower_title = title.lower()
    
    # Check for stop words
    for stop_word in STOP_WORDS:
        if stop_word in lower_title:
            # Exception: if title contains team names, don't ignore
            # Check if there's a team match pattern (e.g., "Зенит - Краснодар")
            if re.search(r'.*[-–—].*', title):
                return False
            return True
    return False

def determine_sport_type(title, genre=""):
    """Determine the sport type of an event"""
    lower_title = title.lower()
    lower_genre = genre.lower() if genre else ""
    
    # Check for football keywords
    is_football = any(keyword in lower_title or keyword in lower_genre for keyword in FOOTBALL_KEYWORDS)
    
    # Check for MMA keywords
    is_mma = any(keyword in lower_title or keyword in lower_genre for keyword in MMA_KEYWORDS)
    
    if is_football:
        return "Football"
    elif is_mma:
        return "MMA"
    else:
        return "Unknown"

async def parse_matchtv_source(date_str=None):
    """Parse sports broadcasts from matchtv.ru"""
    logger.info(f"Attempting to fetch data from matchtv.ru for date {date_str or 'today'}")
    
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
        if date_str:
            url = f"https://matchtv.ru/tvguide?date={date_str}"
        else:
            url = "https://matchtv.ru/tvguide"
            
        response = scraper.get(url, headers=headers, timeout=15)
        
        if response.status_code != 200:
            logger.warning(f"Failed to fetch {url}, status code: {response.status_code}")
            return []
        
        # Parse the HTML content
        soup = BeautifulSoup(response.content, 'html.parser')
        
        broadcasts = []
        
        # Get current time for filtering
        current_time = get_current_time()
        
        # Try to find JSON data in script tags
        scripts = soup.find_all('script')
        schedule_data = []
        
        # Look for schedule data in script tags
        for i, script in enumerate(scripts):
            if script.string:
                script_content = script.string
                # Extract the JSON data using a pattern
                schedule_pattern = re.compile(r'"schedule":(\[\{.*?\}\])')
                schedule_matches = schedule_pattern.findall(script_content)
                
                if schedule_matches:
                    logger.info(f"Found schedule data in script {i}")
                    for j, schedule_json in enumerate(schedule_matches):
                        try:
                            # Try to parse the schedule JSON
                            schedule_items = json.loads(schedule_json)
                            logger.info(f"Schedule {j+1} in script {i} has {len(schedule_items)} items")
                            
                            # Add items to our schedule data
                            for item in schedule_items:
                                schedule_data.append(item)
                        except json.JSONDecodeError as e:
                            logger.warning(f"JSON decode error for schedule {j+1} in script {i}: {e}")
                            # Try to fix common issues
                            fixed_json = schedule_json.replace('\\"', '"')
                            try:
                                schedule_items = json.loads(fixed_json)
                                logger.info(f"Fixed JSON for schedule {j+1} in script {i}, has {len(schedule_items)} items")
                                for item in schedule_items:
                                    schedule_data.append(item)
                            except json.JSONDecodeError:
                                logger.warning(f"Still couldn't parse schedule {j+1} in script {i}")
                    break  # Found schedule data, no need to check other scripts
        
        logger.info(f"Total schedule items found: {len(schedule_data)}")
        
        # Process schedule data if found
        for item in schedule_data:
            time_str = item.get('time', 'N/A')
            title = item.get('title', '')
            genre = item.get('genre', '')
            
            # Fix escaped quotes
            title = title.replace('\\"', '"')
            
            # Clean the title
            title = clean_event_title(title)
            
            # Skip if title is empty or too short
            if not title or len(title) < 3:
                continue
            
            # Check for sports content
            if is_sports_event(title, genre):
                # Check if event is in the future
                if is_future_event(time_str, date_str, current_time):
                    # Determine sport type
                    sport_type = determine_sport_type(title, genre)
                    
                    broadcast = {
                        "time": time_str,
                        "sport": sport_type,
                        "event": title,
                        "link": "https://matchtv.ru/video/live",
                        "source": "matchtv.ru"
                    }
                    broadcasts.append(broadcast)
                    logger.info(f"Found broadcast: {time_str} - {sport_type} - {title[:50]}...")
        
        # If we didn't find any broadcasts from JSON, try alternative parsing method
        if not broadcasts:
            logger.info("Trying alternative parsing method for matchtv.ru")
            # Look for all elements that might contain broadcast information
            all_elements = soup.find_all(['div', 'a', 'span', 'p', 'li', 'td', 'tr', 'h1', 'h2', 'h3', 'h4', 'h5', 'h6'])
            # Filter elements that contain sports keywords
            all_elements = [elem for elem in all_elements if elem.get_text() and
                           (re.search(r'Футбол|ММА|UFC|Бокс', elem.get_text(), re.I))]
            logger.info(f"Found {len(all_elements)} potential broadcast elements")
            
            # Process each element
            for element in all_elements:
                try:
                    # Get the element itself and its parent to get more context
                    parent = element.parent
                    # Look for time information in the element or nearby elements
                    time_elements = element.find_all(string=re.compile(r'\d{1,2}:\d{2}', re.I))
                    if not time_elements:
                        time_elements = parent.find_all(string=re.compile(r'\d{1,2}:\d{2}', re.I))
                    if not time_elements:
                        # Look for time elements in siblings
                        time_elements = parent.find_all_previous(string=re.compile(r'\d{1,2}:\d{2}', re.I))
                    
                    time_str = "N/A"
                    if time_elements:
                        # Get the first time match
                        time_match = re.search(r'(\d{1,2}:\d{2})', str(time_elements[0]))
                        if time_match:
                            time_str = time_match.group(1)
                
                    # Skip if time is not available
                    if time_str == "N/A":
                        continue
                
                    # Get the text content of the element and its siblings
                    full_text = ' '.join([t.strip() for t in element.find_all(string=True) if t.strip()])
                    if not full_text:
                        full_text = ' '.join([t.strip() for t in parent.find_all(string=True) if t.strip()])
                    
                    # Validate title - only process elements with text length under 200 characters
                    title = full_text.strip()
                    if not title or len(title) < 5 or len(title) > 200:
                        continue
                    
                    # Skip obvious JavaScript/code
                    if re.search(r'\b(self\.|window\.|function\s|[\[\]{}])\b', title, re.I):
                        continue
                    
                    # Clean the title
                    title = clean_event_title(title)
                    
                    # Check for sports content
                    if is_sports_event(title):
                        # Check if event is in the future
                        if is_future_event(time_str, date_str, current_time):
                            # Determine sport type
                            sport_type = determine_sport_type(title)
                            
                            broadcast = {
                                "time": time_str,
                                "sport": sport_type,
                                "event": title,
                                "link": "https://matchtv.ru/video/live",
                                "source": "matchtv.ru"
                            }
                            broadcasts.append(broadcast)
                            logger.info(f"Found broadcast with alternative method: {time_str} - {sport_type} - {title[:50]}...")
                except Exception as e:
                    logger.warning(f"Error processing alternative element: {e}")
                    continue
                            
        # Sort by time
        broadcasts.sort(key=lambda x: x['time'])
        
        logger.info(f"Successfully parsed {len(broadcasts)} broadcasts from matchtv.ru")
        return broadcasts
            
    except Exception as e:
        logger.error(f"Error parsing matchtv.ru: {e}")
        return []

async def parse_sports_source(date_str=None):
    """Parse sports broadcasts from sports.ru"""
    logger.info(f"Attempting to fetch data from sports.ru for date {date_str or 'today'}")
    
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
        
        if date_str:
            url = f"https://sports.ru/tv/?date={date_str}"
        else:
            url = "https://sports.ru/tv/"
        logger.info(f"Trying to fetch {url}")
        
        response = scraper.get(url, headers=headers, timeout=15)
        
        logger.info(f"sports.ru returned status code: {response.status_code}")
        
        if response.status_code != 200:
            logger.warning(f"Failed to fetch {url}, status code: {response.status_code}")
            return []
            
        soup = BeautifulSoup(response.text, 'html.parser')
        broadcasts = []
        
        # Get current time for filtering
        current_time = get_current_time()
        
        # Look for TV schedule items
        schedule_items = soup.find_all('div', class_=re.compile(r'tv|schedule|broadcast', re.I))
        
        if not schedule_items:
            # Try alternative selectors
            schedule_items = soup.find_all('div', class_=re.compile(r'item|row', re.I))
        
        logger.info(f"Found {len(schedule_items)} schedule items on sports.ru")
        
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
                
                # Extract title - look in all <a> and <span> tags
                title_elem = item.find(['h3', 'h2', 'div'], class_=re.compile(r'title|name|event', re.I))
                if not title_elem:
                    # Look for <a> tags first
                    title_elem = item.find('a')
                if not title_elem:
                    # Look for <span> tags
                    title_elem = item.find('span')
                
                title = ""
                if title_elem:
                    title = title_elem.get_text(strip=True)
                else:
                    # If no specific element found, get all text from the item
                    title = item.get_text(strip=True)
                
                # Clean the title
                title = clean_event_title(title)
                
                # Skip if title is empty or too short
                if not title or len(title) < 3:
                    continue
                
                # Convert title to lowercase for matching
                lower_title = title.lower()
                
                # Simplified filter: if text contains specific keywords, take the match
                sports_keywords = ["ufc", "mma", "бой", "юфс", "футбол", "рпл", "лига", "чемпионат"]
                if any(keyword in lower_title for keyword in sports_keywords):
                    # Check if event is in the future
                    if is_future_event(time_str, date_str, current_time):
                        # Determine sport type
                        sport_type = determine_sport_type(title)
                        
                        broadcast = {
                            "time": time_str,
                            "sport": sport_type,
                            "event": title,
                            "link": "https://sports.ru/tv/" if not date_str else f"https://sports.ru/tv/?date={date_str}",
                            "source": "sports.ru"
                        }
                        broadcasts.append(broadcast)
                        logger.info(f"Found broadcast: {time_str} - {sport_type} - {title[:50]}...")
                        
            except Exception as e:
                logger.warning(f"Error processing sports.ru item: {e}")
                continue
        
        # Sort by time
        broadcasts.sort(key=lambda x: x['time'])
        
        logger.info(f"Successfully parsed {len(broadcasts)} broadcasts from sports.ru")
        return broadcasts
            
    except Exception as e:
        logger.error(f"Error parsing sports.ru: {e}")
        return []

async def parse_liveresult_source(date_str=None):
    """Parse sports broadcasts from liveresult.ru"""
    logger.info(f"Attempting to fetch data from liveresult.ru for date {date_str or 'today'}")
    
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
        
        if date_str:
            url = f"https://www.liveresult.ru/tv/?date={date_str}"
        else:
            url = "https://www.liveresult.ru/tv/"
        logger.info(f"Trying to fetch {url}")
        
        response = scraper.get(url, headers=headers, timeout=15)
        
        logger.info(f"liveresult.ru returned status code: {response.status_code}")
        
        if response.status_code != 200:
            logger.warning(f"Failed to fetch {url}, status code: {response.status_code}")
            return []
            
        soup = BeautifulSoup(response.text, 'html.parser')
        broadcasts = []
        
        # Get current time for filtering
        current_time = get_current_time()
        
        # Look for TV schedule items
        schedule_items = soup.find_all('div', class_=re.compile(r'event|match|broadcast', re.I))
        
        if not schedule_items:
            # Try alternative selectors
            schedule_items = soup.find_all('div', class_=re.compile(r'item|row', re.I))
        
        logger.info(f"Found {len(schedule_items)} schedule items on liveresult.ru")
        
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
                
                # Clean the title
                title = clean_event_title(title)
                
                # Skip if title is empty or too short
                if not title or len(title) < 3:
                    continue
                
                # Check for sports content
                if is_sports_event(title):
                    # Check if event is in the future
                    if is_future_event(time_str, date_str, current_time):
                        # Determine sport type
                        sport_type = determine_sport_type(title)
                        
                        broadcast = {
                            "time": time_str,
                            "sport": sport_type,
                            "event": title,
                            "link": "https://www.liveresult.ru/tv/" if not date_str else f"https://www.liveresult.ru/tv/?date={date_str}",
                            "source": "liveresult.ru"
                        }
                        broadcasts.append(broadcast)
                        logger.info(f"Found broadcast: {time_str} - {sport_type} - {title[:50]}...")
                        
            except Exception as e:
                logger.warning(f"Error processing liveresult item: {e}")
                continue
        
        # Sort by time
        broadcasts.sort(key=lambda x: x['time'])
        
        logger.info(f"Successfully parsed {len(broadcasts)} broadcasts from liveresult.ru")
        return broadcasts
            
    except Exception as e:
        logger.error(f"Error parsing liveresult.ru: {e}")
        return []

async def parse_fight_source(date_str=None):
    """Parse sports broadcasts from fight.ru"""
    logger.info(f"Attempting to fetch data from fight.ru for date {date_str or 'today'}")
    
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
        
        if date_str:
            url = f"https://fight.ru/tv/?date={date_str}"
        else:
            url = "https://fight.ru/tv/"
        logger.info(f"Trying to fetch {url}")
        
        response = scraper.get(url, headers=headers, timeout=15)
        
        logger.info(f"fight.ru returned status code: {response.status_code}")
        
        if response.status_code != 200:
            logger.warning(f"Failed to fetch {url}, status code: {response.status_code}")
            return []
            
        soup = BeautifulSoup(response.text, 'html.parser')
        broadcasts = []
        
        # Get current time for filtering
        current_time = get_current_time()
        
        # Look for TV schedule items
        schedule_items = soup.find_all('div', class_=re.compile(r'event|match|broadcast', re.I))
        
        if not schedule_items:
            # Try alternative selectors
            schedule_items = soup.find_all('div', class_=re.compile(r'item|row', re.I))
        
        logger.info(f"Found {len(schedule_items)} schedule items on fight.ru")
        
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
                
                # Clean the title
                title = clean_event_title(title)
                
                # Skip if title is empty or too short
                if not title or len(title) < 3:
                    continue
                
                # Focus only on MMA events for fight.ru
                mma_keywords = ["ufc", "mma", "бой", "юфс", "аса", "bellator", "fight night", "прохазка", "единоборства", "бокс"]
                lower_title = title.lower()
                if any(keyword in lower_title for keyword in mma_keywords):
                    # Check if event is in the future
                    if is_future_event(time_str, date_str, current_time):
                        # Determine sport type
                        sport_type = determine_sport_type(title)
                        
                        broadcast = {
                            "time": time_str,
                            "sport": sport_type,
                            "event": title,
                            "link": "https://fight.ru/tv/" if not date_str else f"https://fight.ru/tv/?date={date_str}",
                            "source": "fight.ru"
                        }
                        broadcasts.append(broadcast)
                        logger.info(f"Found broadcast: {time_str} - {sport_type} - {title[:50]}...")
                        
            except Exception as e:
                logger.warning(f"Error processing fight.ru item: {e}")
                continue
        
        # Sort by time
        broadcasts.sort(key=lambda x: x['time'])
        
        logger.info(f"Successfully parsed {len(broadcasts)} broadcasts from fight.ru")
        return broadcasts
            
    except Exception as e:
        logger.error(f"Error parsing fight.ru: {e}")
        return []

def deduplicate_broadcasts(broadcasts):
    """Remove duplicate broadcasts based on event name and time similarity"""
    if not broadcasts:
        return []
    
    # Group broadcasts by time (same minute) and keep the longest text
    time_groups = {}
    for broadcast in broadcasts:
        # Create a key based on time (hour:minute)
        time_key = broadcast['time']
        
        # If we already have broadcasts with this time, keep the one with the longest event text
        if time_key in time_groups:
            if len(broadcast['event']) > len(time_groups[time_key]['event']):
                time_groups[time_key] = broadcast
        else:
            time_groups[time_key] = broadcast
    
    # Convert time_groups back to a list
    unique_broadcasts = list(time_groups.values())
    
    # Sort by time
    unique_broadcasts.sort(key=lambda x: x['time'])
    return unique_broadcasts

async def get_broadcasts_48h():
    """Get sports broadcasts for the next 48 hours using all sources"""
    logger.info("Starting 48-hour broadcast fetching")
    
    # Get current date and tomorrow's date in YYYY-MM-DD format
    current_time = get_current_time()
    today_str = current_time.strftime("%Y-%m-%d")
    tomorrow_time = current_time + timedelta(days=1)
    tomorrow_str = tomorrow_time.strftime("%Y-%m-%d")
    
    logger.info(f"Fetching data for {today_str} and {tomorrow_str}")
    
    # Define sources (keeping only reliable sources)
    sources = [
        ("matchtv.ru", parse_matchtv_source),
        ("sports.ru", parse_sports_source),
        ("fight.ru", parse_fight_source),
    ]
    
    all_broadcasts = []
    
    # Collect data from all sources for both today and tomorrow using asyncio.gather for speed
    today_tasks = [source_function(today_str) for _, source_function in sources]
    tomorrow_tasks = [source_function(tomorrow_str) for _, source_function in sources]
    
    # Execute all tasks concurrently
    today_results = await asyncio.gather(*today_tasks, return_exceptions=True)
    tomorrow_results = await asyncio.gather(*tomorrow_tasks, return_exceptions=True)
    
    # Process today's results
    for i, result in enumerate(today_results):
        source_name = sources[i][0]
        if isinstance(result, Exception):
            logger.error(f"Error with source {source_name} for today: {result}")
        elif result is not None:
            logger.info(f"Successfully got {len(result)} broadcasts from {source_name} for today")
            # Add date information to each broadcast
            for broadcast in result:
                broadcast['date'] = today_str
            all_broadcasts.extend(result)
    
    # Process tomorrow's results
    for i, result in enumerate(tomorrow_results):
        source_name = sources[i][0]
        if isinstance(result, Exception):
            logger.error(f"Error with source {source_name} for tomorrow: {result}")
        elif result is not None:
            logger.info(f"Successfully got {len(result)} broadcasts from {source_name} for tomorrow")
            # Add date information to each broadcast
            for broadcast in result:
                broadcast['date'] = tomorrow_str
            all_broadcasts.extend(result)
    
    # Remove duplicates
    unique_broadcasts = deduplicate_broadcasts(all_broadcasts)
    
    # Get odds for each unique broadcast
    for broadcast in unique_broadcasts:
        home_team, away_team = extract_team_names(broadcast['event'])
        if home_team and away_team:
            odds = await get_odds(home_team, away_team)
            if odds:
                broadcast['odds'] = odds
    
    logger.info(f"Successfully got {len(unique_broadcasts)} unique broadcasts from all sources")
    return unique_broadcasts

def format_broadcast_message(broadcasts):
    """Format broadcasts into a message string with proper emojis and odds"""
    if not broadcasts:
        return "*Трансляций не найдено*"
    
    try:
        # Simple markdown escape function
        def escape_md(text):
            if not text:
                return ""
            # Simple replacement for markdown escaping
            text = text.replace('_', '\\_')
            text = text.replace('*', '\\*')
            text = text.replace('[', '\\[')
            text = text.replace(']', '\\]')
            text = text.replace('(', '\\(')
            text = text.replace(')', '\\)')
            text = text.replace('~', '\\~')
            text = text.replace('`', '\\`')
            text = text.replace('>', '\\>')
            text = text.replace('#', '\\#')
            text = text.replace('+', '\\+')
            text = text.replace('-', '\\-')
            text = text.replace('=', '\\=')
            text = text.replace('|', '\\|')
            text = text.replace('{', '\\{')
            text = text.replace('}', '\\}')
            text = text.replace('.', '\\.')
            text = text.replace('!', '\\!')
            return text
        
        # Group broadcasts by date
        today_broadcasts = []
        tomorrow_broadcasts = []
        
        current_time = get_current_time()
        today_str = current_time.strftime("%Y-%m-%d")
        tomorrow_time = current_time + timedelta(days=1)
        tomorrow_str = tomorrow_time.strftime("%Y-%m-%d")
        
        for broadcast in broadcasts:
            # Clean the event title
            broadcast['event'] = clean_event_title(broadcast['event'])
            
            # Group by date
            broadcast_date = broadcast.get('date', today_str)
            if broadcast_date == today_str:
                today_broadcasts.append(broadcast)
            elif broadcast_date == tomorrow_str:
                tomorrow_broadcasts.append(broadcast)
        
        # Format message with separate sections for today and tomorrow
        message_text = "📺 *Расписание прямых трансляций на ближайшие 48 часов:*\n\n"
        
        # Today's broadcasts
        message_text += "*📅 СЕГОДНЯ:*\n"
        if today_broadcasts:
            for broadcast in today_broadcasts:
                # Determine emoji based on sport type
                emoji = "📺"
                if broadcast['sport'] == "Football":
                    emoji = "⚽"
                elif broadcast['sport'] == "MMA":
                    emoji = "🥊"
                
                # Escape markdown and limit length
                safe_time = escape_md(broadcast['time'])
                safe_event = escape_md(broadcast['event'])
                
                # Format as requested: ⏰ 13:40 | ⚽️ Футбол: Крылья Советов - Ахмат
                message_text += f"⏰ {safe_time} | {emoji} *{broadcast['sport']}*: {safe_event}\n"
                
                # Add odds if available
                if 'odds' in broadcast and broadcast['odds']:
                    safe_odds = escape_md(broadcast['odds'])
                    message_text += f"{safe_odds}\n"
                else:
                    # Try to extract team names and get odds
                    home_team, away_team = extract_team_names(broadcast['event'])
                    if home_team and away_team:
                        # Note: In a real implementation, we would await get_odds here
                        # But since this is a sync function, we'll skip it for now
                        pass
                
                # Add link
                safe_link = escape_md(broadcast['link'])
                message_text += f"🔗 [Смотреть трансляцию]({safe_link})\n\n"
        else:
            message_text += "_Трансляций не найдено_\n\n"
        
        # Tomorrow's broadcasts
        message_text += "*📅 ЗАВТРА:*\n"
        if tomorrow_broadcasts:
            for broadcast in tomorrow_broadcasts:
                # Determine emoji based on sport type
                emoji = "📺"
                if broadcast['sport'] == "Football":
                    emoji = "⚽"
                elif broadcast['sport'] == "MMA":
                    emoji = "🥊"
                
                # Escape markdown and limit length
                safe_time = escape_md(broadcast['time'])
                safe_event = escape_md(broadcast['event'])
                
                # Format as requested: ⏰ 13:40 | ⚽️ Футбол: Крылья Советов - Ахмат
                message_text += f"⏰ {safe_time} | {emoji} *{broadcast['sport']}*: {safe_event}\n"
                
                # Add odds if available
                if 'odds' in broadcast and broadcast['odds']:
                    safe_odds = escape_md(broadcast['odds'])
                    message_text += f"{safe_odds}\n"
                
                # Add link
                safe_link = escape_md(broadcast['link'])
                message_text += f"🔗 [Смотреть трансляцию]({safe_link})\n\n"
        else:
            message_text += "_Трансляций не найдено_\n\n"
        
        return message_text
    except Exception as e:
        logger.error(f"Error formatting broadcast message: {e}")
        # Return a simple message even if formatting fails
        return f"📺 Найдено {len(broadcasts)} трансляций. Подробности смотрите на сайте."

# Test function
async def test_parser():
    """Test the parser"""
    print("Testing parser...")
    
    try:
        broadcasts = await get_broadcasts_48h()
        
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
    # Run the test
    asyncio.run(test_parser())