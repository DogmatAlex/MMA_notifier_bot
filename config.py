import os
from dotenv import load_dotenv

# Загружаем данные из .env
load_dotenv()

TELEGRAM_BOT = os.getenv('TELEGRAM_BOT')
ODDS_API_KEY = os.getenv('ODDS_API_KEY')

if not TELEGRAM_BOT:
    raise ValueError("ОШИБКА: Переменная TELEGRAM_BOT не найдена в .env файле!")

if not ODDS_API_KEY:
    raise ValueError("ОШИБКА: Переменная ODDS_API_KEY не найдена в .env файле!")
