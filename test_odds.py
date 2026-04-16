import asyncio
import sys
import os

# Add the parent directory to the path so we can import our modules
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from odds_parser import get_odds_broadcasts, format_odds_message

async def test_odds_parser():
    """Test the odds parser with betcity.ru"""
    print("Testing odds parser with betcity.ru...")
    
    try:
        # Get broadcasts with odds
        broadcasts = await get_odds_broadcasts()
        
        print(f"\nFound {len(broadcasts)} broadcasts with odds:")
        for i, broadcast in enumerate(broadcasts):
            print(f"  {i+1}. {broadcast['time']} - {broadcast['sport']} - {broadcast['event']}")
            print(f"     Odds: {broadcast['odds']}")
            print(f"     Source: {broadcast['odds_source']}")
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
    asyncio.run(test_odds_parser())