#!/usr/bin/env python3
"""
Test script for config.py
"""

import os
import sys
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

# Mock environment variables
os.environ['BOT_TOKEN'] = 'mock_token_for_testing'
os.environ['ODDS_API_KEY'] = 'mock_odds_api_key_for_testing'

try:
    from config import TELEGRAM_BOT_TOKEN, ODDS_API_KEY
    print("Config import successful!")
    print(f"TELEGRAM_BOT_TOKEN: {TELEGRAM_BOT_TOKEN}")
    print(f"ODDS_API_KEY: {ODDS_API_KEY}")
except Exception as e:
    print(f"Error importing config: {e}")