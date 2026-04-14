import asyncio
from odds_parser import get_odds_broadcasts, format_odds_message

async def test():
    broadcasts = await get_odds_broadcasts()
    print(f'Found {len(broadcasts)} broadcasts')
    print(format_odds_message(broadcasts)[:500])

if __name__ == "__main__":
    asyncio.run(test())
    