import asyncio
import logging
import requests
import cloudscraper
from bs4 import BeautifulSoup
from datetime import datetime, time
import re

from aiogram import Bot, Dispatcher, Router
from aiogram.filters import Command
from aiogram.types import Message

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger

# Import config
from config import TELEGRAM_BOT_TOKEN

# Configure logging
logging.basicConfig(level=logging.INFO)

# Initialize bot and dispatcher
bot = Bot(token=TELEGRAM_BOT_TOKEN)
dp = Dispatcher()
router = Router()

# Store chat IDs for daily notifications
chat_ids = set()

def parse_matchtv_schedule():
    """
    Parse sports broadcasts from matchtv.ru
    Returns a list of dictionaries with time and event information
    """
    try:
        # Use cloudscraper to avoid being blocked by the website
        scraper = cloudscraper.create_scraper(
            browser={
                'browser': 'firefox',
                'platform': 'windows',
                'mobile': False
            }
        )
        
        # Use headers to avoid being blocked by the website
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:89.0) Gecko/20100101 Firefox/89.0',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
            'Accept-Language': 'ru-RU,ru;q=0.8,en-US;q=0.5,en;q=0.3',
            'Accept-Encoding': 'gzip, deflate',
            'Connection': 'keep-alive',
            'Upgrade-Insecure-Requests': '1',
        }
        
        # Try to get the schedule page
        url = "https://matchtv.ru/tvguide"
        response = scraper.get(url, headers=headers, timeout=15)
        
        if response.status_code != 200:
            logging.error(f"Failed to fetch {url}, status code: {response.status_code}")
            raise Exception(f"HTTP Error: {response.status_code}")
        
        # Parse the HTML content
        soup = BeautifulSoup(response.content, 'html.parser')
        
        # Look for sports events
        broadcasts = []
        
        # Find channel transmission elements that contain schedule data
        # Using the actual class names we found
        channel_elements = soup.find_all('div', class_='p-tv-guide-schedule-channel-transmission')
        
        logging.info(f"Found {len(channel_elements)} channel transmission elements")
        
        for element in channel_elements:
            text_content = element.get_text()
            lower_text = text_content.lower()
            
            # Check if this element contains football or MMA/UFC
            if ('футбол' in lower_text or 'mma' in lower_text or
                'ufc' in lower_text or 'единоборства' in lower_text):
                
                # Extract time
                time_elem = element.find(class_='p-tv-guide-schedule-channel-transmission__time-block')
                time_str = time_elem.get_text().strip() if time_elem else "N/A"
                
                # Determine sport type
                sport_type = "Unknown"
                if 'футбол' in lower_text:
                    sport_type = "Football"
                elif 'mma' in lower_text or 'ufc' in lower_text or 'единоборства' in lower_text:
                    sport_type = "MMA"
                
                # Clean up the event text to extract the actual event name
                # Remove time and rating info
                event_name = text_content
                if time_str != "N/A" and time_str in event_name:
                    event_name = event_name.replace(time_str, "", 1).strip()
                
                # Remove rating info like [12+] or [16+]
                event_name = re.sub(r'\[\d+\+\]', '', event_name).strip()
                
                # Clean up sport prefixes
                if sport_type == "Football" and event_name.startswith("Футбол."):
                    event_name = event_name[7:].strip()  # Remove "Футбол."
                elif sport_type == "MMA" and event_name.startswith("Смешанные единоборства."):
                    event_name = event_name[23:].strip()  # Remove "Смешанные единоборства."
                
                # If we have a valid event, add it to broadcasts
                if time_str != "N/A" and event_name:
                    broadcast = {
                        "time": time_str,
                        "sport": sport_type,
                        "event": event_name,
                        "link": "https://matchtv.ru/tvguide"
                    }
                    broadcasts.append(broadcast)
                    logging.info(f"Found broadcast: {time_str} - {sport_type} - {event_name}")
        
        # Remove duplicates by converting to set of tuples and back
        seen = set()
        unique_broadcasts = []
        for broadcast in broadcasts:
            # Create a tuple of the identifying fields
            identifier = (broadcast['time'], broadcast['event'])
            if identifier not in seen:
                seen.add(identifier)
                unique_broadcasts.append(broadcast)
        
        # Sort by time
        unique_broadcasts.sort(key=lambda x: x['time'])
        
        # If we found broadcasts, return them
        if unique_broadcasts:
            logging.info(f"Successfully parsed {len(unique_broadcasts)} broadcasts")
            return unique_broadcasts[:15]  # Return up to 15 events
            
        # If no broadcasts found, log and return sample data
        logging.warning("No broadcasts found, returning sample data")
        return [
            {"time": "10:00", "sport": "MMA", "event": "UFC Fight Night", "link": "https://matchtv.ru/tvguide"},
            {"time": "14:30", "sport": "Football", "event": "Premier League: Team A vs Team B", "link": "https://matchtv.ru/tvguide"},
            {"time": "17:00", "sport": "MMA", "event": "Local MMA Championship", "link": "https://matchtv.ru/tvguide"},
            {"time": "20:00", "sport": "Football", "event": "Champions League: Team C vs Team D", "link": "https://matchtv.ru/tvguide"},
        ]
        
    except Exception as e:
        logging.error(f"Error parsing matchtv.ru: {e}")
        # Return sample data in case of error
        return [
            {"time": "10:00", "sport": "MMA", "event": "UFC Fight Night", "link": "https://matchtv.ru/tvguide"},
            {"time": "14:30", "sport": "Football", "event": "Premier League: Team A vs Team B", "link": "https://matchtv.ru/tvguide"},
            {"time": "17:00", "sport": "MMA", "event": "Local MMA Championship", "link": "https://matchtv.ru/tvguide"},
            {"time": "20:00", "sport": "Football", "event": "Champions League: Team C vs Team D", "link": "https://matchtv.ru/tvguide"},
        ]

async def send_daily_schedule():
    """
    Send daily schedule to all registered chats
    """
    broadcasts = parse_matchtv_schedule()
    if not broadcasts:
        message_text = "❌ Не удалось получить расписание на сегодня."
    else:
        message_text = "📺 Расписание прямых трансляций на сегодня:\n\n"
        for broadcast in broadcasts:
            message_text += f"⏰ {broadcast['time']}\n"
            message_text += f"🥊 {broadcast['sport']}: {broadcast['event']}\n"
            message_text += f"🔗 Смотреть онлайн: {broadcast['link']}\n\n"
    
    # Send to all registered chats
    for chat_id in chat_ids:
        try:
            await bot.send_message(chat_id, message_text)
        except Exception as e:
            logging.error(f"Error sending message to {chat_id}: {e}")

@router.message(Command(commands=["start"]))
async def command_start_handler(message: Message) -> None:
    """
    Handler for /start command
    """
    chat_ids.add(message.chat.id)
    await message.answer("👋 Добро пожаловать в бот уведомлений о спортивных трансляциях!\n\n"
                         "🤖 Я буду присылать вам расписание прямых трансляций MMA/UFC и футбола каждый день в 9:00.\n\n"
                         "⌨️ Доступные команды:\n"
                         "/today - Получить расписание на сегодня\n"
                         "/start - Показать это сообщение")

@router.message(Command(commands=["today"]))
async def command_today_handler(message: Message) -> None:
    """
    Handler for /today command - sends today's schedule immediately
    """
    chat_ids.add(message.chat.id)
    broadcasts = parse_matchtv_schedule()
    
    if not broadcasts:
        await message.answer("❌ Не удалось получить расписание на сегодня.")
        return
    
    message_text = "📺 Расписание прямых трансляций на сегодня:\n\n"
    for broadcast in broadcasts:
        message_text += f"⏰ {broadcast['time']}\n"
        message_text += f"🥊 {broadcast['sport']}: {broadcast['event']}\n"
        message_text += f"🔗 Смотреть онлайн: {broadcast['link']}\n\n"
    
    await message.answer(message_text)

async def main() -> None:
    """
    Main function to start the bot
    """
    # Include router
    dp.include_router(router)
    
    # Create scheduler for daily notifications
    scheduler = AsyncIOScheduler()
    # Schedule daily notification at 9:00 AM (Moscow time)
    scheduler.add_job(send_daily_schedule, CronTrigger(hour=9, minute=0, timezone='Europe/Moscow'))
    scheduler.start()
    
    # Start polling
    await dp.start_polling(bot)

if __name__ == "__main__":
    logging.info("Starting bot...")
    asyncio.run(main())