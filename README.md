# Sports Notification Bot

A Telegram bot that aggregates sports broadcasts for the next 48 hours (today and tomorrow) from multiple Russian sports websites.

## Features

- **Multi-source parsing**: Collects data from 5 reliable sports websites
- **Smart filtering**: Focuses on Football and MMA events only
- **Fast execution**: Uses asyncio for concurrent requests, no time.sleep() delays
- **Clean data**: Removes advertising text and normalizes event titles
- **Deduplication**: Removes duplicate events found on multiple sources
- **Odds integration**: Fetches betting odds from The Odds API
- **Daily notifications**: Automatic daily updates at 9:00 AM Moscow time
- **Proper formatting**: Beautiful Markdown messages with emojis

## Sources

1. matchtv.ru
2. sport-express.ru
3. championat.com
4. sports.ru
5. liveresult.ru

## Requirements

- Python 3.8+
- Telegram Bot Token
- The Odds API Key

## Installation

1. Clone the repository:
   ```bash
   git clone <repository-url>
   cd sports-notification-bot
   ```

2. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```

3. Create a `.env` file based on `sample.env`:
   ```bash
   cp sample.env .env
   ```
   
4. Edit `.env` and add your actual tokens:
   ```
   TELEGRAM_BOT_TOKEN=your_actual_telegram_bot_token_here
   ODDS_API_KEY=your_actual_odds_api_key_here
   ```

## Usage

Run the bot:
```bash
python bot_main.py
```

## Bot Commands

- `/start` - Start the bot and register for daily notifications
- `/today` - Get sports broadcasts for the next 48 hours

## Architecture

### config.py
Handles loading of environment variables and validation.

### parser.py
Contains all parsing logic:
- Concurrent fetching from all sources using asyncio
- Smart filtering for Football and MMA events
- Text cleaning and normalization
- Deduplication algorithms
- Odds integration with fuzzy matching

### bot_main.py
Main bot implementation:
- Telegram command handlers
- Daily notification scheduler
- Message formatting and sending

## Error Handling

- Graceful handling of website outages (continues with remaining sources)
- Increased Telegram API timeout (60 seconds)
- Comprehensive logging
- Fallback messages when no events found

## Development

To test the parser independently:
```bash
python -m parser
```

## License

MIT License