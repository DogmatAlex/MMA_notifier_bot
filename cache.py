import json
import os
import logging
from datetime import datetime, timedelta

# Configure logging
logger = logging.getLogger(__name__)

CACHE_DIR = "cache"
CACHE_TTL = 600  # 10 minutes in seconds

def get_cache_key(source: str, date: str) -> str:
    """Сформировать имя файла кэша"""
    safe_date = date.replace("-", "_") if date else "today"
    return f"{source}_{safe_date}.json"

def load_from_cache(source: str, date: str):
    """Загрузить из кэша, если не истёк срок"""
    key = get_cache_key(source, date)
    path = os.path.join(CACHE_DIR, key)
    
    if not os.path.exists(path):
        return None
    
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
            # Проверка срока жизни
            cached_time = datetime.fromisoformat(data["cached_at"])
            if datetime.now() - cached_time < timedelta(seconds=CACHE_TTL):
                return data["content"]
    except Exception as e:
        logger.warning(f"Cache load error: {e}")
    return None

def save_to_cache(source: str, date: str, content):
    """Сохранить в кэш"""
    os.makedirs(CACHE_DIR, exist_ok=True)
    key = get_cache_key(source, date)
    path = os.path.join(CACHE_DIR, key)
    
    try:
        with open(path, "w", encoding="utf-8") as f:
            json.dump({
                "cached_at": datetime.now().isoformat(),
                "content": content
            }, f, ensure_ascii=False, indent=2)
    except Exception as e:
        logger.warning(f"Cache save error: {e}")