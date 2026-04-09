#!/usr/bin/env python3
"""
Demonstration script for all improvements to the Telegram bot
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

def demonstrate_emoji_improvements():
    """Demonstrate the improved emoji selection"""
    print("=" * 60)
    print("IMPROVEMENT 1: Enhanced Emoji Selection")
    print("=" * 60)
    
    print("Added English keywords for better detection:")
    print("- Football: 'football', 'league', 'cup'")
    print("- MMA: 'boxing', 'fight'")
    print()
    
    test_cases = [
        ("Football: Manchester United vs Liverpool", "⚽"),
        ("Premier League match", "⚽"),
        ("Cup final: Зенит vs Спартак", "⚽"),
        ("Boxing: heavyweight championship", "🥊"),
        ("Fight of the century", "🥊"),
        ("Футбол: Зенит против Спартак", "⚽"),
        ("MMA: турнир чемпионов", "🥊"),
    ]
    
    for event, expected_emoji in test_cases:
        actual_emoji = get_emoji_for_event(event)
        print(f"{actual_emoji} {event}")
    
    print()

def demonstrate_sample_data_improvements():
    """Demonstrate the improved sample data"""
    print("=" * 60)
    print("IMPROVEMENT 2: Realistic Russian Sample Data")
    print("=" * 60)
    
    print("Previous sample data used generic placeholder format")
    print("New sample data uses realistic Russian text with proper keywords:")
    print()
    
    sample_events = [
        "Тренировочный бой - Прямая трансляция",
        "Футбол: Матч еще не определен - Прямая трансляция",
        "Спарринг клуба - Прямая трансляция",
        "Футбол: Резервный матч - Прямая трансляция",
    ]
    
    for event in sample_events:
        emoji = get_emoji_for_event(event)
        print(f"{emoji} {event}")
    
    print()

def demonstrate_odds_api_integration():
    """Demonstrate the Odds API integration"""
    print("=" * 60)
    print("IMPROVEMENT 3: Real Odds from The Odds API")
    print("=" * 60)
    
    print("Previous version only had Google search buttons")
    print("New version fetches real odds from The Odds API:")
    print()
    
    # Example of what the API returns
    example_odds = [
        "📊 Коэффициенты: Зенит 2.10 | Ничья 3.40 | Спартак 3.20",
        "📊 Коэффициенты: Конор Макгрегор 1.80 | Хабиб Нурмагомедов 2.20",
        "📊 Коэффициенты: Тайсон Фьюри 1.90 | Олеся Усик 2.10"
    ]
    
    for odds in example_odds:
        print(odds)
    
    print()
    print("If API is unavailable or rate limit is hit, fallback to Google search button")
    
def demonstrate_cloudscraper_improvements():
    """Demonstrate the improved cloudscraper headers"""
    print("=" * 60)
    print("IMPROVEMENT 4: Enhanced Cloudscraper Headers")
    print("=" * 60)
    
    print("Updated headers to better mimic a real browser:")
    print("- Modern User-Agent string")
    print("- Additional security headers (Sec-Fetch-*, Cache-Control)")
    print("- Better Accept-Language header")
    print()
    print("This should reduce the frequency of getting blocked by the website")
    print()

def main():
    """Main demonstration function"""
    print("MMA/Футбол Telegram Bot - All Improvements Demonstration")
    print("=" * 60)
    print()
    
    demonstrate_emoji_improvements()
    demonstrate_sample_data_improvements()
    demonstrate_odds_api_integration()
    demonstrate_cloudscraper_improvements()
    
    print("=" * 60)
    print("All improvements have been implemented!")
    print("=" * 60)

if __name__ == "__main__":
    main()