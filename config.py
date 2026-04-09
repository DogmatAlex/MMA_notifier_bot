import os
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# Get the Telegram bot token from environment variables
TELEGRAM_BOT_TOKEN = os.getenv('BOT_TOKEN')

# Get the Odds API key from environment variables
ODDS_API_KEY = os.getenv('ODDS_API_KEY')
