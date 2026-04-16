import asyncio
import sys
import os

# Add the parent directory to the path so we can import our modules
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from odds_parser import get_odds_broadcasts, format_odds_message, parse_betcity_api, TESTING

async def test_odds_api():
    """Test the odds parser with Betcity API"""
    print("Testing odds parser with Betcity API...")
    
    try:
        # Test with mock data
        if os.environ.get('TESTING', 'False').lower() == 'true':
            from odds_parser import TESTING
            # Set TESTING to True in the module
            import odds_parser
            odds_parser.TESTING = True
            
            # Get broadcasts with odds directly from Betcity API parser
            broadcasts = await parse_betcity_api()
        else:
            # Get broadcasts with odds
            broadcasts = await get_odds_broadcasts()
        
        print(f"\nFound {len(broadcasts)} broadcasts with odds:")
        for i, broadcast in enumerate(broadcasts):
            print(f"  {i+1}. {broadcast['time']} - {broadcast['sport']} - {broadcast['event']}")
            print(f"     Odds: {broadcast['odds']}")
            print(f"     Source: {broadcast['odds_source']}")
            print(f"     Link: {broadcast['link']}")
            print()
        
        # Test formatting
        formatted_message = format_odds_message(broadcasts)
        print("Formatted message:")
        print(formatted_message)
        
    except Exception as e:
        print(f"Error testing odds parser: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(test_odds_api())