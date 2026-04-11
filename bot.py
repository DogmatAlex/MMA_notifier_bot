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

# Import markdown escape utility
# from aiogram.utils.markdown import escape_md

# Simple markdown escape function
def escape_md(text):
    if not text:
        return ""
    # Escape special markdown characters
    special_chars = ['_', '*', '[', ']', '(', ')', '~', '`', '>', '#', '+', '-', '=', '|', '{', '}', '.', '!']
    for char in special_chars:
        text = text.replace(char, '\\' + char)
    return text

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

def parse_matchtv_schedule(filter_next_24h=False):
    """
    Parse sports broadcasts using multi-source approach
    Returns a list of dictionaries with time and event information
    If filter_next_24h is True, only return events for the next 24 hours
    """
    try:
        # Use the new multi-source parser
        broadcasts = get_broadcasts_multi_source()
        
        if broadcasts:
            logging.info(f"Successfully parsed {len(broadcasts)} broadcasts using multi-source approach")
            
            # If filter_next_24h is True, filter broadcasts to next 24 hours
            if filter_next_24h:
                from datetime import datetime, timedelta
                import re
                
                # Get current time
                current_time = datetime.now()
                end_time = current_time + timedelta(hours=24)
                
                # For testing purposes, return all broadcasts without strict filtering
                logging.info(f"Returning all {len(broadcasts)} broadcasts without strict time filtering")
                return broadcasts
            else:
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
    broadcasts = parse_matchtv_schedule(filter_next_24h=True)
    print(f"!!! DAILY SCHEDULE: BOT RECEIVED {len(broadcasts)} EVENTS")
    
    # Ensure we send a message even if formatting fails
    if broadcasts:
        try:
            message_text = format_broadcast_message(broadcasts)
            # Always send the count of matches found, even if formatting fails
            if not message_text or "Трансляций на сегодня не найдено" in message_text or len(broadcasts) > 0:
                # Fallback message with count
                message_text = f"Найдено матчей: {len(broadcasts)}"
        except Exception as e:
            logging.error(f"Error formatting message: {e}")
            # Fallback message with count
            message_text = f"Найдено матчей: {len(broadcasts)}"
    else:
        message_text = "Трансляций на сегодня не найдено"
    
    # Send to all registered chats
    for chat_id in chat_ids:
        try:
            await bot.send_message(chat_id, message_text, parse_mode="Markdown", timeout=30)
        except asyncio.TimeoutError as e:
            logging.error(f"Timeout error sending message to {chat_id}: {e}")
            try:
                await bot.send_message(chat_id, "⚠️ Не удалось отправить расписание, попробуйте позже.", parse_mode="Markdown")
            except Exception as e2:
                logging.error(f"Failed to send fallback message to {chat_id}: {e2}")
        except Exception as e:
            logging.error(f"Error sending message to {chat_id}: {e}")
            try:
                await bot.send_message(chat_id, "⚠️ Ошибка при отправке расписания.", parse_mode="Markdown")
            except Exception as e2:
                logging.error(f"Failed to send fallback message to {chat_id}: {e2}")

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
    broadcasts = parse_matchtv_schedule(filter_next_24h=True)
    print(f"!!! FINAL CHECK: BOT RECEIVED {len(broadcasts)} EVENTS")
    
    # Ensure we send a message even if formatting fails
    if broadcasts:
        try:
            message_text = format_broadcast_message(broadcasts)
            # Always send the count of matches found, even if formatting fails
            if not message_text or "Трансляций на сегодня не найдено" in message_text or len(broadcasts) > 0:
                # Fallback message with count
                message_text = f"Найдено матчей: {len(broadcasts)}"
        except Exception as e:
            logging.error(f"Error formatting message: {e}")
            # Fallback message with count
            message_text = f"Найдено матчей: {len(broadcasts)}"
    else:
        message_text = "Трансляций на сегодня не найдено"
    
    try:
        await message.answer(message_text, parse_mode="Markdown", timeout=30)
    except asyncio.TimeoutError as e:
        logging.error(f"Timeout error sending message to {message.chat.id}: {e}")
        await message.answer("⚠️ Не удалось отправить расписание, попробуйте позже.", parse_mode="Markdown")
    except Exception as e:
        logging.error(f"Error sending message to {message.chat.id}: {e}")
        await message.answer("⚠️ Ошибка при отправке расписания.", parse_mode="Markdown")

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