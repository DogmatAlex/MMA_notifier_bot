#!/usr/bin/env python3
"""
Script to demonstrate all the improvements made to the Telegram bot
without requiring a Telegram bot token.
"""

import sys
import os
import re
from datetime import datetime

# Add the project directory to the path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

# Mock the Telegram bot token to avoid validation issues
os.environ['TELEGRAM_BOT_TOKEN'] = '1234567890:ABCDEF1234567890ABCDEF1234567890ABC'

def get_emoji_for_event(event_name):
    """
    Get appropriate emoji for event based on its content
    """
    event_lower = event_name.lower()
    
    # Football emojis
    if any(keyword in event_lower for keyword in ['футбол', 'кубок', 'лига']):
        return "⚽"
    
    # MMA/Combat sports emojis
    if any(keyword in event_lower for keyword in ['mma', 'ufc', 'бокс', 'единоборства', 'боец']):
        return "🥊"
    
    # Default emoji
    return "📺"

def demonstrate_emoji_selection():
    """Demonstrate the smart emoji selection feature"""
    print("=" * 50)
    print("DEMONSTRATION: Smart Emoji Selection")
    print("=" * 50)
    
    test_events = [
        "Футбол. Премьер-лига: Зенит против Спартак",
        "MMA. UFC 300: Конор Макгрегор против Хабиба Нурмагомедова",
        "Бокс. Чемпионат мира: Тайсон Фьюри против Олеся Усика",
        "Теннис. Открытый чемпионат Франции",
        "Хоккей. КХЛ: СКА против ЦСКА",
        "Единоборства. Чемпионат России по ММА",
        "Кубок России по футболу",
        "Лига чемпионов UEFA"
    ]
    
    for event in test_events:
        emoji = get_emoji_for_event(event)
        print(f"{emoji} {event}")
    
    print("\n")

def demonstrate_time_filtering():
    """Demonstrate the time filtering feature"""
    print("=" * 50)
    print("DEMONSTRATION: Time Filtering")
    print("=" * 50)
    
    # Get current time
    current_time = datetime.now()
    current_hour = current_time.hour
    current_minute = current_time.minute
    
    print(f"Current time: {current_time.strftime('%H:%M')}")
    print("Filtering logic: Show only broadcasts that start at or after current time")
    print()
    
    # Sample broadcasts with different times
    sample_broadcasts = [
        {"time": "08:00", "sport": "Football", "event": "Morning Match - Прямая трансляция"},
        {"time": "12:00", "sport": "MMA", "event": "Midday Fight - Прямая трансляция"},
        {"time": "18:00", "sport": "Football", "event": "Evening Game - Прямая трансляция"},
        {"time": "22:00", "sport": "Boxing", "event": "Night Show - Прямая трансляция"},
    ]
    
    print("Sample broadcasts:")
    for broadcast in sample_broadcasts:
        try:
            hour, minute = map(int, broadcast['time'].split(':'))
            # Compare with current time
            if hour > current_hour or (hour == current_hour and minute >= current_minute):
                status = "SHOWING (future or current)"
            else:
                status = "HIDDEN (past)"
        except ValueError:
            status = "SHOWING (time parsing error)"
            
        print(f"  {broadcast['time']} - {broadcast['sport']}: {broadcast['event']} [{status}]")
    
    print("\n")

def demonstrate_live_broadcast_filtering():
    """Demonstrate the live broadcast filtering feature"""
    print("=" * 50)
    print("DEMONSTRATION: Live Broadcast Filtering")
    print("=" * 50)
    
    sample_events = [
        "Футбол. Премьер-лига: Зенит против Спартак - Прямая трансляция",
        "MMA. UFC 300: Конор Макгрегор против Хабиба Нурмагомедова - Прямая трансляция",
        "Бокс. Чемпионат мира: Тайсон Фьюри против Олеся Усика - Прямая трансляция",
        "Теннис. Открытый чемпионат Франции",  # No live broadcast
        "Хоккей. КХЛ: СКА против ЦСКА - Прямая трансляция",
        "Единоборства. Чемпионат России по ММА",  # No live broadcast
    ]
    
    print("Filtering logic: Show only events containing 'Прямая трансляция'")
    print()
    
    for event in sample_events:
        if 'прямая трансляция' in event.lower():
            status = "SHOWING (live broadcast)"
        else:
            status = "HIDDEN (not live)"
            
        emoji = get_emoji_for_event(event)
        print(f"{emoji} {event} [{status}]")
    
    print("\n")

def demonstrate_odds_buttons():
    """Demonstrate the odds/buttons feature"""
    print("=" * 50)
    print("DEMONSTRATION: Odds/Buttons Feature")
    print("=" * 50)
    
    sample_broadcasts = [
        {"time": "20:00", "sport": "MMA", "event": "UFC Fight Night - Прямая трансляция"},
        {"time": "22:00", "sport": "Football", "event": "Champions League: Бавария vs ПСЖ - Прямая трансляция"},
    ]
    
    print("For each broadcast, a button is added to check betting odds:")
    print()
    
    for broadcast in sample_broadcasts:
        emoji = get_emoji_for_event(broadcast['event'])
        print(f"⏰ {broadcast['time']}")
        print(f"{emoji} {broadcast['sport']}: {broadcast['event']}")
        
        # Create search query for odds
        search_query = broadcast['event'].replace('Прямая трансляция', '').strip()
        google_search_url = f"https://www.google.com/search?q={search_query}+коэффициенты+ставки"
        
        print(f"🔗 [Проверить коэффициенты]({google_search_url})")
        print()
    
    print("\n")

def main():
    """Main function to demonstrate all improvements"""
    print("MMA/Футбол Telegram Bot - Feature Demonstrations")
    print("=" * 50)
    print()
    
    demonstrate_emoji_selection()
    demonstrate_time_filtering()
    demonstrate_live_broadcast_filtering()
    demonstrate_odds_buttons()
    
    print("=" * 50)
    print("All demonstrations completed!")
    print("These features have been implemented in the Telegram bot.")
    print("=" * 50)

if __name__ == "__main__":
    main()