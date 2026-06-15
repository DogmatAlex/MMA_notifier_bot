import logging
import requests
import cloudscraper
import asyncio
from bs4 import BeautifulSoup
from datetime import datetime, timedelta
import re
import json
from fuzzywuzzy import fuzz

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
    'бой', 'единоборства', 'бокс'
]

# Stop words that indicate non-sports events
STOP_WORDS = [
    'плавание', 'баскетбол', 'волейбол', 'хоккей', 'теннис', 'биатлон',
    'лыжи', 'боулинг', 'кубок мира', 'советский футбол', 'обзор', 'новости',
    'интервью', 'итоги', 'репортаж', 'дневник', 'фильм', 'синхронное плавание',
    'после футбола', 'черданцев', 'георгий', 'обзор тура', 'главные новости',
    'лучшие моменты', 'топ-10', 'фото', 'видео голов', 'человек из футбола',
    'сделано в россии', 'наши иностранцы', 'магия'
]

# Trash keywords to remove (soft cleaning)
TRASH_KEYWORDS = [
    'войти на сайт', 'выход', 'эфир', 'телепрограмма',
    'смотри в ultra hd с', 'переключай камеры', 'трансляция в ultra hd 4k',
    'сегодня,', 'завтра,', 'футбол хоккей единоборства',
    'сегодня', 'завтра', 'переключай камеры', 'смотри в ultra hd',
    'Переключай камеры', 'Завтра,', 'Сегодня,', '17 апр,', '18 апр,'
]

# Channel names to ignore (not sports events)
CHANNEL_NAMES_TO_IGNORE = [
    'футбол 1', 'футбол 2', 'футбол 3',
    'матч! футбол 1', 'матч! футбол 2', 'матч! футбол 3',
    'боец', 'арена', 'игра', 'страна', 'премьер',
    'матч! боец', 'матч! арена', 'матч! игра', 'матч! страна',
    'матч! премьер', 'матч тв', 'matchtv',
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

def is_sports_event(title, genre=""):
    """Check if the event is a sports event we're interested in"""
    if not title:
        return False
    
    # Convert to lowercase for case-insensitive matching
    lower_title = title.lower()
    lower_genre = genre.lower() if genre else ""
    
    # Combine title and genre for matching
    combined = f"{lower_title} {lower_genre}"
    
    # Check for stop words that indicate non-sports events
    if any(stop_word in combined for stop_word in STOP_WORDS):
        return False
    
    # Check for MMA keywords
    if any(mma_keyword in combined for mma_keyword in MMA_KEYWORDS):
        return True
    
    # Check for football keywords
    if any(football_keyword in combined for football_keyword in FOOTBALL_KEYWORDS):
        return True
    
    # If no specific keywords found, check for generic sports terms
    generic_sports = ['футбол', 'mma', 'ufc', 'аса', 'bellator', 'бой', 'единоборства']
    return any(sport in combined for sport in generic_sports)

def determine_sport_type(event_title, subtitle=""):
    """Determine sport type based on event title and subtitle"""
    combined_text = f"{event_title} {subtitle}".lower()
    
    # Check for MMA keywords first (higher priority)
    mma_keywords = ['mma', 'ufc', 'аса', 'bellator', 'бокс', 'единоборства', 'смешанные единоборства']
    if any(keyword in combined_text for keyword in mma_keywords):
        # Special case: if it's boxing but also mentions "кубок победы" - treat as MMA
        if 'бокс' in combined_text and ('кубок победы' in combined_text or 'кубок' in combined_text and 'победы' in combined_text):
            return "MMA"
        elif 'бокс' in combined_text:
            return "MMA"  # Treat boxing as MMA in our context
        else:
            return "MMA"
    
    # Check for football keywords
    football_keywords = ['футбол', 'рпл', 'апл', 'серия а', 'ла лига', 'бундеслига', 'лига чемпионов', 'лига европы']
    if any(keyword in combined_text for keyword in football_keywords):
        return "Football"
    
    # Default to Football if no specific sport detected
    return "Football"

async def parse_matchtv_source(date_str=None):
    """Parse sports broadcasts from matchtv.ru through direct HTML card parsing"""
    logger.info(f"Attempting to fetch data from matchtv.ru for date {date_str or 'today'}")
    
    # Import cache functions
    from cache import load_from_cache, save_to_cache
    
    # Try to load from cache first
    cached = load_from_cache("matchtv", date_str or "today")
    if cached:
        logger.info(f"Using cached data for matchtv.ru ({date_str or 'today'})")
        return cached
    
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
        
        # Try to get the live broadcasts page
        if date_str:
            # Try adding date parameter, if site supports it
            url = f"https://matchtv.ru/video/live?date={date_str}"
        else:
            url = "https://matchtv.ru/video/live"
            
        response = scraper.get(url, headers=headers, timeout=15)
        
        if response.status_code != 200:
            logger.warning(f"Failed to fetch {url}, status code: {response.status_code}")
            return []
        
        # Parse the HTML content
        soup = BeautifulSoup(response.content, 'html.parser')
        
        # Check if the date parameter is working
        if date_str and response.status_code == 200:
            # Look for date indicators in the response
            date_indicators = soup.find_all(string=re.compile(date_str.replace('-', '.')))
            if not date_indicators:
                logger.warning(f"Date parameter may not be working. Requested {date_str} but no date indicators found in response.")
                # Check if we're getting today's content instead of tomorrow's
                today = get_current_time().strftime("%Y-%m-%d")
                today_indicators = soup.find_all(string=re.compile(today.replace('-', '.')))
                if today_indicators:
                    logger.warning("It appears we're getting today's content instead of the requested date.")
                
                # Since the date parameter doesn't work, we need to fetch all broadcasts
                # and then filter them based on the parsed date from the badge
        
        broadcasts = []
        
        # Get current time for filtering
        current_time = get_current_time()
        
        # Find all broadcast cards by stable class
        cards = soup.find_all('div', class_='m-media-card-wrapper')
        logger.info(f"Found {len(cards)} broadcast cards on matchtv.ru")
        
        # === НОВОЕ: Строгая проверка вида спорта ===
        def is_allowed_sport(title: str, subtitle: str) -> bool:
            """Разрешаем только футбол и ММА/бокс/единоборства"""
            lower_title = title.lower()
            lower_subtitle = subtitle.lower()
            combined = f"{lower_title} {lower_subtitle}"
            
            # Явно запрещённые виды (даже если содержат "футбол" или "чемпионат")
            blocked = [
                'тхэквондо', 'регби', 'прыжки в воду', 'волейбол', 'баскетбол',
                'хоккей', 'теннис', 'биатлон', 'лыжи', 'плавание', 'гандбол',
                'водное поло', 'настольный теннис', 'бадминтон', 'фигурное катание',
                'керлинг', 'сноуборд', 'фристайл', 'шорт-трек'
            ]
            if any(kw in combined for kw in blocked):
                return False
            
            # Разрешённые виды
            football_ok = any(kw in combined for kw in ['футбол', 'фнл', 'рпл', 'ла лига', 'апл', 'серия а', 'бундеслига', 'лига чемпионов', 'лига европы'])
            mma_ok = any(kw in combined for kw in ['mma', 'ufc', 'аса', 'bellator', 'бокс', 'единоборства', 'смешанные единоборства', 'one fc', 'ural fc', 'aca'])
            
            return football_ok or mma_ok
        # === КОНЕЦ НОВОГО ===
        
        # === НОВОЕ: Извлечение даты из бейджа ===
        def parse_date_from_badge(badge_text: str, current_date) -> str:
            """Преобразует 'Сегодня, 19:55' или 'Завтра, 20:30' в YYYY-MM-DD"""
            if 'сегодня' in badge_text.lower():
                return current_date.strftime("%Y-%m-%d")
            elif 'завтра' in badge_text.lower():
                return (current_date + timedelta(days=1)).strftime("%Y-%m-%d")
            else:
                # Фоллбэк: пытаемся распарсить дату из текста (если сайт отдаёт "14 мая, 19:55")
                date_match = re.search(r'(\d{1,2})\s+(?:янв|фев|мар|апр|мая|июн|июл|авг|сен|окт|ноя|дек)[а-я]*', badge_text.lower())
                if date_match:
                    try:
                        # Упрощённый парсинг: предполагаем текущий год
                        from datetime import datetime
                        month_map = {'янв':1,'фев':2,'мар':3,'апр':4,'мая':5,'июн':6,'июл':7,'авг':8,'сен':9,'окт':10,'ноя':11,'дек':12}
                        day = int(date_match.group(1))
                        month_str = date_match.group(0).split()[1][:3]
                        month = month_map.get(month_str, current_date.month)
                        return datetime(current_date.year, month, day).strftime("%Y-%m-%d")
                    except:
                        pass
                # Если не получилось — используем дату из аргумента
                return current_date.strftime("%Y-%m-%d") if current_date else None
        # === КОНЕЦ НОВОГО ===
        
        # Process each card
        for card in cards:
            try:
                # 1. Extract time from date badge
                badge = card.find('div', class_='m-media-card-date-badge')
                badge_text = badge.get_text(strip=True) if badge else ""
                time_str = "N/A"
                if badge:
                    # Extract time from text
                    time_match = re.search(r'(\d{1,2}:\d{2})', badge_text)
                    if time_match:
                        time_str = time_match.group(1)
                
                # 2. Extract title (teams/fighters)
                title_elem = card.find('div', class_='m-media-card__title')
                title = title_elem.get_text(strip=True) if title_elem else ""
                
                # 3. Extract subtitle (tournament)
                subtitle_elem = card.find('div', class_='m-media-card-subtitle')
                subtitle = subtitle_elem.get_text(strip=True) if subtitle_elem else ""
                
                # 4. Combine into full event title
                full_title = f"{title} {subtitle}".strip() if subtitle else title
                
                # 5. Skip empty titles
                if not full_title or len(full_title) < 5:
                    continue
                
                # 6. Check if it's an allowed sport (football or MMA only)
                if not is_allowed_sport(title, subtitle):
                    continue
                
                # 7. Extract date from badge
                event_date = parse_date_from_badge(badge_text, current_time.date())
                
                # 8. Check if event is in the future (within 48 hours)
                if not is_future_event(time_str, event_date, current_time):
                    continue
                
                # 9. Determine sport type
                sport_type = determine_sport_type(full_title, subtitle)
                
                # 10. Create broadcast object
                broadcast = {
                    "time": time_str,
                    "sport": sport_type,
                    "event": clean_event_title(full_title),
                    "link": "https://matchtv.ru/video/live",
                    "source": "matchtv.ru",
                    "date": event_date  # Add date for debugging
                }
                broadcasts.append(broadcast)
                logger.info(f"Found broadcast: {time_str} - {sport_type} - {full_title[:50]}... (date: {event_date})")
                
            except Exception as e:
                logger.warning(f"Error processing card: {e}")
                continue
        
        # Sort by time
        broadcasts.sort(key=lambda x: x['time'])
        
        # If we requested a specific date, filter broadcasts to only include that date
        # This is necessary because the date parameter in the URL doesn't actually work
        if date_str:
            original_count = len(broadcasts)
            broadcasts = [b for b in broadcasts if b.get('date') == date_str]
        
        logger.info(f"Successfully parsed {len(broadcasts)} broadcasts from matchtv.ru")
        
        # Save to cache if we have broadcasts
        if broadcasts:
            save_to_cache("matchtv", date_str or "today", broadcasts)
        
        return broadcasts
            
    except Exception as e:
        logger.error(f"Error parsing matchtv.ru: {e}")
        return []

async def parse_fight_source(date_str=None):
    """Parse upcoming MMA events from fight.ru/schedule/"""
    logger.info("Attempting to fetch upcoming MMA events from fight.ru/schedule/")
    
    # Import cache functions
    from cache import load_from_cache, save_to_cache
    
    # Try to load from cache first
    cached = load_from_cache("fight_schedule", "upcoming")
    if cached:
        logger.info("Using cached data for fight.ru schedule (upcoming)")
        return cached
    
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
        
        # New URL for upcoming events
        url = "https://fight.ru/schedule/"
        
        response = scraper.get(url, headers=headers, timeout=15)
        
        if response.status_code != 200:
            logger.warning(f"Failed to fetch {url}, status code: {response.status_code}")
            return []
        
        # Parse the HTML content
        soup = BeautifulSoup(response.text, 'html.parser')
        broadcasts = []
        
        # Look for the upcoming tab (to avoid parsing past events)
        upcoming_tab = soup.find('div', id='upcoming', class_=re.compile(r'active|upcoming-tab', re.I))
        if not upcoming_tab:
            logger.warning("Could not find upcoming tab on fight.ru/schedule/")
            return []
        
        # Look for event items with correct CSS selectors only within the upcoming tab
        event_items = upcoming_tab.find_all('div', class_='fights-item position-relative')
        
        # Get current date for filtering
        current_date = datetime.now().date()
        
        for item in event_items:
            try:
                # Date
                date_elem = item.find('span', class_='date fw-bold')
                date_str = date_elem.get_text(strip=True) if date_elem else ""
                
                # Time (extract only time from "01:00 МСК")
                time_elem = item.find('span', class_='time text-nowrap')
                time_str = "N/A"
                if time_elem:
                    time_text = time_elem.get_text(strip=True)
                    time_match = re.search(r'(\d{1,2}:\d{2})', time_text)
                    if time_match:
                        time_str = time_match.group(1)
                
                # Tournament name
                title_elem = item.find('a', class_='fw-bold h6')
                title = title_elem.get_text(strip=True) if title_elem else ""
                if not title:
                    continue  # skip if no title
                
                # Location (next span after link)
                location = ""
                if title_elem:
                    location_elem = title_elem.find_next('span')
                    if location_elem:
                        location = location_elem.get_text(strip=True)
                
                # Format event (without location - it will be added separately)
                event_text = title
                
                # Convert date from DD.MM.YYYY to YYYY-MM-DD for sorting
                formatted_date = None
                event_date = None
                if date_str:
                    try:
                        date_obj = datetime.strptime(date_str, "%d.%m.%Y")
                        formatted_date = date_obj.strftime("%Y-%m-%d")
                        event_date = date_obj.date()
                        
                        # Filter events: only include events within 0-90 days from today
                        max_date = current_date + timedelta(days=90)
                        if event_date < current_date or event_date > max_date:
                            continue  # skip events outside the range
                    except ValueError:
                        logger.warning(f"Could not parse date: {date_str}")
                        pass
                
                broadcast = {
                    "time": time_str,
                    "sport": "MMA",
                    "event": event_text,
                    "link": "https://fight.ru" + title_elem['href'] if title_elem and title_elem.get('href') else "https://fight.ru/schedule/",
                    "source": "fight.ru",
                    "date_iso": formatted_date,      # YYYY-MM-DD for sorting/filtering
                    "date_display": date_str,       # DD.MM.YYYY for display to user
                    "location": location
                }
                broadcasts.append(broadcast)
                
            except Exception as e:
                logger.warning(f"Error parsing fight.ru event: {e}")
                continue
        
        # Sort by date
        broadcasts.sort(key=lambda x: x.get('date_iso', '') or '')
        
        logger.info(f"Successfully parsed {len(broadcasts)} upcoming events from fight.ru/schedule/")
        
        # Save to cache if we have broadcasts
        if broadcasts:
            save_to_cache("fight_schedule", "upcoming", broadcasts)
        
        return broadcasts
            
    except Exception as e:
        logger.error(f"Error parsing fight.ru/schedule/: {e}")
        return []

async def parse_championat_ucl_source(date_str=None) -> list:
    """
    Parse ONLY Champions League matches from championat.com
    URL pattern: https://www.championat.com/stat/#YYYY-MM-DD
    Returns: list of broadcasts in standard format
    """
    logger.info(f"Attempting to fetch Champions League data from championat.com for date {date_str or 'today'}")
    
    # Import cache functions
    from cache import load_from_cache, save_to_cache
    
    # Try to load from cache first
    cached = load_from_cache("championat_ucl", date_str or "today")
    if cached:
        logger.info(f"Using cached data for championat.com ({date_str or 'today'})")
        return cached
    
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
        
        # Try to get the schedule page
        if date_str:
            url = f"https://www.championat.com/stat/football/#date={date_str}"
        else:
            url = "https://www.championat.com/stat/football/"
            
        response = scraper.get(url, headers=headers, timeout=10)
        
        if response.status_code != 200:
            logger.warning(f"Failed to fetch {url}, status code: {response.status_code}")
            return []
        
        # Parse the HTML content
        soup = BeautifulSoup(response.content, 'html.parser')
        
        broadcasts = []
        
        # Get current time for filtering
        current_time = get_current_time()
        
        # Extract tournament stage information
        tournament_stage = None
        tournament_elem = soup.find('div', class_='seo-results__tournament')
        if tournament_elem:
            tournament_text = tournament_elem.get_text(strip=True)
            if "Лига чемпионов" in tournament_text or "лига чемпионов" in tournament_text:
                tournament_stage = clean_event_title(tournament_text)
        
        # Look for match links with UCL pattern
        # Find all links that contain /football/_ucl/ in href
        match_links = soup.find_all('a', href=re.compile(r'/football/_ucl/.*/match/\d+/'))
        
        for link in match_links:
            try:
                # Extract time from span with class seo-results__item-date
                time_elem = link.find_previous('span', class_='seo-results__item-date')
                time_str = "N/A"
                if time_elem:
                    time_text = time_elem.get_text(strip=True)
                    # Extract time in format HH:MM
                    time_match = re.search(r'(\d{1,2}:\d{2})', time_text)
                    if time_match:
                        time_str = time_match.group(1)
                
                # Extract match title from link text
                title = link.get_text(strip=True)
                
                # Skip if title is empty
                if not title:
                    continue
                
                # === ФИЛЬТР ЮНОШЕСКИХ/ЖЕНСКИХ ТУРНИРОВ (ПЕРЕД ОЧИСТКОЙ!) ===
                exclude_keywords = ["u19", "u17", "u15", "юношеск", "молодёж", "женск", "women", "youth", "junior"]
                if any(kw in title.lower() for kw in exclude_keywords):
                    continue
                # === КОНЕЦ ФИЛЬТРА ===
                
                # Clean title
                clean_title = clean_event_title(title)
                
                # Skip if title is empty after cleaning
                if not clean_title:
                    continue
                
                # Create broadcast object
                broadcast = {
                    "time": time_str,
                    "sport": "Football",
                    "event": clean_title,
                    "link": f"https://www.championat.com{link['href']}" if link.get('href') else "https://www.championat.com/stat/football/",
                    "source": "championat.com"
                }
                
                # Add tournament stage to event name if available
                if tournament_stage:
                    broadcast["event"] = f"{tournament_stage}: {broadcast['event']}"
                
                broadcasts.append(broadcast)
                logger.info(f"Found UCL broadcast: {time_str} - Football - {title[:50]}...")
                
            except Exception as e:
                logger.warning(f"Error parsing championat.com UCL match: {e}")
                continue
        
        # Sort by time
        broadcasts.sort(key=lambda x: x['time'])
        
        logger.info(f"Successfully parsed {len(broadcasts)} UCL broadcasts from championat.com")
        
        # Save to cache if we have broadcasts
        if broadcasts:
            save_to_cache("championat_ucl", date_str or "today", broadcasts)
        
        return broadcasts
        
    except Exception as e:
        logger.error(f"Error parsing championat.com UCL: {e}")
        return []

def deduplicate_broadcasts(broadcasts):
    """Remove duplicate broadcasts based on event name and time similarity"""
    if not broadcasts:
        return []
    
    def _strip_tournament_prefix(event_name: str) -> str:
        """Remove tournament prefix like 'Лига чемпионов. 1/4 финала: '"""
        # Match pattern: anything followed by colon+space, then capture the rest
        match = re.match(r'^[^:]+:\s*(.+)$', event_name)
        if match:
            return match.group(1).strip()
        return event_name
    
    def _score_broadcast(broadcast):
        """Score a broadcast based on quality criteria"""
        score = 0
        event_text = broadcast['event']
        text_lower = event_text.lower()
        
        # Приоритет 1: содержит "Прямая трансляция" или "Прямая"
        if "прямая" in text_lower:
            score += 100
        
        # Приоритет 2: extract_team_names() вернул валидные команды
        home, away = extract_team_names(event_text)
        if home and away and len(home) > 2 and len(away) > 2:
            score += 50
            # Дополнительно: чем короче название после извлечения команд — тем лучше
            clean_name = f"{home} - {away}"
            if len(clean_name) < len(event_text):
                score += 20  # предпочитаем более "чистые" названия
        
        # Приоритет 3: меньше мусорных фраз
        trash_count = sum(1 for kw in TRASH_KEYWORDS if kw.lower() in text_lower)
        score -= trash_count * 5  # штраф за мусор
        
        return score
    
    # Use fuzzy matching to identify similar events
    unique_broadcasts = []
    processed_indices = set()
    
    for i, broadcast in enumerate(broadcasts):
        if i in processed_indices:
            continue
            
        # Check for similar broadcasts
        similar_broadcasts = [broadcast]
        
        for j in range(i + 1, len(broadcasts)):
            if j in processed_indices:
                continue
                
            other_broadcast = broadcasts[j]
            
            # Check if times are close (less than 45 minutes apart)
            try:
                time1_parts = broadcast['time'].split(':')
                time2_parts = other_broadcast['time'].split(':')
                
                if len(time1_parts) == 2 and len(time2_parts) == 2:
                    hour1, minute1 = int(time1_parts[0]), int(time1_parts[1])
                    hour2, minute2 = int(time2_parts[0]), int(time2_parts[1])
                    
                    # Convert to minutes for comparison
                    total_minutes1 = hour1 * 60 + minute1
                    total_minutes2 = hour2 * 60 + minute2
                    
                    # Handle day boundary (if needed)
                    if abs(total_minutes1 - total_minutes2) > 45:
                        # Check if it's a day boundary case (e.g., 23:50 and 00:10)
                        if total_minutes1 > 23 * 60 and total_minutes2 < 1 * 60:
                            # Adjust for day boundary
                            total_minutes2 += 24 * 60
                        elif total_minutes2 > 23 * 60 and total_minutes1 < 1 * 60:
                            # Adjust for day boundary
                            total_minutes1 += 24 * 60
                            
                    time_diff = abs(total_minutes1 - total_minutes2)
                    
                    # Check if events are similar (fuzzy ratio > 60%) and time difference < 45 minutes
                    if time_diff < 45:
                        # Strip tournament prefix before extracting team names
                        clean_event1 = _strip_tournament_prefix(broadcast['event'])
                        clean_event2 = _strip_tournament_prefix(other_broadcast['event'])
                        home1, away1 = extract_team_names(clean_event1)
                        home2, away2 = extract_team_names(clean_event2)
                        
                        # If teams are extracted, compare only team names
                        if home1 and away1 and home2 and away2:
                            # Form clean names for comparison
                            clean_name1 = f"{home1} - {away1}".lower()
                            clean_name2 = f"{home2} - {away2}".lower()
                            similarity = fuzz.ratio(clean_name1, clean_name2)
                        else:
                            # Fallback: compare full names (as before)
                            similarity = fuzz.ratio(broadcast['event'], other_broadcast['event'])
                            
                        if similarity > 60:
                            similar_broadcasts.append(other_broadcast)
                            processed_indices.add(j)
            except Exception:
                # If time parsing fails, skip time comparison but still check similarity
                # Strip tournament prefix before extracting team names
                clean_event1 = _strip_tournament_prefix(broadcast['event'])
                clean_event2 = _strip_tournament_prefix(other_broadcast['event'])
                home1, away1 = extract_team_names(clean_event1)
                home2, away2 = extract_team_names(clean_event2)
                
                # If teams are extracted, compare only team names
                if home1 and away1 and home2 and away2:
                    # Form clean names for comparison
                    clean_name1 = f"{home1} - {away1}".lower()
                    clean_name2 = f"{home2} - {away2}".lower()
                    similarity = fuzz.ratio(clean_name1, clean_name2)
                else:
                    # Fallback: compare full names (as before)
                    similarity = fuzz.ratio(broadcast['event'], other_broadcast['event'])
                    
                if similarity > 60:
                    similar_broadcasts.append(other_broadcast)
                    processed_indices.add(j)
        
        # From similar broadcasts, keep the best one using the new scoring system
        best_broadcast = similar_broadcasts[0]
        best_score = _score_broadcast(best_broadcast)
        
        for similar in similar_broadcasts[1:]:
            similar_score = _score_broadcast(similar)
            if similar_score > best_score:
                best_broadcast = similar
                best_score = similar_score
                
        unique_broadcasts.append(best_broadcast)
        processed_indices.add(i)
    
    # Sort by time
    unique_broadcasts.sort(key=lambda x: x['time'])
    return unique_broadcasts

async def get_broadcasts_48h():
    """Get sports broadcasts for the next 48 hours using matchtv.ru, fight.ru, and championat.com sources"""
    logger.info("Starting 48-hour broadcast fetching")
    
    # Get current date and tomorrow's date in YYYY-MM-DD format
    current_time = get_current_time()
    today_str = current_time.strftime("%Y-%m-%d")
    tomorrow_time = current_time + timedelta(days=1)
    tomorrow_str = tomorrow_time.strftime("%Y-%m-%d")
    
    logger.info(f"Fetching data for {today_str} and {tomorrow_str}")
    
    # Fetch broadcasts from all sources for today and tomorrow
    tasks = [
        parse_matchtv_source(today_str),
        parse_fight_source(today_str),
        parse_championat_ucl_source(today_str),
        parse_matchtv_source(tomorrow_str),
        parse_fight_source(tomorrow_str),
        parse_championat_ucl_source(tomorrow_str)
    ]
    
    results = await asyncio.gather(*tasks, return_exceptions=True)
    
    # Process results and handle exceptions
    all_broadcasts = []
    source_names = ["matchtv.ru", "fight.ru", "championat.com", "matchtv.ru", "fight.ru", "championat.com"]
    date_labels = ["today", "today", "today", "tomorrow", "tomorrow", "tomorrow"]
    
    for i, result in enumerate(results):
        if isinstance(result, Exception):
            logger.error(f"Error fetching {source_names[i]} for {date_labels[i]}: {result}")
        else:
            logger.info(f"Successfully got {len(result)} broadcasts from {source_names[i]} for {date_labels[i]}")
            all_broadcasts.extend(result)
    
    # Remove duplicates
    unique_broadcasts = deduplicate_broadcasts(all_broadcasts)
    
    logger.info(f"Successfully got {len(unique_broadcasts)} unique broadcasts from all sources")
    return unique_broadcasts

def format_broadcast_message(broadcasts):
    """Format broadcasts into a message string with proper emojis and without odds"""
    if not broadcasts:
        return "<b>Трансляций не найдено</b>"
    
    try:
        # Simple HTML escape function
        def escape_html(text):
            if not text:
                return ""
            # Simple replacement for HTML escaping
            text = text.replace('&', '&')
            text = text.replace('<', '<')
            text = text.replace('>', '>')
            text = text.replace('"', '"')
            text = text.replace("'", "'")
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
            
            # For events from fight.ru (they have a 'location' field) - don't add to today/tomorrow sections
            if broadcast.get('source') == 'fight.ru':
                continue  # these events will only go to the "Предстоящие события" section
            
            # Group by actual calendar date for other sources
            # Calculate the actual calendar date based on event time
            api_date_str = broadcast.get('date', today_str)
            event_time_str = broadcast.get('time', '00:00')
            
            # Try to calculate the actual calendar date
            event_calendar_date = api_date_str  # fallback to API date
            try:
                if event_time_str != "N/A":
                    # Parse the API date
                    base_date = datetime.strptime(api_date_str, "%Y-%m-%d")
                    # Parse the time
                    hour, minute = map(int, event_time_str.split(':'))
                    # Create datetime with the API date and event time
                    event_datetime = base_date.replace(hour=hour, minute=minute, second=0, microsecond=0)
                    # For early morning events (00:00-05:59), consider them part of the next calendar day
                    # Добавляем день для ночных часов ТОЛЬКО если сайт показал "сегодня"
                    # Если сайт уже показал "завтра" — значит, он сам учёл переход через полночь
                    if 0 <= hour <= 5 and api_date_str == today_str:
                        event_datetime += timedelta(days=1)
                    # Get the actual calendar date as string
                    event_calendar_date = event_datetime.strftime("%Y-%m-%d")
            except (ValueError, TypeError) as e:
                # If parsing fails, use the API date as fallback
                event_calendar_date = api_date_str
            
            # Group by the calculated calendar date
            if event_calendar_date == today_str:
                today_broadcasts.append(broadcast)
            elif event_calendar_date == tomorrow_str:
                tomorrow_broadcasts.append(broadcast)
        
        # Format message with separate sections for today and tomorrow
        message_text = "🖥 <b>Расписание трансляций на ближайшие сутки:</b>\n\n"
        
        # Today's broadcasts
        message_text += "<b>📅 СЕГОДНЯ:</b>\n"
        if today_broadcasts:
            for broadcast in today_broadcasts:
                # Determine emoji based on sport type
                emoji = "🖥"
                if broadcast['sport'] == "Football":
                    emoji = "⚽"
                elif broadcast['sport'] == "MMA":
                    emoji = "🥊"
                
                # Escape HTML and limit length
                safe_time = escape_html(broadcast['time'])
                safe_event = escape_html(broadcast['event'])
                
                # Format as requested: ⏰ 13:40 | ⚽️ Футбол: Крылья Советов - Ахмат
                event_line = f"⏰ {safe_time} | {emoji} <b>{broadcast['sport']}</b>: {safe_event}"

                # Add ❗️ if it's a "Прямая трансляция"
                if "прямая трансляция" in broadcast['event'].lower() or "прямая" in broadcast['event'].lower():
                    event_line += " ❗️"

                message_text += event_line + "\n"
                
                # Add source information
                source_name = broadcast.get('source', 'Unknown')
                if source_name == "matchtv.ru":
                    source_text = "MatchTV"
                    source_link = "https://matchtv.ru/on-air"
                else:
                    source_text = source_name
                    source_link = f"https://www.google.com/search?q={source_name}"
                message_text += f"📡 <b>Источник:</b> <a href='{source_link}'>{source_text}</a>\n\n"
        else:
            message_text += "<i>Трансляций не найдено</i>\n\n"
        
        # Tomorrow's broadcasts
        message_text += "<b>📅 ЗАВТРА:</b>\n"
        if tomorrow_broadcasts:
            for broadcast in tomorrow_broadcasts:
                # Determine emoji based on sport type
                emoji = "🖥"
                if broadcast['sport'] == "Football":
                    emoji = "⚽"
                elif broadcast['sport'] == "MMA":
                    emoji = "🥊"
                
                # Escape HTML and limit length
                safe_time = escape_html(broadcast['time'])
                safe_event = escape_html(broadcast['event'])
                
                # Format as requested: ⏰ 13:40 | ⚽️ Футбол: Крылья Советов - Ахмат
                event_line = f"⏰ {safe_time} | {emoji} <b>{broadcast['sport']}</b>: {safe_event}"

                # Add ❗️ if it's a "Прямая трансляция"
                if "прямая трансляция" in broadcast['event'].lower() or "прямая" in broadcast['event'].lower():
                    event_line += " ❗️"

                message_text += event_line + "\n"
                
                # Add source information
                source_name = broadcast.get('source', 'Unknown')
                if source_name == "matchtv.ru":
                    source_text = "MatchTV"
                    source_link = "https://matchtv.ru/on-air"
                else:
                    source_text = source_name
                    source_link = f"https://www.google.com/search?q={source_name}"
                message_text += f"📡 <b>Источник:</b> <a href='{source_link}'>{source_text}</a>\n\n"
        else:
            message_text += "<i>Трансляций не найдено</i>\n\n"
        
        # Add upcoming MMA events block
        # Filter upcoming events (those with location field, which indicates they're from fight.ru schedule)
        upcoming_events = [b for b in broadcasts if 'location' in b and b['location']]
        if upcoming_events:
            message_text += "🔮 <b>Предстоящие MMA события:</b>\n"
            for event in upcoming_events:
                # Format date
                event_date = event.get('date', 'Дата не указана')
                # Get clean event name (without any location that might be in the event text)
                event_name = event['event'].split('\n')[0].strip()
                # Use date_display for fight.ru events (original format DD.MM.YYYY)
                event_date_display = event.get('date_display', event.get('date_iso', event_date))
                if event_date_display:
                    message_text += f"🥊 {event_date_display} {event['time']} | {event_name}\n"
                    # Add location if available
                    if event['location']:
                        message_text += f"📍 {event['location']}\n"
                else:
                    message_text += f"🥊 {event['time']} | {event_name}\n"
                    # Add location if available
                    if event['location']:
                        message_text += f"📍 {event['location']}\n"
                message_text += "📡 <i>Источник: fight.ru</i>\n\n"
        
        return message_text
    except Exception as e:
        logger.error(f"Error formatting broadcast message: {e}")
        # Return a simple message even if formatting fails
        return f"🖥 Найдено {len(broadcasts)} трансляций. Подробности смотрите на сайте."
    