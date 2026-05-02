import os
import httpx
import logging
from telegram import Update, ReplyKeyboardMarkup, InlineKeyboardMarkup, InlineKeyboardButton
from telegram.ext import (
    ApplicationBuilder, 
    ContextTypes, 
    MessageHandler, 
    CommandHandler,
    ConversationHandler,
    CallbackQueryHandler,
    filters
)

# Setup logging
logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)

TOKEN = os.getenv("BOT_TOKEN")
API_URL = "http://api:8000/events" 
PROCESS_URL = "http://api:8000/events/process"

SEARCHING = 1

# --- BOT MENU STATE ---
def get_main_menu():
    keyboard = [['📅 All Events', '🔍 Search Event']]
    return ReplyKeyboardMarkup(keyboard, resize_keyboard=True)

def get_inline_filters(current_filter="none"):
    btn_free = InlineKeyboardButton("🆓 Free Only", callback_data="filter:free")
    btn_mycsd = InlineKeyboardButton("🌟 MyCSD Provided", callback_data="filter:mycsd")
    btn_all = InlineKeyboardButton("🔄 Show All", callback_data="filter:none")
    
    if current_filter == "free":
        keyboard = [[btn_mycsd], [btn_all]]
    elif current_filter == "mycsd":
        keyboard = [[btn_free], [btn_all]]
    else:
        keyboard = [[btn_free, btn_mycsd]]
        
    return InlineKeyboardMarkup(keyboard)

def format_event(event) -> str:
    time_str = f"{event.get('start_time', 'TBD')} - {event.get('end_time', 'TBD')}"
    return (
        f"📅 **{event.get('title', 'Unknown Event')}**\n"
        f"━━━━━━━━━━━━━━━━━━\n"
        f"🗓 **Date:** {event.get('start_date', 'TBD')} to {event.get('end_date', 'TBD')}\n"
        f"🕒 **Time:** {time_str}\n"
        f"💰 **Fee:** {event.get('fee', 'Unknown')}\n"
        f"📍 **Venue:** {event.get('venue', 'TBD')}\n"
        f"🌟 **MyCSD:** {'Yes' if event.get('has_mycsd') else 'No'}\n"
        f"🔗 **Link:** [Register/More Info]({event.get('registration_link', 'https://t.me/usm_hub')})\n"
    )

async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "Welcome to the USM Event Hub!\nUse the menu below to discover events.",
        reply_markup=get_main_menu()
    )

async def fetch_and_send_events(update: Update, query_params: dict, filter_type: str = "none"):
    chat_id = update.effective_chat.id
    message_to_edit = update.callback_query.message if update.callback_query else None

    async with httpx.AsyncClient() as client:
        try:
            response = await client.get(API_URL, params=query_params)
            data = response.json()
            events = data.get("events", [])
            
            if not events:
                text = "No events found matching your criteria. 😔"
                if message_to_edit:
                    await message_to_edit.edit_text(text, reply_markup=get_inline_filters(filter_type))
                else:
                    await update.message.reply_text(text, reply_markup=get_inline_filters(filter_type))
                return

            text = f"Found {len(events)} event(s):\n\n"
            for ev in events:
                text += format_event(ev) + "\n"

            if message_to_edit:
                await message_to_edit.edit_text(
                    text, parse_mode="Markdown", 
                    reply_markup=get_inline_filters(filter_type),
                    disable_web_page_preview=True
                )
            else:
                await update.message.reply_text(
                    text, parse_mode="Markdown", 
                    reply_markup=get_inline_filters(filter_type),
                    disable_web_page_preview=True
                )

        except Exception as e:
            logging.error(f"Failed to fetch events: {e}")
            if message_to_edit:
                await message_to_edit.edit_text("❌ Error contacting the API.", reply_markup=get_inline_filters(filter_type))
            else:
                await update.message.reply_text("❌ Error contacting the API.", reply_markup=get_main_menu())


# --- MENU HANDLERS ---
async def handle_menu_all_events(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await fetch_and_send_events(update, {}, filter_type="none")

async def handle_menu_search(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("What are you looking for? Type a keyword (e.g. 'Hackathon'):")
    return SEARCHING

async def handle_search_input(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyword = update.message.text
    await update.message.reply_text(f"Searching for '{keyword}'...")
    await fetch_and_send_events(update, {"search": keyword}, filter_type="none")
    return ConversationHandler.END

async def handle_cancel_search(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Search cancelled.", reply_markup=get_main_menu())
    return ConversationHandler.END

async def handle_inline_filters(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    filter_data = query.data.split(":")[1] # "free", "mycsd", or "none"
    params = {}
    
    if filter_data == "free":
        params["fee"] = "free"
    elif filter_data == "mycsd":
        params["has_mycsd"] = True
        
    await fetch_and_send_events(update, params, filter_type=filter_data)


# --- OLD UPLOAD HANDLER (PUSH) ---
async def handle_push_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    raw_text = ""
    file_id = None

    if update.message.photo:
        file_id = update.message.photo[-1].file_id
        raw_text = update.message.caption or ""
    elif update.message.text:
        raw_text = update.message.text

    if not raw_text:
        return

    await context.bot.send_chat_action(chat_id=update.effective_chat.id, action="typing")

    async with httpx.AsyncClient() as client:
        try:
            payload = {"text": raw_text, "image_url": file_id}
            response = await client.post(PROCESS_URL, json=payload)
            
            if response.status_code == 200:
                data = response.json()
                ext = data.get("extracted_data", {})
                
                time_str = f"{ext.get('start_time', 'TBD')} - {ext.get('end_time', 'TBD')}"
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

                if file_id:
                    await update.message.reply_photo(photo=file_id, caption=reply_markup, parse_mode="Markdown")
                else:
                    await update.message.reply_text(reply_markup, parse_mode="Markdown", disable_web_page_preview=True)
            elif response.status_code == 409:
                await update.message.reply_text("⚠️ **Event already exists!**", parse_mode="Markdown")
            else:
                await update.message.reply_text("❌ **Failed to process event.**")
        except Exception as e:
            logging.error(f"Error handling push: {e}")
            await update.message.reply_text("🔌 Connection Error: API is offline or an error occurred.")


if __name__ == '__main__':
    application = ApplicationBuilder().token(TOKEN).build()
    
    # Handlers
    application.add_handler(CommandHandler("start", start_command))
    application.add_handler(CallbackQueryHandler(handle_inline_filters, pattern="^filter:"))
    application.add_handler(MessageHandler(filters.Regex("^📅 All Events$"), handle_menu_all_events))
    
    conv_handler = ConversationHandler(
        entry_points=[MessageHandler(filters.Regex("^🔍 Search Event$"), handle_menu_search)],
        states={
            SEARCHING: [MessageHandler(filters.TEXT & ~filters.COMMAND, handle_search_input)],
        },
        fallbacks=[CommandHandler("cancel", handle_cancel_search)]
    )
    application.add_handler(conv_handler)
    
    # Push/Upload Handler for everything else (as long as it's not a command or matching above)
    application.add_handler(MessageHandler((filters.TEXT | filters.PHOTO) & ~filters.COMMAND, handle_push_message))
    
    logging.info("Bot is running...")
    application.run_polling()