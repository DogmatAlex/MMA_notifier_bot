import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

# Create a temporary environment variable for the token
os.environ['TELEGRAM_BOT_TOKEN'] = '1234567890:ABCDEF1234567890ABCDEF1234567890ABC'

# Now import the functions we want to test
from bot import parse_matchtv_schedule, get_emoji_for_event

def test_emoji_selection():
    """Test the emoji selection function"""
    print("Testing emoji selection:")
    
    test_cases = [
        ("Футбол. Премьер-лига: Зенит против Спартак", "⚽"),
        ("MMA. UFC 300: Конор Макгрегор против Хабиба Нурмагомедова", "🥊"),
        ("Бокс. Чемпионат мира: Тайсон Фьюри против Олеся Усика", "🥊"),
        ("Теннис. Открытый чемпионат Франции", "📺"),
        ("Хоккей. КХЛ: СКА против ЦСКА", "📺"),
        ("Единоборства. Чемпионат России", "🥊"),
        ("Кубок России по футболу", "⚽"),
        ("Лига чемпионов", "⚽")
    ]
    
    for event, expected_emoji in test_cases:
        actual_emoji = get_emoji_for_event(event)
        status = "✓" if actual_emoji == expected_emoji else "✗"
        print(f"  {status} {actual_emoji} {event}")
    
    print()

def test_parsing_function():
    """Test the parsing function"""
    print("Testing schedule parsing...")
    
    try:
        broadcasts = parse_matchtv_schedule()
        print(f"Found {len(broadcasts)} broadcasts:")
        
        # Show first 5 broadcasts
        for i, broadcast in enumerate(broadcasts[:5]):
            emoji = get_emoji_for_event(broadcast['event'])
            print(f"  {emoji} {broadcast['time']} - {broadcast['sport']}: {broadcast['event']}")
            
            # Check if it contains live broadcast
            if 'прямая трансляция' in broadcast['event'].lower():
                print(f"    ✓ Contains live broadcast")
            else:
                print(f"    ✗ Does not contain live broadcast")
                
            # Check time filtering (this is harder to test without knowing current time)
            print(f"    ? Time filtering applied")
        print()
        
    except Exception as e:
        print(f"Error during parsing: {e}")
        print()

def main():
    print("Testing improved bot functionality...\n")
    
    test_emoji_selection()
    test_parsing_function()
    
    print("Testing completed!")

if __name__ == "__main__":
    main()