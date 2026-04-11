#!/usr/bin/env python3
"""
Test script to verify the fixes for synchronization issues
"""

import sys
import os

# Add the current directory to the path so we can import our modules
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from multi_source_parser import get_broadcasts_multi_source, format_broadcast_message, is_future_event
from datetime import datetime, timedelta

def test_is_future_event():
    """Test the is_future_event function with midnight transitions"""
    print("Testing is_future_event function...")
    
    # Test case: Current time is 22:00, event is at 03:00 (should be considered future)
    current_time = datetime.now().replace(hour=22, minute=0, second=0, microsecond=0)
    event_time = "03:00"
    
    result = is_future_event(event_time, current_time)
    print(f"Current time: {current_time.strftime('%H:%M')}, Event time: {event_time}")
    print(f"Is future event: {result}")
    
    if result:
        print("✅ PASS: Midnight transition handled correctly")
    else:
        print("❌ FAIL: Midnight transition not handled correctly")
    
    print()

def test_parser_and_formatter():
    """Test the parser and formatter together"""
    print("Testing parser and formatter...")
    
    try:
        # Get broadcasts
        broadcasts = get_broadcasts_multi_source()
        print(f"Found {len(broadcasts)} broadcasts")
        
        # Test formatting
        message = format_broadcast_message(broadcasts)
        print(f"Formatted message length: {len(message)} characters")
        print(f"Message preview: {message[:200]}...")
        
        if broadcasts and "Трансляций на сегодня не найдено" not in message:
            print("✅ PASS: Parser and formatter working correctly")
        else:
            print("❌ FAIL: No broadcasts found or formatting issue")
            
    except Exception as e:
        print(f"❌ ERROR: {e}")
        import traceback
        traceback.print_exc()
    
    print()

def main():
    """Run all tests"""
    print("Running synchronization fixes verification tests...\n")
    
    test_is_future_event()
    test_parser_and_formatter()
    
    print("All tests completed!")

if __name__ == "__main__":
    main()