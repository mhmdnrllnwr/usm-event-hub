import os
import time
import httpx
import logging
from telegram import Update, ReplyKeyboardMarkup, InlineKeyboardMarkup, InlineKeyboardButton
from telegram.helpers import escape_markdown
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

def wait_for_api():
    max_retries = 30
    for attempt in range(1, max_retries + 1):
        try:
            resp = httpx.get(API_URL, timeout=5)
            if resp.status_code == 200:
                logging.info("API ready")
                return
        except Exception as e:
            logging.warning(f"API not ready (attempt {attempt}/{max_retries}): {e}")
            time.sleep(2)
    logging.error("API not available. Exiting.")
    exit(1)

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

def _format_date(start: str | None, end: str | None) -> str:
    if not start and not end:
        return "empty"
    if start and end and end != start:
        return f"{start} - {end}"
    return start or "empty"

def format_event(event) -> str:
    title = escape_markdown(event.get('title', 'Unknown Event'), version=2)
    date = escape_markdown(_format_date(event.get('start_date'), event.get('end_date')), version=2)

    st_raw = event.get('start_time')
    et_raw = event.get('end_time')
    if st_raw and et_raw:
        st = escape_markdown(st_raw, version=2)
        et = escape_markdown(et_raw, version=2)
        time_str = f"{st} - {et}"
    elif st_raw:
        time_str = escape_markdown(st_raw, version=2)
    else:
        time_str = "empty"

    fee = escape_markdown(event.get('fee') or 'empty', version=2)
    venue = escape_markdown(event.get('venue') or 'empty', version=2)

    link_raw = event.get('registration_link')
    if link_raw:
        link = escape_markdown(str(link_raw), version=2)
        link_line = f"🔗 **Link:** [Register/More Info]({link})"
    else:
        link_line = "🔗 **Link:** empty"

    mycsd = 'Yes' if event.get('has_mycsd') else 'No'
    status = event.get("status", "upcoming")
    status_icon = {"active": "🟢", "expired": "🔴", "upcoming": "🟡"}
    status_badge = f"{status_icon.get(status, '🟡')} **{status.upper()}**\n"
    return (
        f"📅 **{title}**\n"
        f"{status_badge}"
        f"━━━━━━━━━━━━━━━━━━\n"
        f"🗓 **Date:** {date}\n"
        f"🕒 **Time:** {time_str}\n"
        f"💰 **Fee:** {fee}\n"
        f"📍 **Venue:** {venue}\n"
        f"🌟 **MyCSD:** {mycsd}\n"
        f"{link_line}\n"
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
                    text, parse_mode="MarkdownV2",
                    reply_markup=get_inline_filters(filter_type),
                    disable_web_page_preview=True
                )
            else:
                await update.message.reply_text(
                    text, parse_mode="MarkdownV2",
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
                
                st_raw = ext.get('start_time')
                et_raw = ext.get('end_time')
                if st_raw and et_raw:
                    time_str = f"{st_raw} - {et_raw}"
                elif st_raw:
                    time_str = st_raw
                else:
                    time_str = "empty"
                fee_display = ext.get('fee') or "empty"
                venue_display = ext.get('venue') or "empty"
                link_raw = ext.get('registration_link')
                link_display = link_raw if link_raw else "empty"
                status = ext.get("status", "upcoming")
                status_icon = {"active": "🟢", "expired": "🔴", "upcoming": "🟡"}
                status_tag = f"{status_icon.get(status, '🟡')} <b>{status.upper()}</b>\n"
                reply_markup = (
                    f"✅ <b>EVENT CAPTURED</b>\n"
                    f"{status_tag}"
                    f"━━━━━━━━━━━━━━━━━━\n"
                    f"📝 <b>Title:</b> {ext.get('title')}\n"
                    f"📅 <b>Date:</b> {_format_date(ext.get('start_date'), ext.get('end_date'))}\n"
                    f"🕒 <b>Time:</b> {time_str}\n"
                    f"💰 <b>Fee:</b> {fee_display}\n"
                    f"📍 <b>Venue:</b> {venue_display}\n"
                    f"🔗 <b>Link:</b> {link_display}\n"
                    f"━━━━━━━━━━━━━━━━━━\n"
                    f"🆔 <code>ID: {data.get('id')}</code>"
                )

                if file_id:
                    await update.message.reply_photo(photo=file_id, caption=reply_markup, parse_mode="HTML")
                else:
                    await update.message.reply_text(reply_markup, parse_mode="HTML", disable_web_page_preview=True)
            elif response.status_code == 409:
                await update.message.reply_text("⚠️ <b>Event already exists!</b>", parse_mode="HTML")
            else:
                await update.message.reply_text("❌ **Failed to process event.**")
        except Exception as e:
            logging.error(f"Error handling push: {e}")
            await update.message.reply_text("🔌 Connection Error: API is offline or an error occurred.")


if __name__ == '__main__':
    application = ApplicationBuilder().token(TOKEN).build()
    wait_for_api()

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