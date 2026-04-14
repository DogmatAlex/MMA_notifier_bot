import asyncio
from parser import get_broadcasts_48h, format_broadcast_message

async def test_full_output():
    broadcasts = await get_broadcasts_48h()
    print(f'Found {len(broadcasts)} broadcasts')
    message = format_broadcast_message(broadcasts)
    print(message)

if __name__ == "__main__":
    asyncio.run(test_full_output())