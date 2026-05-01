import os
import requests
import logging
from telegram import Update
from telegram.ext import ApplicationBuilder, ContextTypes, MessageHandler, filters

# Setup logging
logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)

TOKEN = os.getenv("BOT_TOKEN")
API_URL = "http://api:8000/events/process" 

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    raw_text = ""
    file_id = None

    # 1. Capture content
    if update.message.photo:
        file_id = update.message.photo[-1].file_id
        raw_text = update.message.caption or ""
    elif update.message.text:
        raw_text = update.message.text

    if not raw_text:
        return

    await context.bot.send_chat_action(chat_id=update.effective_chat.id, action="typing")

    try:
        # 2. Send to API
        payload = {"text": raw_text, "image_url": file_id}
        response = requests.post(API_URL, json=payload)
        
        if response.status_code == 200:
            data = response.json()
            # This is the event object returned by your FastAPI
            ext = data.get("extracted_data", {})
            
            # Format the time range nicely
            time_str = f"{ext.get('start_time', 'TBD')} - {ext.get('end_time', 'TBD')}"
            
            # 3. Construct the "Event Card"
            reply_markup = (
                f"✅ **EVENT CAPTURED**\n"
                f"━━━━━━━━━━━━━━━━━━\n"
                f"📝 **Title:** {ext.get('title')}\n"
                f"📅 **Start Date:** {ext.get('start_date')}\n"
                f"📅 **End Date:** {ext.get('end_date')}\n"
                f"🕒 **Time:** {time_str}\n"
                f"💰 **Fee:** {ext.get('fee')}\n"
                f"📍 **Venue:** {ext.get('venue')}\n"
                f"🔗 **Link:** {ext.get('registration_link')}\n"
                f"━━━━━━━━━━━━━━━━━━\n"
                f"🆔 `ID: {data.get('id')}`"
            )

            # 4. Reply with Photo if available, otherwise Text
            if file_id:
                await update.message.reply_photo(
                    photo=file_id,
                    caption=reply_markup,
                    parse_mode="Markdown"
                )
            else:
                await update.message.reply_text(
                    reply_markup,
                    parse_mode="Markdown",
                    disable_web_page_preview=True # Keeps the chat clean
                )
        else:
            await update.message.reply_text("❌ Brain Error: Failed to process event.")
            
    except Exception as e:
        logging.error(f"Error: {e}")
        await update.message.reply_text("🔌 Connection Error: API is offline.")

if __name__ == '__main__':
    application = ApplicationBuilder().token(TOKEN).build()
    event_handler = MessageHandler((filters.TEXT | filters.PHOTO) & (~filters.COMMAND), handle_message)
    application.add_handler(event_handler)
    application.run_polling()