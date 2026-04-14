import asyncio
from parser import get_broadcasts_48h, format_broadcast_message

async def test():
    broadcasts = await get_broadcasts_48h()
    print(f'Found {len(broadcasts)} broadcasts')
    print(format_broadcast_message(broadcasts)[:500])

if __name__ == "__main__":
    asyncio.run(test())