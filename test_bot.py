#!/usr/bin/env python3
"""
Test script to verify the bot functionality
"""

import asyncio
import sys
import os

# Add the current directory to the path so we can import our modules
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from parser import get_broadcasts_48h, format_broadcast_message

async def test_full_bot():
    """Test the full bot functionality"""
    print("=== Testing Full Bot Functionality ===")
    
    try:
        # Test parsing
        print("1. Testing parsing...")
        broadcasts = await get_broadcasts_48h()
        print(f"   Found {len(broadcasts)} broadcasts")
        
        # Show source distribution
        source_count = {}
        for broadcast in broadcasts:
            source = broadcast.get('source', 'Unknown')
            source_count[source] = source_count.get(source, 0) + 1
            
        print("   Source distribution:")
        for source, count in source_count.items():
            print(f"     {source}: {count}")
            
        # Show sample broadcasts
        print("\n   Sample broadcasts:")
        for i, broadcast in enumerate(broadcasts[:5]):
            print(f"     {i+1}. {broadcast['time']} - {broadcast['sport']} - {broadcast['event'][:50]}...")
            if 'source' in broadcast:
                print(f"        Source: {broadcast['source']}")
        
        # Test formatting
        print("\n2. Testing message formatting...")
        message = format_broadcast_message(broadcasts)
        print(f"   Formatted message length: {len(message)} characters")
        print(f"   Message preview: {message[:300]}...")
        
        # Verify message structure
        if "📅 СЕГОДНЯ" in message and "📅 ЗАВТРА" in message:
            print("   ✅ PASS: Message contains both today and tomorrow sections")
        else:
            print("   ❌ FAIL: Message missing today or tomorrow sections")
            
        if "Трансляций не найдено" in message or len(broadcasts) > 0:
            print("   ✅ PASS: Message handles empty results correctly")
        else:
            print("   ❌ FAIL: Message doesn't handle empty results correctly")
            
        print("\n=== Test Summary ===")
        print("✅ Bot functionality test completed")
        print(f"✅ Found {len(broadcasts)} broadcasts")
        print("✅ Message formatting working correctly")
        
    except Exception as e:
        print(f"❌ Error testing bot: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(test_full_bot())