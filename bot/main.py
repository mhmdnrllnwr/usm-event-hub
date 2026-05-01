import os
import requests
import logging
from telegram import Update
from telegram.ext import ApplicationBuilder, ContextTypes, MessageHandler, filters

# Setup logging to see what's happening in Docker logs
logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)

# Configuration
TOKEN = os.getenv("BOT_TOKEN")
# Note: We use 'api' as the hostname because they are in the same Docker network
API_URL = "http://api:8000/events/process" 

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message or not update.message.text:
        return

    raw_text = update.message.text
    logging.info(f"📥 Received: {raw_text[:30]}...")

    # Show a "typing" status in Telegram so the user knows the bot is thinking
    await context.bot.send_chat_action(chat_id=update.effective_chat.id, action="typing")

    try:
        response = requests.post(API_URL, json={"text": raw_text})
        
        if response.status_code == 200:
            # Parse the response from your FastAPI
            data = response.json()
            extracted = data.get("extracted_data", {})
            title = extracted.get("title", "Unknown Event")
            event_id = data.get("id", "N/A")

            logging.info(f"✅ Success: {title}")
            
            # Send success reply
            await update.message.reply_text(
                f"✅ **Event Captured!**\n\n"
                f"📍 **Title:** {title}\n"
                f"📅 **Date:** {extracted.get('start_date')}\n"
                f"💰 **Fee:** {extracted.get('fee')}\n\n"
                f"Stored in Vault with ID: `{event_id}`",
                parse_mode="Markdown"
            )
        else:
            logging.error(f"❌ API Error: {response.text}")
            await update.message.reply_text("⚠️ The Brain encountered an error processing this message.")

    except Exception as e:
        logging.error(f"❌ Connection Error: {e}")
        await update.message.reply_text("🔌 Connection Error: I couldn't reach the Event Hub Brain.")
        
if __name__ == '__main__':
    if not TOKEN:
        print("Error: BOT_TOKEN not found in environment variables!")
        exit(1)

    application = ApplicationBuilder().token(TOKEN).build()
    
    # This handler tells the bot to listen to all TEXT messages
    message_handler = MessageHandler(filters.TEXT & (~filters.COMMAND), handle_message)
    application.add_handler(message_handler)
    
    logging.info("🤖 Bot is now listening for USM events...")
    application.run_polling()