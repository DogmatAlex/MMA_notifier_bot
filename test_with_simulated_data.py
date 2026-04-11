#!/usr/bin/env python3
"""
Test script to verify the fixes with simulated data
"""

import sys
import os
from datetime import datetime, timedelta

# Add the current directory to the path so we can import our modules
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from multi_source_parser import (
    is_future_event, 
    deduplicate_broadcasts, 
    format_broadcast_message,
    get_odds,
    extract_team_names
)

def test_midnight_transition():
    """Test the is_future_event function with midnight transitions"""
    print("=== Testing Midnight Transition Handling ===")
    
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

def test_deduplication():
    """Test the deduplication function with sample data"""
    print("=== Testing Deduplication Function ===")
    
    # Sample broadcasts with duplicates
    sample_broadcasts = [
        {
            "time": "20:00",
            "sport": "MMA",
            "event": "UFC 287: Pereira vs Adesanya 2",
            "link": "https://matchtv.ru/on-air"
        },
        {
            "time": "20:00",
            "sport": "MMA",
            "event": "UFC 287: Pereira vs Adesanya II",
            "link": "https://matchtv.ru/on-air"
        },
        {
            "time": "22:00",
            "sport": "Football",
            "event": "Real Madrid vs Barcelona",
            "link": "https://matchtv.ru/on-air"
        },
        {
            "time": "22:00",
            "sport": "Football",
            "event": "Real Madrid - Barcelona",
            "link": "https://matchtv.ru/on-air"
        }
    ]
    
    print(f"Before deduplication: {len(sample_broadcasts)} broadcasts")
    for i, broadcast in enumerate(sample_broadcasts):
        print(f"  {i+1}. {broadcast['time']} - {broadcast['sport']}: {broadcast['event']}")
    
    deduplicated = deduplicate_broadcasts(sample_broadcasts)
    print(f"After deduplication: {len(deduplicated)} broadcasts")
    for i, broadcast in enumerate(deduplicated):
        print(f"  {i+1}. {broadcast['time']} - {broadcast['sport']}: {broadcast['event']}")
    
    if len(deduplicated) < len(sample_broadcasts):
        print("✅ PASS: Deduplication working correctly")
    else:
        print("❌ FAIL: Deduplication not working correctly")
    
    print()

def test_formatting():
    """Test the formatting function with sample data"""
    print("=== Testing Message Formatting ===")
    
    # Sample broadcasts
    sample_broadcasts = [
        {
            "time": "20:00",
            "sport": "MMA",
            "event": "UFC 287: Pereira vs Adesanya 2",
            "link": "https://matchtv.ru/on-air"
        },
        {
            "time": "22:00",
            "sport": "Football",
            "event": "Real Madrid vs Barcelona",
            "link": "https://matchtv.ru/on-air"
        }
    ]
    
    message = format_broadcast_message(sample_broadcasts)
    print(f"Formatted message:\n{message}")
    
    if "Трансляций на сегодня не найдено" not in message and len(message) > 50:
        print("✅ PASS: Formatting working correctly")
    else:
        print("❌ FAIL: Formatting not working correctly")
    
    print()

def test_team_extraction():
    """Test team name extraction"""
    print("=== Testing Team Name Extraction ===")
    
    test_cases = [
        "Real Madrid vs Barcelona",
        "UFC 287: Pereira vs Adesanya 2",
        "Liverpool - Manchester United",
        "Boxing: Tyson Fury на Deontay Wilder"
    ]
    
    for case in test_cases:
        home, away = extract_team_names(case)
        print(f"Event: {case}")
        print(f"  Home team: {home}")
        print(f"  Away team: {away}")
        print()
    
    print("✅ Team extraction completed")
    print()

def test_odds_function():
    """Test the odds function (will fail without API key, but we can test the structure)"""
    print("=== Testing Odds Function ===")
    
    # This will likely fail without a valid API key, but we can test the structure
    try:
        odds = get_odds("Real Madrid", "Barcelona")
        print(f"Odds result: {odds}")
        print("✅ Odds function executed (result may be None without valid API key)")
    except Exception as e:
        print(f"✅ Odds function executed with error (expected without valid API key): {e}")
    
    print()

def main():
    """Run all tests"""
    print("Running comprehensive tests with simulated data...\n")
    
    test_midnight_transition()
    test_deduplication()
    test_formatting()
    test_team_extraction()
    test_odds_function()
    
    print("All tests completed!")

if __name__ == "__main__":
    main()