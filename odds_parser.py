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
            # Betcity API endpoint
            # TODO: уточнить актуальный Betcity API endpoint
            url = "https://ad.betcity.ru/d/off/live?rev=3&ver=575&csn=o977aa"
            
            # Headers for API request
            headers = {
                'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0.0.0 Safari/537.36',
                'Referer': 'https://betcity.ru/',
                'Origin': 'https://betcity.ru',
                'Accept': 'application/json',
            }
            
            odds_logger.info("Attempting to fetch data from Betcity API")
            
            # Fetch data from Betcity API with a timeout of 7 seconds
            async with session.get(url, headers=headers, timeout=7) as response:
                if response.status != 200:
                    odds_logger.warning(f"Failed to fetch Betcity API, status code: {response.status}")
                    return []
                
                data = await response.json()
                
            broadcasts = []
            
            # Get current time for filtering
            current_time = get_current_time()
            
            # Process events from API response
            events = data.get('data', {}).get('events', [])
            odds_logger.info(f"Found {len(events)} events in Betcity API response")
            
            for event in events:
                try:
                    # Only football events
                    if event.get('sport_id') != 1 and event.get('sport_name') != 'Футбол':
                        continue
                    
                    # Exclude cyberfootball
                    league_name = event.get('league_name', '').lower()
                    home_team = event.get('home_team', '').lower()
                    if any(kw in league_name for kw in EXCLUDE_KEYWORDS) or any(kw in home_team for kw in EXCLUDE_KEYWORDS):
                        odds_logger.info(f"Skipping cyberfootball match: {event.get('home_team')} - {event.get('away_team')}")
                        continue
                    
                    # Extract teams
                    home_team = event.get('home_team', '')
                    away_team = event.get('away_team', '')
                    
                    if not home_team or not away_team:
                        continue
                    
                    # Create event title
                    event_title = f"{home_team} - {away_team}"
                    
                    # Extract tournament name
                    tournament_name = event.get('league_name', '')
                    
                    # Create full event name with tournament
                    if tournament_name:
                        full_event = f"{tournament_name}: {event_title}"
                    else:
                        full_event = event_title
                    
                    # Extract time
                    time_str = "LIVE"  # Default to LIVE for live matches
                    
                    # Try to get actual time if available
                    event_time = event.get('time', 0)
                    if event_time:
                        # Convert timestamp to time string
                        from datetime import datetime
                        event_datetime = datetime.fromtimestamp(event_time)
                        time_str = event_datetime.strftime("%H:%M")
                    
                    # Extract odds for "Фактический исход" (1X2 market)
                    home_odds = None
                    draw_odds = None
                    away_odds = None
                    
                    # Look for main bets (Фактический исход)
                    main_bets = event.get('main_bets', [])
                    for bet in main_bets:
                        # Check if this is the 1X2 market (usually outcome_type 1 or outcomes with type in [1,2,3])
                        outcome_type = bet.get('outcome_type', 0)
                        if outcome_type in [1, 2, 3]:  # 1 - П1, 2 - X, 3 - П2
                            try:
                                odds_value = float(bet.get('odds', 0))
                                if outcome_type == 1:  # П1
                                    home_odds = odds_value
                                elif outcome_type == 2:  # X
                                    draw_odds = odds_value
                                elif outcome_type == 3:  # П2
                                    away_odds = odds_value
                            except (ValueError, TypeError):
                                odds_logger.warning(f"Could not parse odds value for outcome type {outcome_type}")
                    
                    # If we didn't find odds in main_bets, try outcomes
                    if not home_odds and not draw_odds and not away_odds:
                        outcomes = event.get('outcomes', [])
                        for outcome in outcomes:
                            outcome_type = outcome.get('type', 0)
                            if outcome_type in [1, 2, 3]:  # 1 - П1, 2 - X, 3 - П2
                                try:
                                    odds_value = float(outcome.get('odds', 0))
                                    if outcome_type == 1:  # П1
                                        home_odds = odds_value
                                    elif outcome_type == 2:  # X
                                        draw_odds = odds_value
                                    elif outcome_type == 3:  # П2
                                        away_odds = odds_value
                                except (ValueError, TypeError):
                                    odds_logger.warning(f"Could not parse odds value for outcome type {outcome_type}")
                    
                    # Skip if we don't have both home and away odds
                    if not home_odds or not away_odds:
                        odds_logger.warning(f"Missing odds for match: {full_event}")
                        continue
                    
                    # Format odds string
                    if draw_odds:
                        odds_str = f"П1: {home_odds:.2f} | Х: {draw_odds:.2f} | П2: {away_odds:.2f}"
                    else:
                        odds_str = f"П1: {home_odds:.2f} | П2: {away_odds:.2f}"
                    
                    # Create match link
                    match_id = event.get('id', '')
                    if match_id:
                        link = f"https://betcity.ru/ru/live/event/{match_id}"
                    else:
                        link = "https://betcity.ru/ru/live"
                    
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
                    odds_logger.warning(f"Error processing event: {e}")
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
                
                # Add odds
                if 'odds' in broadcast and broadcast['odds']:
                    safe_odds = escape_html(broadcast['odds'])
                    message_text += f"{safe_odds} 📡 <small>{broadcast['odds_source']}</small>\n\n"
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