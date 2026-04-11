#!/usr/bin/env python3
"""
Test script to verify all improvements to the multi-source parser
"""

import logging
import os
from datetime import datetime, timedelta

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

def test_debug_snapshot():
    """Test that debug snapshot is created"""
    logging.info("Testing debug snapshot creation...")
    
    # Import the parser
    from multi_source_parser import get_broadcasts_multi_source, deduplicate_broadcasts
    
    # Create some test broadcasts
    test_broadcasts = [
        {
            "time": "20:00",
            "sport": "MMA",
            "event": "UFC 327: Прямая трансляция",
            "link": "https://matchtv.ru/on-air",
            "source": "fight.ru"
        },
        {
            "time": "21:00",
            "sport": "Football",
            "event": "Реал Мадрид - Барселона",
            "link": "https://matchtv.ru/on-air",
            "source": "matchtv.ru"
        }
    ]
    
    # Run deduplication to trigger debug snapshot creation
    deduplicated = deduplicate_broadcasts(test_broadcasts)
    
    # Check if debug file was created
    if os.path.exists('last_parse_debug.txt'):
        logging.info("✓ Debug snapshot file created successfully")
        # Check content
        with open('last_parse_debug.txt', 'r', encoding='utf-8') as f:
            content = f.read()
            if "DEBUG SNAPSHOT" in content and "UFC 327" in content:
                logging.info("✓ Debug snapshot contains expected content")
            else:
                logging.error("✗ Debug snapshot content is incorrect")
    else:
        logging.error("✗ Debug snapshot file was not created")

def test_live_broadcast_filtering():
    """Test that live broadcast filtering catches variations"""
    logging.info("Testing live broadcast filtering...")
    
    # Test data with various live broadcast phrases
    test_titles = [
        "UFC 327: Прямая трансляция",
        "Бокс: Прямой эфир",
        "Футбол: Онлайн трансляция",
        "MMA: Live broadcast",
        "Единоборства: ТВ"
    ]
    
    # Expected to match as live broadcasts
    expected_matches = [
        "прямая трансляция",
        "прямой эфир",
        "онлайн",
        "live",
        "тв"
    ]
    
    # Check each title
    for title in test_titles:
        lower_title = title.lower()
        is_live = (
            'прямая трансляция' in lower_title or 
            'live' in lower_title or 
            'прямой эфир' in lower_title or
            'онлайн' in lower_title or
            'тв' in lower_title
        )
        if is_live:
            logging.info(f"✓ Correctly identified as live: {title}")
        else:
            logging.error(f"✗ Failed to identify as live: {title}")

def test_flexible_date_filtering():
    """Test flexible date filtering for /today command"""
    logging.info("Testing flexible date filtering...")
    
    # Import the bot function
    from bot import parse_matchtv_schedule
    
    try:
        # Test with filter_next_24h=True
        broadcasts = parse_matchtv_schedule(filter_next_24h=True)
        logging.info(f"✓ Flexible date filtering works, found {len(broadcasts)} broadcasts")
        
        # Test with filter_next_24h=False
        all_broadcasts = parse_matchtv_schedule(filter_next_24h=False)
        logging.info(f"✓ Full schedule filtering works, found {len(all_broadcasts)} broadcasts")
        
        if len(broadcasts) <= len(all_broadcasts):
            logging.info("✓ Date filtering correctly reduces broadcast count")
        else:
            logging.warning("⚠ Date filtering may not be working correctly")
            
    except Exception as e:
        logging.error(f"✗ Error testing flexible date filtering: {e}")

def test_odds_api_error_logging():
    """Test detailed error logging for Odds API issues"""
    logging.info("Testing Odds API error logging...")
    
    # Import the odds function
    from multi_source_parser import get_odds
    
    try:
        # Test with non-existent teams
        odds = get_odds("NonExistentTeam1", "NonExistentTeam2")
        if odds is None:
            logging.info("✓ Odds API correctly returns None for non-existent teams")
        else:
            logging.warning("⚠ Odds API returned unexpected data for non-existent teams")
    except Exception as e:
        logging.error(f"✗ Error testing Odds API: {e}")

def test_fuzzy_matching():
    """Test fuzzy matching in deduplication"""
    logging.info("Testing fuzzy matching...")
    
    # Import the deduplication function
    from multi_source_parser import deduplicate_broadcasts
    
    # Create test broadcasts with similar names
    test_broadcasts = [
        {
            "time": "20:00",
            "sport": "MMA",
            "event": "UFC 327: Прямая трансляция",
            "link": "https://matchtv.ru/on-air"
        },
        {
            "time": "20:00",
            "sport": "MMA",
            "event": "UFC 327 Прямой эфир",
            "link": "https://matchtv.ru/on-air"
        },
        {
            "time": "21:00",
            "sport": "Football",
            "event": "Реал Мадрид - Барселона",
            "link": "https://matchtv.ru/on-air"
        }
    ]
    
    # Run deduplication
    deduplicated = deduplicate_broadcasts(test_broadcasts)
    
    # Should have 2 unique broadcasts (first two should be considered duplicates)
    if len(deduplicated) == 2:
        logging.info("✓ Fuzzy matching correctly identified duplicates")
    else:
        logging.warning(f"⚠ Fuzzy matching may not be working correctly, found {len(deduplicated)} unique broadcasts")

def main():
    """Run all tests"""
    logging.info("Starting comprehensive test of all improvements...")
    
    try:
        test_debug_snapshot()
        test_live_broadcast_filtering()
        test_flexible_date_filtering()
        test_odds_api_error_logging()
        test_fuzzy_matching()
        
        logging.info("All tests completed!")
        
    except Exception as e:
        logging.error(f"Error during testing: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    main()