import asyncio
import sys
import os

# Add the parent directory to the path so we can import our modules
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from parser import parse_championat_ucl_source

async def test_ucl_filter():
    """Test the UCL filter to ensure youth/women matches are excluded"""
    print("Testing UCL filter for youth/women matches exclusion...")
    
    try:
        # Get UCL matches
        matches = await parse_championat_ucl_source()
        
        print(f"\nFound {len(matches)} UCL matches:")
        for i, match in enumerate(matches):
            print(f"  {i+1}. {match['time']} - {match['event']}")
        
        # Check if any youth/women matches slipped through
        youth_keywords = ["u19", "u17", "юношеск", "молодёж", "женск", "women", "youth"]
        youth_matches = []
        for match in matches:
            title = match['event'].lower()
            if any(kw in title for kw in youth_keywords):
                youth_matches.append(match)
        
        if youth_matches:
            print(f"\n❌ WARNING: Found {len(youth_matches)} youth/women matches that should have been filtered out:")
            for match in youth_matches:
                print(f"  - {match['event']}")
        else:
            print("\n✅ SUCCESS: No youth/women matches found in the results")
            
    except Exception as e:
        print(f"Error testing UCL filter: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(test_ucl_filter())