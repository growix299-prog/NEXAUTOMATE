import os
import sys
import logging
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, MessageHandler, filters

# Setup path so we can import backend packages
sys.path.append(os.path.join(os.path.dirname(__file__), ".."))

# Load .env file from root directory
env_path = os.path.join(os.path.dirname(__file__), "..", ".env")
if os.path.exists(env_path):
    with open(env_path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                k, v = line.split("=", 1)
                os.environ[k.strip()] = v.strip()

from handlers.menu import start_command, handle_callback_query
from handlers.delivery import handle_user_text

# Configure logging
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", 
    level=logging.INFO
)
logger = logging.getLogger(__name__)

BOT_TOKEN = os.getenv("BOT_TOKEN")

def main():
    """Starts the Telegram Bot."""
    if not BOT_TOKEN:
        logger.critical("BOT_TOKEN is not defined in environment variables! Exiting.")
        sys.exit(1)

    logger.info("Initializing Telegram Digital Delivery Bot...")
    
    # Initialize python-telegram-bot application
    application = Application.builder().token(BOT_TOKEN).build()

    # Register handlers
    application.add_handler(CommandHandler("start", start_command))
    application.add_handler(CallbackQueryHandler(handle_callback_query))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_user_text))

    logger.info("Bot is active and polling for new messages...")
    
    # Run the bot polling loop
    application.run_polling()

if __name__ == "__main__":
    main()
