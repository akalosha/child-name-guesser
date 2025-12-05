import os
from pathlib import Path


# Base project directory (two levels up from this file)
BASE_DIR = Path(__file__).resolve().parent.parent

# Paths
DB_PATH = BASE_DIR / "child_names.db"
NAMES_FILE = BASE_DIR / "names_1000.txt"

# Telegram bot token
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "")

# Answer constants
ANSWER_LIKE = "like"
ANSWER_DISLIKE = "dislike"
ANSWER_NEUTRAL = "neutral"

# Rounds
ROUND_ONE = 1
ROUND_TWO = 2