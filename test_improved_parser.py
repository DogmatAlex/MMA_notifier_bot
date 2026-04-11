#!/usr/bin/env python3
"""
Test script for the improved multi-source parser
"""

import logging
from multi_source_parser import get_broadcasts_multi_source, format_broadcast_message

# Configure logging to show detailed output
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler()
    ]
)

def test_improved_parser():
    """Test the improved multi-source parser"""
    print("Testing improved multi-source parser...")
    print("=" * 50)
    
    try:
        # Get broadcasts using the improved parser
        broadcasts = get_broadcasts_multi_source()
        
        print(f"\nFound {len(broadcasts)} unique broadcasts:")
        print("-" * 50)
        
        if broadcasts:
            for i, broadcast in enumerate(broadcasts[:15]):  # Show first 15
                source = broadcast.get('source', 'Unknown')
                print(f"{i+1:2d}. {broadcast['time']} - {broadcast['sport']} - {broadcast['event'][:60]}... (from {source})")
                
                # Show odds if available
                if 'odds' in broadcast and broadcast['odds']:
                    print(f"     Odds: {broadcast['odds']}")
        else:
            print("No broadcasts found")
            
        # Test formatting
        print("\n" + "=" * 50)
        print("FORMATTED MESSAGE:")
        print("=" * 50)
        message = format_broadcast_message(broadcasts)
        print(message[:2000])  # Show first 2000 characters
        if len(message) > 2000:
            print("... (message truncated)")
        
    except Exception as e:
        print(f"Error testing parser: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    test_improved_parser()