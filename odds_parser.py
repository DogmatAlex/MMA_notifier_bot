import logging
import re
import asyncio
import aiohttp
from datetime import timedelta
from parser import (
    clean_event_title, extract_team_names, get_current_time,
    is_future_event, deduplicate_broadcasts,
    parse_matchtv_source, parse_fight_source, logger
)
from config import ODDS_API_KEY

# Configure logging
odds_logger = logging.getLogger('odds_parser')

# Keywords to exclude for cyberfootball
EXCLUDE_KEYWORDS = ["кибер", "cyber", "esports", "virtual", "fifa", "pes", "e-football", "pes"]

# For testing purposes
TESTING = False

async def parse_betcity_api():
    """
    Parse live football matches with odds from Betcity API
    Returns: list of broadcasts with odds
    """
    # Mock data for testing
    if TESTING:
        odds_logger.info("Using mock data for testing")
        return [
            {
                "time": "22:00",
                "sport": "Football",
                "event": "Англия. Премьер-лига: Арсенал - Манчестер Сити",
                "odds": "📊 П1: 2.10 | Х: 3.40 | П2: 3.20",
                "odds_source": "betcity.ru",
                "link": "https://betcity.ru/ru/live/event/123456"
            },
            {
                "time": "LIVE",
                "sport": "Football",
                "event": "Испания. Ла Лига: Барселона - Реал Мадрид",
                "odds": "📊 П1: 1.80 | Х: 3.60 | П2: 4.20",
                "odds_source": "betcity.ru",
                "link": "https://betcity.ru/ru/live/event/123457"
            }
        ]
    
    try:
        # Use aiohttp for async requests
        async with aiohttp.ClientSession() as session:
            # Betcity API endpoints
            events_url = "https://ad.betcity.ru/d/on_air/events?rev=5&ver=69&csn=ooca9s"
            bets_url = "https://ad.betcity.ru/d/on_air/bets?rev=8&add=dep_event&ver=69&csn=ooca9s"
            
            # Headers for API request
            headers = {
                'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0.0.0 Safari/537.36',
                'Referer': 'https://betcity.ru/',
                'Origin': 'https://betcity.ru',
                'Accept': 'application/json',
            }
            
            odds_logger.info("Attempting to fetch data from Betcity Events API")
            
            # Fetch events data from Betcity API with a timeout of 7 seconds
            async with session.get(events_url, headers=headers, timeout=7) as response:
                if response.status != 200:
                    odds_logger.warning(f"Failed to fetch Betcity Events API, status code: {response.status}")
                    return []
                
                events_data = await response.json()
                
            odds_logger.info("Attempting to fetch data from Betcity Bets API")
            
            # Fetch bets data from Betcity API with a timeout of 7 seconds
            async with session.get(bets_url, headers=headers, timeout=7) as response:
                if response.status != 200:
                    odds_logger.warning(f"Failed to fetch Betcity Bets API, status code: {response.status}")
                    return []
                
                bets_data = await response.json()
                
            broadcasts = []
            
            # Process sports from Events API response
            sports = events_data.get('reply', {}).get('sports', {})
            odds_logger.info(f"Found {len(sports)} sports in Betcity Events API response")
            
            # Create a lookup for bets data by event_id
            bets_lookup = {}
            bets_sports = bets_data.get('reply', {}).get('sports', {})
            for sport_id, sport_data in bets_sports.items():
                chmps = sport_data.get('chmps', {})
                for chmp_id, chmp_data in chmps.items():
                    evts = chmp_data.get('evts', {})
                    for event_id, event_bets_data in evts.items():
                        bets_lookup[event_id] = event_bets_data
            
            for sport_id, sport_data in sports.items():
                try:
                    # Only football events (sport_id = "1" as string)
                    if sport_id != "1":
                        continue
                    
                    sport_name = sport_data.get('name_sp', '')
                    chmps = sport_data.get('chmps', {})
                    
                    for chmp_id, chmp_data in chmps.items():
                        # Exclude cyberfootball
                        is_cyber = chmp_data.get('is_cyber', 0)
                        if is_cyber == 1:
                            continue
                        
                        league_name = chmp_data.get('name_ch', '')
                        # Additional check for cyberfootball keywords
                        if any(kw in league_name.lower() for kw in EXCLUDE_KEYWORDS):
                            continue
                        
                        evts = chmp_data.get('evts', {})
                        for event_id, event in evts.items():
                            try:
                                # Exclude esports
                                is_esports = event.get('is_esports', 0)
                                if is_esports == 1:
                                    continue
                                
                                # Extract teams
                                home_team = event.get('name_ht', '')
                                away_team = event.get('name_at', '')
                                
                                if not home_team or not away_team:
                                    continue
                                
                                # Create event title
                                event_title = f"{home_team} - {away_team}"
                                
                                # Create full event name with tournament
                                full_event = f"{league_name}: {event_title}"
                                
                                # Extract time
                                is_online = event.get('is_online', 0)
                                time_str = "LIVE" if is_online == 1 else "UPCOMING"
                                
                                # Extract odds for "Фактический исход" (1X2 market)
                                home_odds = None
                                draw_odds = None
                                away_odds = None
                                
                                # Look for odds data for this event
                                event_bets_data = bets_lookup.get(event_id, {})
                                
                                # Check if we have odds data for this event
                                if event_bets_data:
                                    # Look for the "Wm" block which contains the "Фактический исход" market
                                    # The structure is: event_bets_data -> "main" -> "69" -> "data" -> event_id -> "blocks" -> "Wm" -> {P1, X, P2} -> "kf"
                                    main_market = event_bets_data.get('main', {})
                                    fact_outcome_market = main_market.get('69', {})  # 69 is "Фактический исход"
                                    market_data = fact_outcome_market.get('data', {})
                                    event_data = market_data.get(event_id, {})
                                    blocks = event_data.get('blocks', {})
                                    wm_block = blocks.get('Wm', {})
                                    
                                    if wm_block:
                                        # Extract odds for each outcome
                                        p1_data = wm_block.get('P1', {})
                                        x_data = wm_block.get('X', {})
                                        p2_data = wm_block.get('P2', {})
                                        
                                        # Get the odds values (kf = коэффициент)
                                        home_odds = p1_data.get('kf')
                                        draw_odds = x_data.get('kf')
                                        away_odds = p2_data.get('kf')
                                
                                # Skip if we don't have odds
                                if home_odds is None or draw_odds is None or away_odds is None:
                                    odds_logger.warning(f"Missing odds for match: {full_event}")
                                    continue
                                
                                # Validate that odds are numbers
                                try:
                                    home_odds = float(home_odds)
                                    draw_odds = float(draw_odds)
                                    away_odds = float(away_odds)
                                except (ValueError, TypeError):
                                    odds_logger.warning(f"Invalid odds values for match: {full_event}")
                                    continue
                                
                                # Format odds string
                                odds_str = f"П1: {home_odds:.2f} | Х: {draw_odds:.2f} | П2: {away_odds:.2f}"
                                
                                # Create match link
                                link = f"https://betcity.ru/ru/live/event/{event_id}"
                                
                                # Create broadcast entry
                                broadcast = {
                                    "time": time_str,
                                    "sport": "Football",
                                    "event": full_event,
                                    "odds": f"📊 {odds_str}",
                                    "odds_source": "betcity.ru",
                                    "link": link
                                }
                                
                                broadcasts.append(broadcast)
                                odds_logger.info(f"Found broadcast: {time_str} - Football - {full_event}")
                                
                            except Exception as e:
                                odds_logger.warning(f"Error processing event {event_id}: {e}")
                                continue
                    
                except Exception as e:
                    odds_logger.warning(f"Error processing sport {sport_id}: {e}")
                    continue
            
            odds_logger.info(f"Successfully parsed {len(broadcasts)} broadcasts from Betcity API")
            return broadcasts
            
    except (aiohttp.ClientError, asyncio.TimeoutError) as e:
        odds_logger.warning(f"Betcity API unavailable: {e}")
        return []
    except Exception as e:
        odds_logger.error(f"Error parsing Betcity API: {e}")
        return []

async def get_odds_from_the_odds_api(home_team, away_team):
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
                    from fuzzywuzzy import fuzz
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
                                        best_odds = f"📊 П1: {home_price} | Х: {draw_price} | П2: {away_price}"
                                    else:
                                        best_odds = f"📊 П1: {home_price} | П2: {away_price}"
                
                return best_odds
                
    except Exception as e:
        odds_logger.error(f"Error getting odds for {home_team} vs {away_team}: {e}")
        return None

async def get_odds_broadcasts():
    """Get broadcasts with odds from Betcity API with fallback to The Odds API"""
    odds_logger.info("Starting odds broadcast fetching with Betcity API as primary source")
    
    try:
        # Try to get live matches from Betcity API
        live_broadcasts = await parse_betcity_api()
        
        # If Betcity API returned data, use it
        if live_broadcasts:
            odds_logger.info(f"Successfully got {len(live_broadcasts)} broadcasts from Betcity API")
            return live_broadcasts
        
        # If Betcity API failed or returned no data, try fallback to The Odds API
        odds_logger.info("Betcity API returned no data, trying fallback to The Odds API")
        
        # For fallback, we would need to get events from some source
        # Since we don't have access to the original source of events for The Odds API,
        # we'll return empty list for now
        # In a real implementation, we would get events from another source and then
        # try to match them with The Odds API
        
        return []
        
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
        
        # Limit the number of broadcasts to display (to prevent exceeding 4096 characters)
        MAX_ODDS_DISPLAY = 20
        broadcasts_with_odds = broadcasts_with_odds[:MAX_ODDS_DISPLAY]
        
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
                safe_event = escape_html(broadcast['event'])
                safe_teams = escape_html(teams_text)
                
                # Format as requested
                message_text += f"⏰ {safe_time} | {emoji} <b>Football</b>: {safe_event}\n"
                message_text += "Фактический исход:\n"
                
                # Add odds - FIXED HTML TAGS FOR TELEGRAM COMPATIBILITY
                if 'odds' in broadcast and broadcast['odds']:
                    safe_odds = escape_html(broadcast['odds'])
                    message_text += f"{safe_odds} 📡 <i>{broadcast['odds_source']}</i>\n\n"
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