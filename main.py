import os
import sqlite3
import random
import logging
import datetime
import re
from zoneinfo import ZoneInfo

from dotenv import load_dotenv
from telegram import Update
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    ContextTypes,
    filters,
    JobQueue,  # <-- Added explicit import for JobQueue
)

from groq import Groq

# ---- CONFIG ----
load_dotenv()
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
GROQ_API_KEY = os.getenv("GROQ_API_KEY")

DB_PATH = "subscribers.db"
TIMEZONE = "Asia/Kolkata"

# ---- LOGGING ----
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# ---- QUOTES ----
QUOTES = [
    "The only way to do great work is to love what you do. — Steve Jobs",
    "Don't watch the clock; do what it does. Keep going. — Sam Levenson",
    "Believe you can and you're halfway there. — Theodore Roosevelt",
    "Start where you are. Use what you have. Do what you can. — Arthur Ashe",
    "Do something today that your future self will thank you for.",
    "Small progress is still progress. Keep going.",
    "Difficult roads often lead to beautiful destinations.",
    "You are capable of amazing things.",
    "Mistakes are proof that you are trying.",
    "Focus on progress, not perfection."
]

# ---- DB HELPERS ----
def init_db():
    """Initializes the SQLite database table for subscribers."""
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute(
        """
        CREATE TABLE IF NOT EXISTS subscribers (
            chat_id INTEGER PRIMARY KEY,
            first_name TEXT,
            timezone TEXT
        )
        """
    )
    conn.commit()
    conn.close()


def add_subscriber(chat_id: int, first_name: str, tz: str = TIMEZONE):
    """Adds a new chat ID to the subscribers table."""
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute(
        "INSERT OR IGNORE INTO subscribers (chat_id, first_name, timezone) VALUES (?, ?, ?)",
        (chat_id, first_name, tz),
    )
    conn.commit()
    conn.close()


def remove_subscriber(chat_id: int):
    """Removes a chat ID from the subscribers table."""
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("DELETE FROM subscribers WHERE chat_id = ?", (chat_id,))
    conn.commit()
    conn.close()


def get_subscribers():
    """Returns a list of all subscriber chat IDs."""
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("SELECT chat_id FROM subscribers")
    rows = c.fetchall()
    conn.close()
    return [r[0] for r in rows]


# ---- AI (Groq) ----
# Initialize Groq client
if GROQ_API_KEY:
    groq_client = Groq(api_key=GROQ_API_KEY)
else:
    logger.error("GROQ_API_KEY not found in .env. AI features disabled.")
    groq_client = None

USER_CONTEXT = {}
MAX_HISTORY = 5

def chat_with_groq(chat_id: int, user_message: str) -> str:
    """Send user message + context to Groq and return AI reply."""
    if not groq_client:
        return "Sorry, my AI chat service is currently unavailable. But remember: You've got this!"
        
    history = USER_CONTEXT.get(chat_id, [])

    messages = [{"role": "system", "content":
        "You are a kind motivational assistant. "
        "Reply in 2-3 sentences, always positive, encouraging, and supportive. "
        "If user is stressed, give calming and simple tips."
    }]
    for role, msg in history:
        messages.append({"role": role, "content": msg})
    messages.append({"role": "user", "content": user_message})

    try:
        resp = groq_client.chat.completions.create(
            model="llama-3.1-8b-instant",
            messages=messages,
            max_tokens=120,
            temperature=0.7,
        )
        reply = resp.choices[0].message.content.strip()
    except Exception as e:
        logger.error(f"Groq error: {e}")
        reply = "I'm here for you 💙. Take a deep breath and remember you're doing your best."

    # update history
    history.append(("user", user_message))
    history.append(("assistant", reply))
    # Keep only the last few messages for context
    USER_CONTEXT[chat_id] = history[-MAX_HISTORY*2:] 
    return reply


# ---- HANDLERS ----
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Sends a welcome message and lists commands."""
    user = update.effective_user
    text = (
        f"Hi {user.first_name}! 👋\n\n"
        "I'm your Motivational Bot.\n\n"
        "Commands:\n"
        "/subscribe - Receive daily motivational message (every morning)\n"
        "/unsubscribe - Stop daily messages\n"
        "/quote - Get a random motivational quote now\n"
        "/help - Show this message\n\n"
        "You can also just chat with me if you're stressed or need motivation."
    )
    await update.message.reply_text(text)


async def help_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Sends the help message."""
    await start(update, context)


async def subscribe(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Subscribes the user to the daily job."""
    chat_id = update.effective_chat.id
    first_name = update.effective_user.first_name or ""
    add_subscriber(chat_id, first_name)
    await update.message.reply_text(
        "You're subscribed ✅\n"
        "You'll get a motivational message every day at 9 AM IST.\n"
        "Use /unsubscribe to stop."
    )


async def unsubscribe(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Unsubscribes the user from the daily job."""
    chat_id = update.effective_chat.id
    remove_subscriber(chat_id)
    await update.message.reply_text("You've been unsubscribed. Use /subscribe to join again.")


async def quote_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Sends a random motivational quote immediately."""
    quote = random.choice(QUOTES)
    await update.message.reply_text(f"🌟 {quote}")


async def text_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handles regular text messages and responds using Groq."""
    text = (update.message.text or "").strip()
    if not text:
        return

    chat_id = update.effective_chat.id
    reply = chat_with_groq(chat_id, text)
    await update.message.reply_text(reply)


async def error_handler(update: object, context: ContextTypes.DEFAULT_TYPE):
    """Logs Errors caused by Updates."""
    logger.error("Error: %s", context.error)


# ---- DAILY JOB ----
async def send_daily_messages(context: ContextTypes.DEFAULT_TYPE):
    """The scheduled job that sends daily motivational messages to all subscribers."""
    # Note: Using TIMEZONE for the initial scheduling time is correct, 
    # but the message sends immediately when the scheduled time hits 
    # *in the bot's environment*. The message content is timezone-agnostic here.
    quote = random.choice(QUOTES)
    message = f"Good morning! 🌞\n\n{quote}\n\nHave a great day! 💪"

    subs = get_subscribers()
    logger.info("Sending daily message to %d subscribers", len(subs))
    for chat_id in subs:
        try:
            # We use context.bot.send_message here because the job is not associated 
            # with a specific update object, but with the application's bot instance.
            await context.bot.send_message(chat_id=chat_id, text=message)
        except Exception as e:
            logger.warning("Failed to send to %s: %s", chat_id, e)


# ---- MAIN ----
def main():
    """Starts the bot."""
    if not TELEGRAM_TOKEN:
        raise RuntimeError("TELEGRAM_TOKEN not found in .env")

    init_db()

    app = (
        Application.builder()
        .token(TELEGRAM_TOKEN)
        .build()
    )

    # Handlers
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("help", help_cmd))
    app.add_handler(CommandHandler("subscribe", subscribe))
    app.add_handler(CommandHandler("unsubscribe", unsubscribe))
    app.add_handler(CommandHandler("quote", quote_cmd))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, text_handler))

    app.add_error_handler(error_handler)

    # Schedule daily motivational messages at 9 AM IST
    tz = ZoneInfo(TIMEZONE)
    app.job_queue.run_daily(send_daily_messages, time=datetime.time(9, 0, tzinfo=tz))

    logger.info("Bot starting... Polling.")
    app.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    main()
