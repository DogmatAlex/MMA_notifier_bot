import logging
import re
import json
import cloudscraper
import asyncio
import aiohttp
from datetime import timedelta
from bs4 import BeautifulSoup
from fuzzywuzzy import fuzz
from config import ODDS_API_KEY
from parser import (
    clean_event_title, extract_team_names, get_current_time,
    is_future_event, deduplicate_broadcasts,
    parse_matchtv_source, parse_fight_source, logger
)

# Configure logging
odds_logger = logging.getLogger('odds_parser')

async def get_odds(home_team, away_team):
    """Get odds for a match from The Odds API"""
    # If team names are None, don't even try to make the request
    if not home_team or not away_team:
        return None
        
    if not ODDS_API_KEY:
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
            async with session.get(url, params=params, timeout=7) as response:
                if response.status == 429:
                    # Rate limit reached, just return None without logging
                    return None
                    
                if response.status != 200:
                    # API error, just return None without logging
                    return None
                    
                data = await response.json()
                
                # Check if we have data
                if not data:
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
        odds_logger.error(f"Error getting odds for {home_team} vs {away_team}: {e}")
        return None

async def search_championat_match(home_team: str, away_team: str) -> str | None:
    """
    Search for a match on championat.com by team names
    Returns: match URL if found, None otherwise
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
        
        # Create search query with just team names
        search_query = f"{home_team} {away_team}".replace(" ", "+")
        search_url = f"https://www.championat.com/search/?q={search_query}"
        
        odds_logger.info(f"Searching for match on championat.com: {home_team} vs {away_team}")
        odds_logger.info(f"Search URL: {search_url}")
        
        # Fetch the search results page with a timeout of 7 seconds
        response = scraper.get(search_url, headers=headers, timeout=7)
        
        if response.status_code != 200:
            odds_logger.warning(f"Failed to fetch search results from championat.com, status code: {response.status_code}")
            return None
        
        # Parse the HTML content
        soup = BeautifulSoup(response.content, 'html.parser')
        
        # Look for search results
        search_results = soup.find_all(['div', 'a'], class_=re.compile(r'search|result|item', re.I))
        
        # If no results found with class search, try other selectors
        if not search_results:
            search_results = soup.find_all('a', href=re.compile(r'/football/|/mma/|/boxing/'))
        
        # Look for match links in search results
        for result in search_results:
            # Get the link
            link = result.get('href') if result.name == 'a' else result.find('a')
            if link:
                href = link.get('href') if hasattr(link, 'get') else link
                if href and re.match(r'/football/.*match/|/mma/.*match/|/boxing/.*match/', href):
                    # Found a match link
                    full_url = f"https://www.championat.com{href}" if href.startswith('/') else href
                    odds_logger.info(f"Found potential match URL: {full_url}")
                    return full_url
                
                # Also check the text content for team names
                result_text = result.get_text(strip=True).lower()
                if home_team.lower() in result_text and away_team.lower() in result_text:
                    # This result contains both team names
                    href = result.get('href') if result.name == 'a' else None
                    if href:
                        full_url = f"https://www.championat.com{href}" if href.startswith('/') else href
                        odds_logger.info(f"Found potential match URL by team names: {full_url}")
                        return full_url
        
        odds_logger.info("No match found on championat.com")
        return None
                
    except asyncio.TimeoutError:
        odds_logger.warning(f"Timeout while searching for match on championat.com: {home_team} vs {away_team}")
        return None
    except Exception as e:
        odds_logger.error(f"Error searching for match on championat.com {home_team} vs {away_team}: {e}")
        return None


async def parse_championat_odds(match_url: str) -> dict | None:
    """
    Parse odds from individual match page on championat.com
    URL pattern: /{sport}/.../match/{match_id}/#stats
    Returns: {'P1': float, 'X': float|None, 'P2': float, 'source': 'championat.com'}
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
        
        odds_logger.info(f"Attempting to fetch odds from championat.com: {match_url}")
        
        # Fetch the match page with a timeout of 7 seconds
        response = scraper.get(match_url, headers=headers, timeout=7)
        
        if response.status_code != 200:
            odds_logger.warning(f"Failed to fetch {match_url}, status code: {response.status_code}")
            return None
        
        # Parse the HTML content
        soup = BeautifulSoup(response.content, 'html.parser')
        
        # Look for odds in various possible locations
        odds_data = {}
        
        # Try to find JSON-LD data first
        json_scripts = soup.find_all('script', type='application/ld+json')
        for script in json_scripts:
            try:
                json_data = json.loads(script.string)
                # Check if this contains betting data
                if isinstance(json_data, dict) and 'offers' in json_data:
                    # Extract odds from offers
                    offers = json_data.get('offers', [])
                    if offers and isinstance(offers, list):
                        for offer in offers:
                            if isinstance(offer, dict) and 'price' in offer:
                                # This is a simplified approach - in reality, we'd need to map
                                # the offer to P1/X/P2 based on additional data
                                pass
            except (json.JSONDecodeError, TypeError):
                continue
        
        # Look for odds in specific HTML elements
        odds_containers = soup.find_all(['div', 'span', 'section'], class_=re.compile(r'match-bets|bet-item|odds|betting', re.I))
        if not odds_containers:
            # Try alternative selectors
            odds_containers = soup.find_all(attrs={'data-bet-type': re.compile(r'1x2|match-result', re.I)})
        
        # Process each container looking for odds
        p1_odds = None
        x_odds = None
        p2_odds = None
        
        for container in odds_containers:
            # Look for text patterns that might contain odds
            container_text = container.get_text(strip=True)
            
            # Pattern for decimal odds: P1: 2.45 | X: 3.20 | P2: 2.90
            decimal_pattern = re.compile(r'[PП]1[:\s]*([\d.,]+).*?[XХ][:]?\s*([\d.,]+).*?[PП]2[:\s]*([\d.,]+)', re.DOTALL | re.IGNORECASE)
            decimal_match = decimal_pattern.search(container_text)
            
            if decimal_match:
                try:
                    p1_odds = float(decimal_match.group(1).replace(',', '.'))
                    x_odds = float(decimal_match.group(2).replace(',', '.'))
                    p2_odds = float(decimal_match.group(3).replace(',', '.'))
                    break  # Found what we're looking for
                except ValueError:
                    pass
            
            # Pattern for percentage odds: 24% | 18% | 58% (convert to decimal: 100/percentage)
            percent_pattern = re.compile(r'(\d+)%.*?(\d+)%.*?(\d+)%', re.DOTALL)
            percent_match = percent_pattern.search(container_text)
            
            if percent_match:
                try:
                    p1_pct = int(percent_match.group(1))
                    x_pct = int(percent_match.group(2))
                    p2_pct = int(percent_match.group(3))
                    
                    # Convert percentages to decimal odds (100/percentage)
                    if p1_pct > 0:
                        p1_odds = round(100 / p1_pct, 2)
                    if x_pct > 0:
                        x_odds = round(100 / x_pct, 2)
                    if p2_pct > 0:
                        p2_odds = round(100 / p2_pct, 2)
                    break  # Found what we're looking for
                except (ValueError, ZeroDivisionError):
                    pass
        
        # If we still haven't found odds, look for individual elements
        if not p1_odds or not x_odds or not p2_odds:
            # Look for individual odds elements
            odds_elements = soup.find_all(['span', 'div'], class_=re.compile(r'odds|coef|bet-odds', re.I))
            for elem in odds_elements:
                elem_text = elem.get_text(strip=True)
                # Look for decimal numbers that might be odds
                odds_numbers = re.findall(r'\b\d+[.,]?\d*\b', elem_text)
                # If we find 3 numbers, assume they are P1, X, P2 odds
                if len(odds_numbers) >= 3:
                    try:
                        p1_odds = float(odds_numbers[0].replace(',', '.'))
                        x_odds = float(odds_numbers[1].replace(',', '.'))
                        p2_odds = float(odds_numbers[2].replace(',', '.'))
                        break
                    except (ValueError, IndexError):
                        continue
        
        # If we found odds, return them
        if p1_odds or p2_odds:  # At minimum we need P1 and P2 odds
            odds_data = {
                'P1': p1_odds,
                'X': x_odds,  # This can be None
                'P2': p2_odds,
                'source': 'championat.com'
            }
            odds_logger.info(f"Successfully parsed odds from championat.com: {odds_data}")
            return odds_data
        else:
            odds_logger.info("No odds found on championat.com page")
            return None
                
    except asyncio.TimeoutError:
        odds_logger.warning(f"Timeout while fetching odds from championat.com: {match_url}")
        return None
    except Exception as e:
        odds_logger.error(f"Error parsing odds from championat.com {match_url}: {e}")
        return None

async def get_odds_broadcasts():
    """Get sports broadcasts for the next 48 hours with odds"""
    odds_logger.info("Starting 48-hour broadcast fetching for odds")
    
    # Get current date and tomorrow's date in YYYY-MM-DD format
    current_time = get_current_time()
    today_str = current_time.strftime("%Y-%m-%d")
    tomorrow_time = current_time + timedelta(days=1)
    tomorrow_str = tomorrow_time.strftime("%Y-%m-%d")
    
    odds_logger.info(f"Fetching data for {today_str} and {tomorrow_str}")
    
    # Define sources for odds (all sources)
    sources = [
        ("matchtv.ru", parse_matchtv_source),
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
            odds_logger.error(f"Error with source {source_name} for today: {result}")
        elif result is not None:
            odds_logger.info(f"Successfully got {len(result)} broadcasts from {source_name} for today")
            # Add date information to each broadcast
            for broadcast in result:
                broadcast['date'] = today_str
            all_broadcasts.extend(result)
    
    # Process tomorrow's results
    for i, result in enumerate(tomorrow_results):
        source_name = sources[i][0]
        if isinstance(result, Exception):
            odds_logger.error(f"Error with source {source_name} for tomorrow: {result}")
        elif result is not None:
            odds_logger.info(f"Successfully got {len(result)} broadcasts from {source_name} for tomorrow")
            # Add date information to each broadcast
            for broadcast in result:
                broadcast['date'] = tomorrow_str
            all_broadcasts.extend(result)
    
    # Remove duplicates
    unique_broadcasts = deduplicate_broadcasts(all_broadcasts)
    
    # Get odds for each unique broadcast
    # Only try to get odds for events that likely have them (UFC, "against", or contain "-")
    for broadcast in unique_broadcasts:
        event_title = broadcast['event'].lower()
        if "ufc" in event_title or "против" in event_title or " - " in broadcast['event']:
            home_team, away_team = extract_team_names(broadcast['event'])
            if home_team and away_team:
                # Try to get odds from championat.com first
                odds = None
                odds_source = None
                
                # Search for match on championat.com by team names
                odds_logger.info(f"Searching for match on championat.com: {home_team} vs {away_team}")
                # Clean team names for search
                clean_home = re.sub(r'[^\w\s\-]', '', home_team).strip()
                clean_away = re.sub(r'[^\w\s\-]', '', away_team).strip()
                match_url = await search_championat_match(clean_home, clean_away)
                
                if match_url:
                    # Try to get odds from championat.com match page
                    championat_odds = await parse_championat_odds(match_url)
                    if championat_odds:
                        # Format odds for display
                        p1 = championat_odds.get('P1')
                        x = championat_odds.get('X')
                        p2 = championat_odds.get('P2')
                        
                        if p1 and p2:
                            if x:
                                odds = f"📊 Коэффициенты: П1: {p1} | Х: {x} | П2: {p2}"
                            else:
                                odds = f"📊 Коэффициенты: П1: {p1} | П2: {p2}"
                            odds_source = "championat.com"
                    else:
                        odds_logger.warning(f"Odds not found on championat.com page: {match_url}")
                else:
                    odds_logger.info(f"Match not found on championat.com for: {home_team} vs {away_team}")
                
                # Fallback to The Odds API if championat.com didn't work
                if not odds:
                    odds = await get_odds(home_team, away_team)
                    if odds:
                        odds_source = "The-Odds-API"
                
                # Add odds to broadcast if found
                if odds:
                    broadcast['odds'] = odds
                    broadcast['odds_source'] = odds_source
    
    odds_logger.info(f"Successfully got {len(unique_broadcasts)} unique broadcasts from all sources")
    return unique_broadcasts

def format_odds_message(broadcasts):
    """Format broadcasts into an odds-only message string for bettors"""
    if not broadcasts:
        return "<b>Коэффициентов не найдено</b>"
    
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
            return "<b>Коэффициентов не найдено</b>"
        
        # Group broadcasts by date
        today_broadcasts = []
        tomorrow_broadcasts = []
        
        current_time = get_current_time()
        today_str = current_time.strftime("%Y-%m-%d")
        tomorrow_time = current_time + timedelta(days=1)
        tomorrow_str = tomorrow_time.strftime("%Y-%m-%d")
        
        for broadcast in broadcasts_with_odds:
            # Clean the event title
            broadcast['event'] = clean_event_title(broadcast['event'])
            
            # Group by date
            broadcast_date = broadcast.get('date', today_str)
            if broadcast_date == today_str:
                today_broadcasts.append(broadcast)
            elif broadcast_date == tomorrow_str:
                tomorrow_broadcasts.append(broadcast)
        
        # Format message with separate sections for today and tomorrow
        message_text = "📊 <b>Коэффициенты на ближайшие сутки:</b>\n\n"
        
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
                
                # Extract clean team names
                home_team, away_team = extract_team_names(broadcast['event'])
                if home_team and away_team:
                    teams_text = f"{home_team} - {away_team}"
                else:
                    teams_text = broadcast['event']
                
                # Escape HTML and limit length
                safe_time = escape_html(broadcast['time'])
                safe_teams = escape_html(teams_text)
                
                # Format as requested: ⏰ 13:40 | ⚽️ Футбол: Крылья Советов - Ахмат
                message_text += f"⏰ {safe_time} | {emoji} <b>{broadcast['sport']}</b>: {safe_teams}\n"
                
                # Add odds
                if 'odds' in broadcast and broadcast['odds']:
                    safe_odds = escape_html(broadcast['odds'])
                    # Extract just the odds part (remove "📊 Коэффициенты: ")
                    odds_text = safe_odds.replace("📊 Коэффициенты: ", "")
                    message_text += f"{odds_text}"
                    # Add source information
                    odds_source = broadcast.get('odds_source', 'Unknown')
                    if odds_source and odds_source != "championat.com":
                        message_text += " 📡 <small>другой источник</small>"
                    elif odds_source == "championat.com":
                        message_text += " 📡 <small>championat.com</small>"
                    message_text += "\n\n"
                else:
                    # Show message when odds are not available
                    message_text += "⚠️ Коэффициенты для этого матча временно недоступны.\n\n"
        else:
            message_text += "<i>Коэффициентов не найдено</i>\n\n"
        
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
                
                # Extract clean team names
                home_team, away_team = extract_team_names(broadcast['event'])
                if home_team and away_team:
                    teams_text = f"{home_team} - {away_team}"
                else:
                    teams_text = broadcast['event']
                
                # Escape HTML and limit length
                safe_time = escape_html(broadcast['time'])
                safe_teams = escape_html(teams_text)
                
                # Format as requested: ⏰ 13:40 | ⚽️ Футбол: Крылья Советов - Ахмат
                message_text += f"⏰ {safe_time} | {emoji} <b>{broadcast['sport']}</b>: {safe_teams}\n"
                
                # Add odds
                if 'odds' in broadcast and broadcast['odds']:
                    safe_odds = escape_html(broadcast['odds'])
                    # Extract just the odds part (remove "📊 Коэффициенты: ")
                    odds_text = safe_odds.replace("📊 Коэффициенты: ", "")
                    message_text += f"{odds_text}"
                    # Add source information
                    odds_source = broadcast.get('odds_source', 'Unknown')
                    if odds_source and odds_source != "championat.com":
                        message_text += " 📡 <small>другой источник</small>"
                    elif odds_source == "championat.com":
                        message_text += " 📡 <small>championat.com</small>"
                    message_text += "\n\n"
                else:
                    # Show message when odds are not available
                    message_text += "⚠️ Коэффициенты для этого матча временно недоступны.\n\n"
        else:
            message_text += "<i>Коэффициентов не найдено</i>\n\n"
        
        return message_text
    except Exception as e:
        odds_logger.error(f"Error formatting odds message: {e}")
        # Return a simple message even if formatting fails
        return f"📊 Найдено {len([b for b in broadcasts if 'odds' in b and b['odds']])} коэффициентов."

# Import timedelta for date calculations
from datetime import timedelta