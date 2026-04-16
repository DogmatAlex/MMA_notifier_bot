import logging
import re
import cloudscraper
import asyncio
from bs4 import BeautifulSoup
from datetime import timedelta
from parser import (
    clean_event_title, extract_team_names, get_current_time,
    is_future_event, deduplicate_broadcasts,
    parse_matchtv_source, parse_fight_source, logger
)

# Configure logging
odds_logger = logging.getLogger('odds_parser')

# Keywords to exclude for cyberfootball
EXCLUDE_KEYWORDS = ["кибер", "cyber", "esports", "virtual", "fifa", "pes", "e-football"]

async def parse_betcity_live():
    """
    Parse live football matches with odds from betcity.ru
    Returns: list of broadcasts with odds
    """
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
        
        odds_logger.info("Attempting to fetch data from betcity.ru/live")
        
        # Fetch the live page with a timeout of 10 seconds
        response = scraper.get("https://betcity.ru/ru/live", headers=headers, timeout=10)
        
        if response.status_code != 200:
            odds_logger.warning(f"Failed to fetch https://betcity.ru/ru/live, status code: {response.status_code}")
            return []
        
        # Debug: save first 2000 characters of response for analysis
        sample = response.text[:2000].replace('\n', ' ')
        odds_logger.info(f"DEBUG: Response preview: {sample}")
        
        # Check if "Фактический исход" exists in the response
        if 'Фактический исход' not in response.text:
            odds_logger.warning("WARNING: 'Фактический исход' not found in page source!")
        
        # Parse the HTML content
        soup = BeautifulSoup(response.content, 'html.parser')
        
        broadcasts = []
        
        # Get current time for filtering
        current_time = get_current_time()
        
        # Find all blocks with "Фактический исход" (using fuzzy matching)
        market_headers = soup.find_all('span', string=lambda text: text and 'Фактический исход' in text)
        
        odds_logger.info(f"Found {len(market_headers)} 'Фактический исход' blocks")
        
        for market_header in market_headers:
            try:
                # Find the parent match container
                match_container = market_header.find_parent('div', class_=re.compile(r'match|event|row', re.I))
                
                if not match_container:
                    continue
                
                # Extract tournament and team names
                # Look for elements containing team names
                team_elements = match_container.find_all(['div', 'span'], class_=re.compile(r'team|name|title', re.I))
                
                if len(team_elements) < 2:
                    continue
                
                # Get the first two team elements as home and away teams
                home_team_elem = team_elements[0]
                away_team_elem = team_elements[1]
                
                home_team = home_team_elem.get_text(strip=True)
                away_team = away_team_elem.get_text(strip=True)
                
                if not home_team or not away_team:
                    continue
                
                # Create event title
                event_title = f"{home_team} - {away_team}"
                
                # Check for exclude keywords (cyberfootball filter)
                if any(kw in event_title.lower() for kw in EXCLUDE_KEYWORDS):
                    odds_logger.info(f"Skipping cyberfootball match: {event_title}")
                    continue
                
                # Extract tournament name if available
                tournament_elem = match_container.find(['div', 'span'], class_=re.compile(r'tournament|league', re.I))
                tournament_name = tournament_elem.get_text(strip=True) if tournament_elem else ""
                
                # Create full event name with tournament
                if tournament_name:
                    full_event = f"{tournament_name}: {event_title}"
                else:
                    full_event = event_title
                
                # Extract time (default to "LIVE" for live matches)
                time_str = "LIVE"
                
                # Look for time elements
                time_elem = match_container.find(['div', 'span'], class_=re.compile(r'time', re.I))
                if time_elem:
                    time_text = time_elem.get_text(strip=True)
                    # If we find a time pattern, use it
                    time_match = re.search(r'(\d{1,2}:\d{2})', time_text)
                    if time_match:
                        time_str = time_match.group(1)
                
                # Extract odds
                home_odds = None
                draw_odds = None
                away_odds = None
                
                # Find all outcome labels and odds buttons
                outcomes = match_container.find_all('span', class_='dops-item-row__block-left')
                odds_buttons = match_container.find_all('button', class_='dops-item-row__block-right')
                
                # Match outcomes with odds by index
                for i, outcome in enumerate(outcomes):
                    label = outcome.get_text(strip=True)
                    if i < len(odds_buttons):
                        odds_value = odds_buttons[i].get_text(strip=True)
                        try:
                            odds_float = float(odds_value.replace(',', '.'))
                            if label == '1':
                                home_odds = odds_float
                            elif label.upper() == 'X':
                                draw_odds = odds_float
                            elif label == '2':
                                away_odds = odds_float
                        except ValueError:
                            odds_logger.warning(f"Could not parse odds value: {odds_value}")
                
                # Skip if we don't have both home and away odds
                if not home_odds or not away_odds:
                    odds_logger.warning(f"Missing odds for match: {full_event}")
                    continue
                
                # Format odds string
                if draw_odds:
                    odds_str = f"📊 П1: {home_odds} | Х: {draw_odds} | П2: {away_odds}"
                else:
                    odds_str = f"📊 П1: {home_odds} | П2: {away_odds}"
                
                # Create broadcast entry
                broadcast = {
                    "time": time_str,
                    "sport": "Football",
                    "event": full_event,
                    "odds": odds_str,
                    "odds_source": "betcity.ru",
                    "link": "https://betcity.ru/ru/live"
                }
                
                broadcasts.append(broadcast)
                odds_logger.info(f"Found broadcast: {time_str} - Football - {full_event}")
                
            except Exception as e:
                odds_logger.warning(f"Error processing match container: {e}")
                continue
        
        odds_logger.info(f"Successfully parsed {len(broadcasts)} broadcasts from betcity.ru")
        return broadcasts
            
    except asyncio.TimeoutError:
        odds_logger.warning("Timeout while fetching data from betcity.ru")
        return []
    except Exception as e:
        odds_logger.error(f"Error parsing betcity.ru: {e}")
        return []

async def get_odds_broadcasts():
    """Get broadcasts with odds from betcity.ru only"""
    odds_logger.info("Starting odds broadcast fetching from betcity.ru only")
    
    try:
        # Get live matches from betcity.ru
        live_broadcasts = await parse_betcity_live()
        
        # Filter out broadcasts without odds
        broadcasts_with_odds = [b for b in live_broadcasts if 'odds' in b and b['odds']]
        
        odds_logger.info(f"Successfully got {len(broadcasts_with_odds)} broadcasts with odds from betcity.ru")
        return broadcasts_with_odds
        
    except Exception as e:
        odds_logger.error(f"Error in get_odds_broadcasts: {e}")
        return []

def format_odds_message(broadcasts):
    """Format odds message with new design"""
    if not broadcasts:
        return "📊 <b>Коэффициентов не найдено</b>"
    
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
        
        # Filter broadcasts that have odds
        broadcasts_with_odds = [b for b in broadcasts if 'odds' in b and b['odds']]
        
        if not broadcasts_with_odds:
            return "📊 <b>Коэффициентов не найдено</b>"
        
        # Group broadcasts by date (for live, we'll put them all under TODAY)
        today_broadcasts = []
        tomorrow_broadcasts = []
        
        current_time = get_current_time()
        today_str = current_time.strftime("%Y-%m-%d")
        tomorrow_time = current_time + timedelta(days=1)
        tomorrow_str = tomorrow_time.strftime("%Y-%m-%d")
        
        # For live broadcasts, put them all under TODAY
        today_broadcasts = broadcasts_with_odds
        
        # Format message with separate sections for today and tomorrow
        message_text = "📊 <b>Коэффициенты на ближайшие сутки:</b>\n\n"
        
        # Today's broadcasts
        message_text += "📅 <b>СЕГОДНЯ:</b>\n"
        if today_broadcasts:
            for broadcast in today_broadcasts:
                # Clean the event title
                broadcast['event'] = clean_event_title(broadcast['event'])
                
                # Determine emoji based on sport type
                emoji = "⚽"
                
                # Extract clean team names
                home_team, away_team = extract_team_names(broadcast['event'])
                if home_team and away_team:
                    teams_text = f"{home_team} - {away_team}"
                else:
                    teams_text = broadcast['event']
                
                # Escape HTML and limit length
                safe_time = escape_html(broadcast['time'])
                safe_teams = escape_html(teams_text)
                
                # Format as requested
                message_text += f"⏰ {safe_time} | {emoji} <b>Football</b>: {safe_teams}\n"
                message_text += "Фактический исход:\n"
                
                # Add odds
                if 'odds' in broadcast and broadcast['odds']:
                    safe_odds = escape_html(broadcast['odds'])
                    # Extract just the odds part (remove "📊 ")
                    odds_text = safe_odds.replace("📊 ", "")
                    message_text += f"📊 {odds_text} 📡 <small>betcity.ru</small>\n\n"
                else:
                    # Show message when odds are not available
                    message_text += "⚠️ Коэффициенты временно недоступны\n\n"
        else:
            message_text += "<i>Коэффициентов не найдено</i>\n\n"
        
        # Tomorrow's broadcasts (empty for live odds)
        message_text += "📅 <b>ЗАВТРА:</b>\n"
        message_text += "<i>Коэффициентов не найдено</i>\n\n"
        
        return message_text
    except Exception as e:
        odds_logger.error(f"Error formatting odds message: {e}")
        # Return a simple message even if formatting fails
        return f"📊 Найдено {len([b for b in broadcasts if 'odds' in b and b['odds']])} коэффициентов."