#!/usr/bin/env python3
"""
Test script for the emoji selection function only
"""

def get_emoji_for_event(event_name):
    """
    Get appropriate emoji for event based on its content
    """
    event_lower = event_name.lower()
    
    # Football emojis
    if any(keyword in event_lower for keyword in ['футбол', 'кубок', 'лига', 'football', 'league', 'cup']):
        return "⚽"
    
    # MMA/Combat sports emojis
    if any(keyword in event_lower for keyword in ['mma', 'ufc', 'бокс', 'единоборства', 'боец', 'boxing', 'fight']):
        return "🥊"
    
    # Default emoji
    return "📺"

def test_emoji_function():
    """Test the improved emoji selection function"""
    print("=" * 50)
    print("Testing improved emoji selection function")
    print("=" * 50)
    
    test_cases = [
        # Russian keywords
        ("Футбол: Зенит против Спартак", "⚽"),
        ("Кубок России по футболу", "⚽"),
        ("Премьер-лига: матч дня", "⚽"),
        ("MMA: турнир чемпионов", "🥊"),
        ("UFC: бой века", "🥊"),
        ("Бокс: чемпионат мира", "🥊"),
        ("Единоборства: турнир", "🥊"),
        ("Боец года", "🥊"),
        
        # English keywords
        ("Football: Manchester United vs Liverpool", "⚽"),
        ("Premier League match", "⚽"),
        ("Champions League final", "⚽"),
        ("Cup final: Зенит vs Спартак", "⚽"),
        ("Boxing: heavyweight championship", "🥊"),
        ("Fight of the century", "🥊"),
        
        # Default cases
        ("Теннис: открытый чемпионат", "📺"),
        ("Хоккей: КХЛ", "📺"),
    ]
    
    all_passed = True
    for event, expected_emoji in test_cases:
        actual_emoji = get_emoji_for_event(event)
        status = "PASS" if actual_emoji == expected_emoji else "FAIL"
        if status == "FAIL":
            all_passed = False
        print(f"{status}: '{event}' -> {actual_emoji} (expected: {expected_emoji})")
    
    print(f"\nOverall result: {'ALL TESTS PASSED' if all_passed else 'SOME TESTS FAILED'}")
    print()

def test_sample_data():
    """Test that sample data has proper keywords for emoji selection"""
    print("=" * 50)
    print("Testing sample data for emoji selection")
    print("=" * 50)
    
    # Test the sample data that would be used when parsing fails
    sample_events = [
        "Тренировочный бой - Прямая трансляция",
        "Футбол: Матч еще не определен - Прямая трансляция",
        "Спарринг клуба - Прямая трансляция",
        "Футбол: Резервный матч - Прямая трансляция",
    ]
    
    for event in sample_events:
        emoji = get_emoji_for_event(event)
        has_sport_keyword = any(keyword in event.lower() for keyword in ['футбол', 'mma', 'боец', 'бой', 'спарринг'])
        print(f"Event: '{event}'")
        print(f"  Emoji: {emoji}")
        print(f"  Has sport keyword: {has_sport_keyword}")
        print()

def main():
    """Main test function"""
    print("Testing new improvements to the Telegram bot")
    print()
    
    test_emoji_function()
    test_sample_data()
    
    print("=" * 50)
    print("All tests completed!")
    print("=" * 50)

if __name__ == "__main__":
    main()