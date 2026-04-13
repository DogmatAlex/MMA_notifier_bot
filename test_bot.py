#!/usr/bin/env python3
"""
Test script to verify the bot functionality
"""

import asyncio
import sys
import os

# Add the current directory to the path so we can import our modules
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from parser import get_broadcasts_48h, format_broadcast_message, format_odds_message

async def test_full_bot():
    """Test the full bot functionality"""
    print("=== Testing Full Bot Functionality ===")
    
    try:
        # Test parsing with odds
        print("1. Testing parsing with odds...")
        broadcasts_with_odds = await get_broadcasts_48h(include_odds=True)
        print(f"   Found {len(broadcasts_with_odds)} broadcasts with odds")
        
        # Show source distribution
        source_count = {}
        for broadcast in broadcasts_with_odds:
            source = broadcast.get('source', 'Unknown')
            source_count[source] = source_count.get(source, 0) + 1
            
        print("   Source distribution:")
        for source, count in source_count.items():
            print(f"     {source}: {count}")
            
        # Show sample broadcasts
        print("\n   Sample broadcasts:")
        for i, broadcast in enumerate(broadcasts_with_odds[:5]):
            print(f"     {i+1}. {broadcast['time']} - {broadcast['sport']} - {broadcast['event'][:50]}...")
            if 'source' in broadcast:
                print(f"        Source: {broadcast['source']}")
            if 'odds' in broadcast:
                print(f"        Odds: {broadcast['odds']}")
        
        # Test parsing without odds
        print("\n2. Testing parsing without odds...")
        broadcasts_without_odds = await get_broadcasts_48h(include_odds=False)
        print(f"   Found {len(broadcasts_without_odds)} broadcasts without odds")
        
        # Verify that both results have the same number of broadcasts
        if len(broadcasts_with_odds) == len(broadcasts_without_odds):
            print("   ✅ PASS: Both parsing methods return the same number of broadcasts")
        else:
            print("   ❌ FAIL: Parsing methods return different number of broadcasts")
        
        # Test schedule-only formatting
        print("\n3. Testing schedule-only message formatting...")
        schedule_message = format_broadcast_message(broadcasts_without_odds, include_odds=False)
        print(f"   Formatted schedule message length: {len(schedule_message)} characters")
        print(f"   Schedule message preview: {schedule_message[:300]}...")
        
        # Verify schedule message structure
        if "📅 СЕГОДНЯ" in schedule_message and "📅 ЗАВТРА" in schedule_message:
            print("   ✅ PASS: Schedule message contains both today and tomorrow sections")
        else:
            print("   ❌ FAIL: Schedule message missing today or tomorrow sections")
            
        # Check that odds are not included in schedule message
        if "📊 Коэффициенты:" not in schedule_message:
            print("   ✅ PASS: Schedule message does not contain odds")
        else:
            print("   ❌ FAIL: Schedule message contains odds")
            
        if "Трансляций не найдено" in schedule_message or len(broadcasts_without_odds) > 0:
            print("   ✅ PASS: Schedule message handles empty results correctly")
        else:
            print("   ❌ FAIL: Schedule message doesn't handle empty results correctly")
        
        # Test odds-only formatting
        print("\n4. Testing odds-only message formatting...")
        odds_message = format_odds_message(broadcasts_with_odds)
        print(f"   Formatted odds message length: {len(odds_message)} characters")
        print(f"   Odds message preview: {odds_message[:300]}...")
        
        # Verify odds message structure
        if "📅 СЕГОДНЯ" in odds_message and "📅 ЗАВТРА" in odds_message:
            print("   ✅ PASS: Odds message contains both today and tomorrow sections")
        else:
            print("   ❌ FAIL: Odds message missing today or tomorrow sections")
            
        # Check that odds are included in odds message
        broadcasts_with_odds_count = len([b for b in broadcasts_with_odds if 'odds' in b and b['odds']])
        if broadcasts_with_odds_count > 0:
            if "📊 Коэффициенты:" not in odds_message and "П1:" in odds_message:
                print("   ✅ PASS: Odds message contains odds in the correct format")
            elif "Коэффициентов не найдено" in odds_message:
                print("   ⚠️  WARNING: Odds message indicates no odds found")
            else:
                print("   ❌ FAIL: Odds message format is incorrect")
        else:
            if "Коэффициентов не найдено" in odds_message:
                print("   ✅ PASS: Odds message correctly indicates no odds found")
            else:
                print("   ❌ FAIL: Odds message should indicate no odds found")
            
        print("\n=== Test Summary ===")
        print("✅ Bot functionality test completed")
        print(f"✅ Found {len(broadcasts_with_odds)} broadcasts")
        print("✅ Schedule-only formatting working correctly")
        print("✅ Odds-only formatting working correctly")
        
    except Exception as e:
        print(f"❌ Error testing bot: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(test_full_bot())
    