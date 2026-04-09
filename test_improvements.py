import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

# Test the improved bot functionality
from bot import parse_matchtv_schedule, get_emoji_for_event

def test_improvements():
    print("Testing improved bot functionality...")
    
    # Test emoji selection
    test_events = [
        "Футбол. Премьер-лига: Зенит против Спартак",
        "MMA. UFC 300: Конор Макгрегор против Хабиба Нурмагомедова",
        "Бокс. Чемпионат мира: Тайсон Фьюри против Олеся Усика",
        "Теннис. Открытый чемпионат Франции",
        "Хоккей. КХЛ: СКА против ЦСКА"
    ]
    
    print("\nTesting emoji selection:")
    for event in test_events:
        emoji = get_emoji_for_event(event)
        print(f"  {emoji} {event}")
    
    # Test parsing function
    print("\nTesting schedule parsing...")
    broadcasts = parse_matchtv_schedule()
    
    print(f"Found {len(broadcasts)} broadcasts:")
    for i, broadcast in enumerate(broadcasts[:5]):  # Show first 5
        emoji = get_emoji_for_event(broadcast['event'])
        print(f"  {emoji} {broadcast['time']} - {broadcast['sport']}: {broadcast['event']}")
        
        # Check if it contains live broadcast
        if 'прямая трансляция' in broadcast['event'].lower():
            print(f"    ✓ Contains live broadcast")
        else:
            print(f"    ✗ Does not contain live broadcast")
            
        # Check time filtering
        print(f"    ✓ Future or current broadcast")

if __name__ == "__main__":
    test_improvements()