import logging
from telegram import Update, InlineKeyboardMarkup, InlineKeyboardButton
from telegram.ext import ContextTypes
from api_client import process_forwarded
from helpers import _format_date

logger = logging.getLogger(__name__)


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

    uid = update.effective_user.id
    await context.bot.send_chat_action(chat_id=update.effective_chat.id, action="typing")

    payload = {"text": raw_text, "image_url": file_id, "creator_id": uid}
    result = await process_forwarded(payload)

    if result is None:
        logger.error("Error handling push: connection error")
        await update.message.reply_text("\U0001f50c Connection Error: API is offline or an error occurred.")
        return

    status_code = result.get("status_code")
    if status_code == 409:
        await update.message.reply_text("⚠️ <b>Event already exists!</b>", parse_mode="HTML")
        return

    if status_code is not None and status_code != 200:
        await update.message.reply_text("❌ Failed to process event.")
        return

    data = result
    ext = data.get("extracted_data", {})
    eid = data.get("id")

    st = ext.get("start_time")
    et = ext.get("end_time")
    time_str = f"{st} – {et}" if st and et else (st or "empty")

    fee_d = ext.get("fee") or "empty"
    venue_d = ext.get("venue") or "empty"
    link_d = ext.get("registration_link") or "empty"
    status = ext.get("status", "upcoming")
    icon = {"active": "\U0001f7e2", "expired": "\U0001f534", "upcoming": "\U0001f7e1"}
    si = icon.get(status, "\U0001f7e1")
    tag = f"{si} <b>{status.upper()}</b>\n"

    reply = (
        f"✅ <b>EVENT CAPTURED</b>\n{tag}"
        f"━━━━━━━━━━━━━━━━━━━━\n"
        f"\U0001f4dd <b>Title:</b> {ext.get('title')}\n"
        f"\U0001f5d3 <b>Date:</b> {_format_date(ext.get('start_date'), ext.get('end_date'))}\n"
        f"\U0001f552 <b>Time:</b> {time_str}\n"
        f"\U0001f4b0 <b>Fee:</b> {fee_d}\n"
        f"\U0001f4cd <b>Venue:</b> {venue_d}\n"
        f"\U0001f517 <b>Link:</b> {link_d}\n"
        f"━━━━━━━━━━━━━━━━━━━━\n"
        f"\U0001f194 <code>ID: {eid}</code>"
    )

    view_kb = InlineKeyboardMarkup([
        [InlineKeyboardButton("✏️ Edit", callback_data=f"edit|start|{eid}"),
         InlineKeyboardButton("\U0001f5d1 Delete", callback_data=f"delete|confirm|{eid}")],
    ])

    if file_id:
        await update.message.reply_photo(photo=file_id, caption=reply, parse_mode="HTML", reply_markup=view_kb)
    else:
        await update.message.reply_text(reply, parse_mode="HTML", disable_web_page_preview=True, reply_markup=view_kb)
