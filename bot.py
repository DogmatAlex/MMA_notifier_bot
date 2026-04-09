import asyncio
import logging
import requests
import cloudscraper
from bs4 import BeautifulSoup
from datetime import datetime, time
import re

from aiogram import Bot, Dispatcher, Router
from aiogram.filters import Command
from aiogram.types import Message, InlineKeyboardButton, InlineKeyboardMarkup

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger

# Import config
from config import TELEGRAM_BOT_TOKEN, ODDS_API_KEY

# Configure logging
logging.basicConfig(level=logging.INFO)

# Initialize bot and dispatcher
bot = Bot(token=TELEGRAM_BOT_TOKEN)
dp = Dispatcher()
router = Router()

# Store chat IDs for daily notifications
chat_ids = set()

# Import the new multi-source parser
from multi_source_parser import get_broadcasts_multi_source, format_broadcast_message

def parse_matchtv_schedule():
    """
    Parse sports broadcasts using multi-source approach
    Returns a list of dictionaries with time and event information
    """
    try:
        # Use the new multi-source parser
        broadcasts = get_broadcasts_multi_source()
        
        if broadcasts:
            logging.info(f"Successfully parsed {len(broadcasts)} broadcasts using multi-source approach")
            return broadcasts
        else:
            logging.warning("No broadcasts found from any source")
            return []
            
    except Exception as e:
        logging.error(f"Error in multi-source parsing: {e}")
        return []



async def send_daily_schedule():
    """
    Send daily schedule to all registered chats
    """
    broadcasts = parse_matchtv_schedule()
    message_text = format_broadcast_message(broadcasts)
    
    # Send to all registered chats
    for chat_id in chat_ids:
        try:
            await bot.send_message(chat_id, message_text, parse_mode="Markdown")
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
    message_text = format_broadcast_message(broadcasts)
    await message.answer(message_text, parse_mode="Markdown")

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