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
    Parse upcoming UFC fights with odds from Betcity Line section
    Returns: list of broadcasts with odds
    """
    # Import cache functions
    from cache import load_from_cache, save_to_cache
    
    # Check cache first
    cached = load_from_cache("betcity_odds", "current")
    if cached:
        odds_logger.info("Using cached data for Betcity API")
        return cached
    
    # Mock data for testing
    if TESTING:
        odds_logger.info("Using mock data for testing")
        return [
            {
                "time": "05:00",
                "sport": "MMA",
                "event": "Смешанные боевые искусства. UFC. Алджамейн Стерлинг - Юссеф Залал.",
                "odds": "📊 П1: 1.85 | П2: 4.10",
                "odds_source": "betcity.ru",
                "link": "https://betcity.ru/ru/line/event/123456"
            }
        ]
    
    try:
        # Use aiohttp for async requests
        async with aiohttp.ClientSession() as session:
            broadcasts = []
            
            # Headers for API requests
            headers = {
                'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0.0.0 Safari/537.36',
                'Referer': 'https://betcity.ru/',
                'Origin': 'https://betcity.ru',
                'Accept': 'application/json',
            }
            
            # Step 1: Get list of championships
            odds_logger.info("Fetching odds from Betcity API")
            mma_champs_url = "https://ad.betcity.ru/d/off/champs?rev=4&ids_sp=39&ver=69&csn=ooca9s"
            
            async with session.get(mma_champs_url, headers=headers, timeout=7) as response:
                if response.status != 200:
                    odds_logger.warning(f"Failed to fetch Betcity MMA Championships API, status code: {response.status}")
                    return []
                
                mma_champs_data = await response.json()
            
            # Extract UFC championship IDs
            ufc_champ_ids = []
            
            try:
                sports = mma_champs_data.get('reply', {}).get('sports', {})
                
                # MMA has sport_id = "39"
                mma_data = sports.get("39", {})
                if mma_data:
                    chmps = mma_data.get('chmps', {})
                    
                    for chmp_id, chmp_data in chmps.items():
                        # Filter for UFC only
                        champ_name = chmp_data.get('name_ch', '')
                        if champ_name.startswith("Смешанные боевые искусства. UFC."):
                            # Exclude cyber sports
                            if chmp_data.get('is_cyber') == 1:
                                continue
                            # Exclude "Возможные поединки" (speculative matches)
                            if "возможные поединки" in champ_name.lower():
                                continue
                            
                            ufc_champ_ids.append(chmp_id)
            
            except Exception as e:
                odds_logger.error(f"Error parsing MMA championships: {type(e).__name__}: {e}", exc_info=True)
                return []
            
            odds_logger.info(f"Found {len(ufc_champ_ids)} UFC championships to process")
            
            # Step 2: For each UFC championship, get the events
            for champ_id in ufc_champ_ids:
                try:
                    mma_events_url = f"https://ad.betcity.ru/d/off/events?rev=6&ids_ch={champ_id}&ver=69&csn=ooca9s"
                    
                    async with session.get(mma_events_url, headers=headers, timeout=7) as event_response:
                        if event_response.status != 200:
                            odds_logger.warning(f"Failed to fetch Betcity MMA Events API for champ {champ_id}, status code: {event_response.status}")
                            continue
                        
                        mma_events_data = await event_response.json()
                        
                        # Parse events data
                        try:
                            sports = mma_events_data.get('reply', {}).get('sports', {})
                            
                            # MMA has sport_id = "39"
                            mma_data = sports.get("39", {})
                            if not mma_data:
                                continue
                                
                            chmps = mma_data.get('chmps', {})
                            
                            for chmp_id, chmp_data in chmps.items():
                                # Filter for UFC only
                                champ_name = chmp_data.get('name_ch', '')
                                if not champ_name.startswith("Смешанные боевые искусства. UFC."):
                                    continue
                                
                                # Exclude cyber sports
                                if chmp_data.get('is_cyber') == 1:
                                    continue
                                # Exclude "Возможные поединки" (speculative matches) - safety check
                                if "возможные поединки" in champ_name.lower():
                                    continue
                                
                                evts = chmp_data.get('evts', {})
                                for event_id, event in evts.items():
                                    try:
                                        # Exclude cyber sports and esports
                                        if event.get('is_cyber') == 1 or event.get('is_esports') == 1:
                                            continue
                                        
                                        # Extract fighters
                                        home_fighter = event.get('name_ht', '')
                                        away_fighter = event.get('name_at', '')
                                        
                                        if not home_fighter or not away_fighter:
                                            continue
                                        
                                        # Check if event is upcoming (not live)
                                        if event.get('is_online') == 1:
                                            continue  # Skip live events
                                        
                                        # Extract time
                                        date_ev_str = event.get('date_ev_str', '')
                                        if not date_ev_str:
                                            continue
                                        
                                        # Extract time part from date_ev_str (e.g., "2026-04-29 05:00")
                                        time_str = date_ev_str.split(' ')[1] if ' ' in date_ev_str else date_ev_str
                                        
                                        # Create event title
                                        event_title = f"{home_fighter} - {away_fighter}"
                                        full_event = f"{champ_name}: {event_title}"
                                        
                                        # Exclude "Возможные поединки" (speculative matches) - safety check
                                        if "возможные поединки" in full_event.lower():
                                            continue
                                        
                                        # Extract odds for "Фактический исход" (1X2 market)
                                        home_odds = None
                                        away_odds = None
                                        
                                        # Look for the "Wm" block which contains the "Фактический исход" market
                                        # The structure is: event -> "main" -> "69" -> "data" -> event_id -> "blocks" -> "Wm" -> {P1, P2} -> "kf"
                                        main_market = event.get('main', {})
                                        fact_outcome_market = main_market.get('69', {})  # 69 is "Фактический исход"
                                        market_data = fact_outcome_market.get('data', {})
                                        event_data = market_data.get(event_id, {})
                                        blocks = event_data.get('blocks', {})
                                        wm_block = blocks.get('Wm', {})
                                        
                                        if wm_block:
                                            # Extract odds for each outcome (MMA usually only has P1 and P2)
                                            p1_data = wm_block.get('P1', {})
                                            p2_data = wm_block.get('P2', {})
                                            
                                            # Get the odds values (kf = коэффициент)
                                            home_odds = p1_data.get('kf')
                                            away_odds = p2_data.get('kf')
                                        
                                        # Skip if we don't have odds
                                        if home_odds is None or away_odds is None:
                                            odds_logger.warning(f"Missing odds for MMA match: {full_event}")
                                            continue
                                        
                                        # Validate that odds are numbers
                                        try:
                                            home_odds = float(home_odds)
                                            away_odds = float(away_odds)
                                        except (ValueError, TypeError):
                                            odds_logger.warning(f"Invalid odds values for MMA match: {full_event}")
                                            continue
                                        
                                        # Format odds string (MMA usually doesn't have draw/X)
                                        odds_str = f"П1: {home_odds:.2f} | П2: {away_odds:.2f}"
                                        
                                        # Create match link
                                        link = f"https://betcity.ru/ru/line/event/{event_id}"
                                        
                                        # Create broadcast entry
                                        broadcast = {
                                            "time": time_str,
                                            "date": date_ev_str.split(' ')[0],  # ← НОВОЕ: "2026-04-26"
                                            "sport": "MMA",
                                            "event": full_event,
                                            "odds": f"📊 {odds_str}",
                                            "odds_source": "betcity.ru",
                                            "link": link
                                        }
                                        
                                        broadcasts.append(broadcast)
                                        odds_logger.info(f"Found MMA broadcast: {time_str} - {full_event}")
                                        
                                    except Exception as e:
                                        odds_logger.warning(f"Error processing MMA event {event_id}: {e}")
                                        continue
                                
                        except Exception as e:
                            odds_logger.warning(f"Error parsing MMA events data for champ {champ_id}: {type(e).__name__}: {e}", exc_info=True)
                            continue
                        
                except (aiohttp.ClientError, asyncio.TimeoutError) as e:
                    odds_logger.warning(f"Betcity Line API unavailable for champ {champ_id}: {e}")
                    continue
                except Exception as e:
                    odds_logger.error(f"Error processing champ {champ_id}: {type(e).__name__}: {e}", exc_info=True)
                    continue
            
            # Deduplicate events based on (sport, event, time)
            unique_broadcasts = []
            seen = set()
            
            for broadcast in broadcasts:
                # Create a unique key: (sport, event, time)
                key = (broadcast['sport'], broadcast['event'], broadcast['time'])
                if key not in seen:
                    seen.add(key)
                    unique_broadcasts.append(broadcast)
            
            odds_logger.info(f"Removed {len(broadcasts) - len(unique_broadcasts)} duplicate broadcasts")
            odds_logger.info(f"Successfully parsed {len(unique_broadcasts)} unique broadcasts from Betcity Line API")
            
            # Save to cache if we have data
            if unique_broadcasts:
                save_to_cache("betcity_odds", "current", unique_broadcasts)
            
            return unique_broadcasts
            
    except (aiohttp.ClientError, asyncio.TimeoutError) as e:
        odds_logger.warning(f"Betcity Line API unavailable: {e}")
        # Try to return cached data if available
        cached = load_from_cache("betcity_odds", "current")
        if cached:
            odds_logger.info("Returning cached data for Betcity API due to API unavailability")
            return cached
        return []
    except Exception as e:
        odds_logger.error(f"Error parsing Line: {type(e).__name__}: {e}", exc_info=True)
        # Try to return cached data if available
        cached = load_from_cache("betcity_odds", "current")
        if cached:
            odds_logger.info("Returning cached data for Betcity API due to error")
            return cached
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
        
        def format_date_russian(date_str):
            """Преобразовать '2026-04-26' в '26 апреля'"""
            if not date_str or ' ' in date_str:
                return date_str
            try:
                from datetime import datetime
                dt = datetime.strptime(date_str, "%Y-%m-%d")
                months = ["января", "февраля", "марта", "апреля", "мая", "июня",
                          "июля", "августа", "сентября", "октября", "ноября", "декабря"]
                return f"{dt.day} {months[dt.month - 1]}"
            except:
                return date_str
        
        # Filter broadcasts that have odds
        broadcasts_with_odds = [b for b in broadcasts if 'odds' in b and b['odds']]
        
        if not broadcasts_with_odds:
            return "📊 <b>Коэффициентов не найдено</b>"
        
        # Limit the number of broadcasts to display (to prevent exceeding 4096 characters)
        MAX_ODDS_DISPLAY = 40
        broadcasts_with_odds = broadcasts_with_odds[:MAX_ODDS_DISPLAY]
        
        # Group broadcasts by tournament
        tournaments = {}
        for broadcast in broadcasts_with_odds:
            # Clean the event title
            broadcast['event'] = clean_event_title(broadcast['event'])
            
            # Extract tournament and fighters from event
            if ':' in broadcast['event']:
                tournament, fighters = broadcast['event'].split(':', 1)
                tournament = tournament.strip()
                fighters = fighters.strip()
            else:
                tournament = "UFC"
                fighters = broadcast['event']
            
            if tournament not in tournaments:
                tournaments[tournament] = []
            
            # Add fighters and odds to tournament
            # Extract odds values from the existing odds string
            odds_str = broadcast['odds'].replace('📊 ', '')  # Remove the emoji
            
            # For MMA, add draw odds (Х: 70.00) if not present
            if 'Х:' not in odds_str:
                # Parse existing odds (expecting format "П1: X.XX | П2: X.XX")
                parts = odds_str.split(' | ')
                if len(parts) == 2:
                    # Add draw odds
                    odds_str = f"{parts[0]} | Х: 70.00 | {parts[1]}"
            
            tournaments[tournament].append({
                'fighters': fighters,
                'odds': odds_str,
                'odds_source': broadcast['odds_source'],
                'date': broadcast.get('date', '')  # Add date field
            })
        
        # Sort fights within each tournament by date (from nearest to latest)
        for tournament in tournaments:
            # Sort fights by date (convert "2026-04-26" to comparable format)
            tournaments[tournament].sort(key=lambda x: x.get('date', '9999-99-99'))
        
        # Format message with tournament grouping
        message_text = "📊 <b>Коэффициенты ближайших боёв UFC</b>\n\n"
        
        for tournament, fights in tournaments.items():
            # Add tournament header
            message_text += f"🏆 {escape_html(tournament)}\n"
            
            # Group fights by date (assuming fights are already sorted by date)
            from itertools import groupby
            for date, date_fights in groupby(fights, key=lambda x: x.get('date', '')):
                date_list = list(date_fights)  # groupby returns an iterator, convert to list
                
                # Display date only if it exists and is not empty
                if date:
                    formatted_date = format_date_russian(date)
                    message_text += f"{formatted_date}\n"  # without emoji
                
                # Display all fights for this date
                for fight in date_list:
                    message_text += f"🥊 {escape_html(fight['fighters'])}\n"
                    message_text += f"📊 {escape_html(fight['odds'])}\n"
            
            # Add source at the end of tournament
            if fights:
                message_text += f"📡 <i>Источник: {escape_html(fights[0]['odds_source'])}</i>\n\n"
        
        return message_text
    except Exception as e:
        odds_logger.error(f"Error formatting odds message: {e}")
        # Return a simple message even if formatting fails
        return f"📊 Найдено {len([b for b in broadcasts if 'odds' in b and b['odds']])} коэффициентов."