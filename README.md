Child Name Guesser – Telegram Bot
=================================

Overview
--------
- Two users connect to the bot and press `/start` to form a pair.
- Round 1 begins automatically: each user is shown a name with three buttons: `Like`, `Neutral`, `Not like`.
- Each user answers each name only once; the next name appears immediately after answering.
- `/result` shows names both users liked in Round 1.
- `/start2` begins Round 2, where only Round 1 common likes are shown.
- `/result2` shows names both users liked in Round 2.
- Uses SQLite for storage and `names_1000.txt` as the name list.

Project Structure
-----------------
- `bot_app/` – bot, DB, and core logic
  - `config.py` – paths and constants
  - `db.py` – SQLite schema and helpers
  - `core.py` – pairing, next-name selection, results
  - `names_loader.py` – load names from file
  - `bot.py` – telegram bot entrypoint (python-telegram-bot v20)
- `tests/test_core.py` – unit tests for core logic
- `names_1000.txt` – source names list (UTF-8)

Setup
-----
1. Create a Telegram bot and get the bot token.
2. Set the environment variable `TELEGRAM_BOT_TOKEN` with your token.
3. Ensure `python-telegram-bot` v20+ is installed in your Python environment.

Windows run instructions
------------------------
- Use the provided Python: `C:\Users\user\.conda\envs\tensorflow3\python.exe`
- From the project root:

  - Run tests:
    - `C:\Users\user\.conda\envs\tensorflow3\python.exe -m unittest discover -s tests -p "test_*.py" -v`

  - Start bot:
    - Set `TELEGRAM_BOT_TOKEN` environment variable
    - `C:\Users\user\.conda\envs\tensorflow3\python.exe bot_app/bot.py`

Notes
-----
- Round 2 shows only names both users liked in Round 1.
- Results (`/result` and `/result2`) list common likes alphabetically.
- If more than two users press `/start`, the first two will form a pair; others will wait until a pending pair exists.