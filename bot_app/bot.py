import logging
import os
from typing import Optional

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes, CallbackQueryHandler

from .config import TELEGRAM_BOT_TOKEN, DB_PATH, ANSWER_LIKE, ANSWER_DISLIKE, ANSWER_NEUTRAL, ROUND_ONE, ROUND_TWO
from .db import get_connection, init_db, get_user_chat_id
from .core import (
    create_or_join_pair,
    get_user_pair,
    get_next_name_for_round,
    record_answer,
    get_results_for_round,
    start_second_round,
    get_round_progress,
)
from .names_loader import load_names
from .db import add_names


logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def build_keyboard(pair_id: int, name_id: int, round_num: int) -> InlineKeyboardMarkup:
    # Compact callback_data format: r|pair|name|round|ans
    def cb(ans_short: str) -> str:
        return f"r|{pair_id}|{name_id}|{round_num}|{ans_short}"

    buttons = [
        [
            InlineKeyboardButton("👍 Like", callback_data=cb("L")),
            InlineKeyboardButton("😐 Neutral", callback_data=cb("N")),
            InlineKeyboardButton("👎 Not like", callback_data=cb("D")),
        ]
    ]
    return InlineKeyboardMarkup(buttons)


async def send_next_name(update: Update, context: ContextTypes.DEFAULT_TYPE, conn, pair_id: int, user_id: int, round_num: int):
    row = get_next_name_for_round(conn, pair_id, round_num, user_id)
    answered, total = get_round_progress(conn, pair_id, round_num, user_id)
    if not row:
        await context.bot.send_message(
            chat_id=update.effective_chat.id,
            text=f"All names rated for round {round_num}. Progress: {answered}/{total}. Use /result{'' if round_num == 1 else '2'} to see matches.",
        )
        return
    await context.bot.send_message(
        chat_id=update.effective_chat.id,
        text=f"Round {round_num} ({answered}/{total}): {row['name']}",
        reply_markup=build_keyboard(pair_id, row["id"], round_num),
    )


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not TELEGRAM_BOT_TOKEN:
        await update.message.reply_text("Bot token missing. Set TELEGRAM_BOT_TOKEN env variable.")
        return
    conn = get_connection(str(DB_PATH))
    init_db(conn)
    # Seed names once if empty
    cur = conn.cursor()
    cur.execute("SELECT COUNT(*) AS cnt FROM names")
    if cur.fetchone()["cnt"] == 0:
        names = load_names(DB_PATH.parent / "names_1000.txt")
        add_names(conn, names)

    user_id = update.effective_user.id
    username = update.effective_user.username
    chat_id = update.effective_chat.id

    pair, paired_now = create_or_join_pair(conn, user_id, username, chat_id)

    if pair["user2_id"] is None:
        await update.message.reply_text("Waiting for another user to press /start to form a pair.")
        return

    # Pair is complete now
    await update.message.reply_text("Pair found! Starting round 1.")
    # Notify the other user, if we know their chat_id
    other_user_id = pair["user1_id"] if pair["user2_id"] == user_id else pair["user2_id"]
    other_chat_id = get_user_chat_id(conn, other_user_id)
    if other_chat_id:
        await context.bot.send_message(chat_id=other_chat_id, text="Pair found! Starting round 1.")

    await send_next_name(update, context, conn, pair["id"], user_id, ROUND_ONE)


def _map_answer_short(ans_short: str) -> str:
    return {"L": ANSWER_LIKE, "N": ANSWER_NEUTRAL, "D": ANSWER_DISLIKE}[ans_short]


async def rate_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    data = q.data  # r|pair|name|round|ans
    try:
        _, pair_id_s, name_id_s, round_s, ans_short = data.split("|")
        pair_id = int(pair_id_s)
        name_id = int(name_id_s)
        round_num = int(round_s)
        answer = _map_answer_short(ans_short)
    except Exception:
        await q.edit_message_text("Invalid selection.")
        return

    conn = get_connection(str(DB_PATH))
    init_db(conn)
    user_id = update.effective_user.id
    recorded = record_answer(conn, pair_id, round_num, user_id, name_id, answer)
    if not recorded:
        # Already answered; show the next
        pass
    # Send next name
    await send_next_name(update, context, conn, pair_id, user_id, round_num)


async def result_round1(update: Update, context: ContextTypes.DEFAULT_TYPE):
    conn = get_connection(str(DB_PATH))
    init_db(conn)
    user_id = update.effective_user.id
    pair = get_user_pair(conn, user_id)
    if not pair or pair["user2_id"] is None:
        await update.message.reply_text("No active pair. Use /start with another user.")
        return
    matches = get_results_for_round(conn, pair["id"], ROUND_ONE)
    if not matches:
        await update.message.reply_text("No common likes yet in round 1.")
        return
    await update.message.reply_text("Round 1 matches:\n" + "\n".join(matches))


async def start2(update: Update, context: ContextTypes.DEFAULT_TYPE):
    conn = get_connection(str(DB_PATH))
    init_db(conn)
    user_id = update.effective_user.id
    pair = get_user_pair(conn, user_id)
    if not pair or pair["user2_id"] is None:
        await update.message.reply_text("No active pair. Use /start with another user.")
        return
    start_second_round(conn, pair["id"])
    await update.message.reply_text("Starting round 2 (common likes from round 1).")

    other_user_id = pair["user1_id"] if pair["user2_id"] == user_id else pair["user2_id"]
    other_chat_id = get_user_chat_id(conn, other_user_id)
    if other_chat_id:
        await context.bot.send_message(chat_id=other_chat_id, text="Starting round 2.")

    await send_next_name(update, context, conn, pair["id"], user_id, ROUND_TWO)


async def result_round2(update: Update, context: ContextTypes.DEFAULT_TYPE):
    conn = get_connection(str(DB_PATH))
    init_db(conn)
    user_id = update.effective_user.id
    pair = get_user_pair(conn, user_id)
    if not pair or pair["user2_id"] is None:
        await update.message.reply_text("No active pair. Use /start with another user.")
        return
    matches = get_results_for_round(conn, pair["id"], ROUND_TWO)
    if not matches:
        await update.message.reply_text("No common likes in round 2 yet.")
        return
    await update.message.reply_text("Round 2 matches:\n" + "\n".join(matches))


def main():
    token = TELEGRAM_BOT_TOKEN
    if not token:
        logger.error("TELEGRAM_BOT_TOKEN environment variable not set.")
        raise RuntimeError("TELEGRAM_BOT_TOKEN environment variable not set.")

    # Ensure DB exists and seed names
    conn = get_connection(str(DB_PATH))
    init_db(conn)
    cur = conn.cursor()
    cur.execute("SELECT COUNT(*) AS cnt FROM names")
    if cur.fetchone()["cnt"] == 0:
        names = load_names(DB_PATH.parent / "names_1000.txt")
        add_names(conn, names)

    application = ApplicationBuilder().token(token).build()

    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("result", result_round1))
    application.add_handler(CommandHandler("start2", start2))
    application.add_handler(CommandHandler("result2", result_round2))
    application.add_handler(CallbackQueryHandler(rate_callback))

    application.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    main()