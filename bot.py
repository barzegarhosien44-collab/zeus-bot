import os
import sqlite3
import logging
import re
from telegram import Update
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    ContextTypes,
    filters,
)

TOKEN = os.getenv("BOT_TOKEN")

if not TOKEN:
    raise RuntimeError("BOT_TOKEN تنظیم نشده است.")

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
)

DB = "bot.db"


def db():
    return sqlite3.connect(DB)


def init_db():
    conn = db()
    cur = conn.cursor()

    cur.execute("""
        CREATE TABLE IF NOT EXISTS users (
            user_id INTEGER PRIMARY KEY,
            name TEXT NOT NULL,
            coins INTEGER DEFAULT 0,
            wins INTEGER DEFAULT 0
        )
    """)

    conn.commit()
    conn.close()


def add_user(user):
    conn = db()
    cur = conn.cursor()

    cur.execute(
        "INSERT OR IGNORE INTO users (user_id, name) VALUES (?, ?)",
        (user.id, user.full_name),
    )

    cur.execute(
        "UPDATE users SET name = ? WHERE user_id = ?",
        (user.full_name, user.id),
    )

    conn.commit()
    conn.close()


def get_coins(user_id):
    conn = db()
    cur = conn.cursor()

    cur.execute("SELECT coins FROM users WHERE user_id = ?", (user_id,))
    row = cur.fetchone()

    conn.close()

    return row[0] if row else 0


def change_coins(user_id, amount):
    conn = db()
    cur = conn.cursor()

    cur.execute(
        "UPDATE users SET coins = coins + ? WHERE user_id = ?",
        (amount, user_id),
    )

    conn.commit()
    conn.close()


def add_win(user_id):
    conn = db()
    cur = conn.cursor()

    cur.execute(
        "UPDATE users SET wins = wins + 1 WHERE user_id = ?",
        (user_id,),
    )

    conn.commit()
    conn.close()


async def is_owner(update):
    if not update.effective_chat:
        return False

    if update.effective_chat.type == "private":
        return False

    member = await update.effective_chat.get_member(
        update.effective_user.id
    )

    return member.status == "creator"


async def message_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message or not update.effective_user:
        return

    text = update.message.text.strip()

    user = update.effective_user
    add_user(user)

    # موجودی
    if text in ["موجودی", "موجودی من", "سکه"]:
        coins = get_coins(user.id)

        await update.message.reply_text(
            f"👤 {user.full_name}\n"
            f"🪙 موجودی شما: {coins:,} سکه"
        )
        return

    # لیدربورد سکه
    if text in ["لیدربورد", "لیدر بورد", "ثروتمندترین"]:
        conn = db()
        cur = conn.cursor()

        cur.execute("""
            SELECT name, coins
            FROM users
            ORDER BY coins DESC
            LIMIT 10
        """)

        rows = cur.fetchall()
        conn.close()

        if not rows:
            await update.message.reply_text("هنوز کسی سکه‌ای ندارد.")
            return

        result = "🏆 لیدربورد سکه\n\n"

        medals = ["🥇", "🥈", "🥉"]

        for i, (name, coins) in enumerate(rows):
            medal = medals[i] if i < 3 else f"{i + 1}."
            result += f"{medal} {name} — 🪙 {coins:,}\n"

        await update.message.reply_text(result)
        return

    # لیدربورد برد
    if text in ["لیدربورد برد", "لیدر بورد برد", "بیشترین برد"]:
        conn = db()
        cur = conn.cursor()

        cur.execute("""
            SELECT name, wins
            FROM users
            ORDER BY wins DESC
            LIMIT 10
        """)

        rows = cur.fetchall()
        conn.close()

        result = "🏆 لیدربورد برد\n\n"

        medals = ["🥇", "🥈", "🥉"]

        for i, (name, wins) in enumerate(rows):
            medal = medals[i] if i < 3 else f"{i + 1}."
            result += f"{medal} {name} — {wins} برد\n"

        await update.message.reply_text(result)
        return

    # انتقال سکه با ریپلای
    match = re.fullmatch(
        r"([0-9۰-۹]+)\s*سکه",
        text
    )if match and update.message.reply_to_message:
        amount_text = match.group(1)

        translation = str.maketrans(
            "۰۱۲۳۴۵۶۷۸۹",
            "0123456789"
        )

        amount = int(amount_text.translate(translation))

        if amount <= 0:
            return

        target = update.message.reply_to_message.from_user

        if target.is_bot:
            await update.message.reply_text(
                "❌ نمی‌توانی به ربات سکه بدهی."
            )
            return

        add_user(target)

        sender_coins = get_coins(user.id)

        if sender_coins < amount:
            await update.message.reply_text(
                f"❌ موجودی کافی نیست.\n"
                f"🪙 موجودی شما: {sender_coins:,}"
            )
            return

        change_coins(user.id, -amount)
        change_coins(target.id, amount)

        await update.message.reply_text(
            f"💸 انتقال انجام شد!\n\n"
            f"👤 فرستنده: {user.full_name}\n"
            f"👤 گیرنده: {target.full_name}\n"
            f"🪙 مقدار: {amount:,} سکه"
        )
        return

    # دستورات مالک
    if await is_owner(update):

        # دادن سکه با ریپلای
        match = re.fullmatch(
            r"(?:دادن|افزایش)\s*([0-9۰-۹]+)\s*سکه",
            text
        )

        if match and update.message.reply_to_message:
            amount_text = match.group(1)

            translation = str.maketrans(
                "۰۱۲۳۴۵۶۷۸۹",
                "0123456789"
            )

            amount = int(amount_text.translate(translation))

            target = update.message.reply_to_message.from_user

            add_user(target)
            change_coins(target.id, amount)

            await update.message.reply_text(
                f"👑 انجام شد.\n"
                f"👤 {target.full_name}\n"
                f"🪙 +{amount:,} سکه"
            )
            return

        # گرفتن سکه با ریپلای
        match = re.fullmatch(
            r"(?:کم کردن|کاهش)\s*([0-9۰-۹]+)\s*سکه",
            text
        )

        if match and update.message.reply_to_message:
            amount_text = match.group(1)

            translation = str.maketrans(
                "۰۱۲۳۴۵۶۷۸۹",
                "0123456789"
            )

            amount = int(amount_text.translate(translation))

            target = update.message.reply_to_message.from_user

            add_user(target)

            current = get_coins(target.id)
            amount = min(amount, current)

            change_coins(target.id, -amount)

            await update.message.reply_text(
                f"👑 انجام شد.\n"
                f"👤 {target.full_name}\n"
                f"🪙 -{amount:,} سکه"
            )
            return


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "🎮 ربات بازی و سکه فعال است!\n\n"
        "🪙 موجودی\n"
        "🏆 لیدربورد\n"
        "🏆 لیدربورد برد\n\n"
        "برای بازی‌ها به‌زودی آماده می‌شویم."
    )


def main():
    init_db()

    app = Application.builder().token(TOKEN).build()

    app.add_handler(CommandHandler("start", start))

    app.add_handler(
        MessageHandler(
            filters.TEXT & ~filters.COMMAND,
            message_handler
        )
    )

    print("Bot is running...")

    app.run_polling()


if name == "main":
    main()
