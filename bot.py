import asyncio
import logging
import os
from dotenv import load_dotenv
from aiogram import Bot, Dispatcher, Router
from aiogram.filters import Command
from aiogram.types import Message
from aiogram.client.session.aiohttp import AiohttpSession
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from config import TELEGRAM_BOT
from parser import get_broadcasts_48h, format_broadcast_message, format_odds_message

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Initialize bot and dispatcher
session = AiohttpSession(timeout=60)  # Increase timeout to 60 seconds
bot = Bot(token=TELEGRAM_BOT, session=session)
dp = Dispatcher()
router = Router()

# Store chat IDs for daily notifications
chat_ids = set()

@router.message(Command(commands=["start"]))
async def command_start_handler(message: Message) -> None:
    """Handle /start command"""
    chat_ids.add(message.chat.id)
    
    welcome_text = (
        "👋 Добро пожаловать в бот уведомлений о спортивных трансляциях!\n\n"
        "🤖 Я буду присылать вам расписание трансляций MMA/UFC и футбола каждый день в 9:00.\n\n"
        "⌨️ Доступные команды:\n"
        "/today - Получить расписание на ближайшие 2 дня\n"
        "/odds - Получить коэффициенты для беттинга\n"
        "/start - Показать это сообщение"
    )
    
    await message.answer(welcome_text, parse_mode="HTML")

@router.message(Command(commands=["odds"]))
async def command_odds_handler(message: Message) -> None:
    """Handle /odds command - show only odds for bettors"""
    chat_ids.add(message.chat.id)
    
    # Send typing action to show the bot is working
    await bot.send_chat_action(message.chat.id, "typing")
    
    try:
        # Get broadcasts for the next 48 hours with odds
        broadcasts = await get_broadcasts_48h(include_odds=True)
        logger.info(f"Bot received {len(broadcasts)} events for odds")
        
        # Format the message with odds only
        message_text = format_odds_message(broadcasts)
        
        # Send the message
        await message.answer(message_text, parse_mode="HTML")
    except Exception as e:
        logger.error(f"Error sending odds message: {e}")
        await message.answer("⚠️ Ошибка при получении коэффициентов. Попробуйте позже.")

@router.message(Command(commands=["today"]))
async def command_today_handler(message: Message) -> None:
    """Handle /today command"""
    chat_ids.add(message.chat.id)
    
    # Send typing action to show the bot is working
    await bot.send_chat_action(message.chat.id, "typing")
    
    try:
        # Get broadcasts for the next 48 hours without odds, limited sources
        broadcasts = await get_broadcasts_48h(include_odds=False, limit_sources=True)
        logger.info(f"Bot received {len(broadcasts)} events")
        
        # Format the message without odds
        message_text = format_broadcast_message(broadcasts, include_odds=False)
        
        # Send the message
        await message.answer(message_text, parse_mode="HTML")
    except Exception as e:
        logger.error(f"Error sending message: {e}")
        await message.answer("⚠️ Ошибка при получении расписания. Попробуйте позже.")

async def send_daily():
    """Send daily notifications to all registered chats"""
    try:
        # Get broadcasts for the next 48 hours without odds, limited sources
        broadcasts = await get_broadcasts_48h(include_odds=False, limit_sources=True)
        
        # Format the message without odds
        text = format_broadcast_message(broadcasts, include_odds=False)
        
        # Send to all registered chats
        for cid in chat_ids:
            try:
                await bot.send_message(cid, text, parse_mode="HTML")
            except Exception as e:
                logger.error(f"Error sending daily message to chat {cid}: {e}")
    except Exception as e:
        logger.error(f"Error in send_daily: {e}")

async def main():
    """Main function to start the bot"""
    # Include router
    dp.include_router(router)
    
    # Set up scheduler for daily notifications at 9:00 AM Moscow time
    scheduler = AsyncIOScheduler()
    scheduler.add_job(send_daily, CronTrigger(hour=9, minute=0, timezone='Europe/Moscow'))
    scheduler.start()
    
    # Start polling
    await dp.start_polling(bot)

if __name__ == "__main__":
    # Run the bot
    asyncio.run(main())