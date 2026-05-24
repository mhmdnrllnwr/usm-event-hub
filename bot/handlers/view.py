from telegram import Update, InlineKeyboardMarkup, InlineKeyboardButton
from telegram.ext import ContextTypes
from api_client import fetch_event, fetch_image
from helpers import format_event, is_admin
from keyboards import main_menu_markup


async def handle_view_event(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    parts = q.data.split("|")
    event_id = parts[1]

    event = await fetch_event(event_id)
    if not event:
        await q.edit_message_text("❌ Event not found.", reply_markup=main_menu_markup(update.effective_user.id))
        return

    text = format_event(event)
    uid = update.effective_user.id
    creator = event.get("creator_id")
    can_edit = uid == creator or is_admin(uid)

    buttons = []
    image = event.get("image_url")
    if image:
        buttons.append([InlineKeyboardButton("\U0001f4f8 View Selected Event", callback_data=f"poster|{event_id}")])

    if can_edit:
        buttons.append([InlineKeyboardButton("✏️ Edit", callback_data=f"edit|start|{event_id}"),
                        InlineKeyboardButton("\U0001f5d1 Delete", callback_data=f"delete|confirm|{event_id}")])

    has_batch = bool(context.user_data.get("batch_summary_msg_id"))
    if has_batch:
        buttons.append([InlineKeyboardButton("\U0001f519 Back to Batch", callback_data="batch|back_to_summary")])
    else:
        buttons.append([InlineKeyboardButton("\U0001f519 Back to List", callback_data="menu")])

    await q.edit_message_text(
        text, reply_markup=InlineKeyboardMarkup(buttons), parse_mode="HTML", disable_web_page_preview=True,
    )


async def handle_view_poster(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    parts = q.data.split("|")
    event_id = parts[1]

    event = await fetch_event(event_id)
    if not event:
        await q.edit_message_text("❌ Event not found.", reply_markup=main_menu_markup(update.effective_user.id))
        return

    image = event.get("image_url")
    if not image:
        await q.answer("No poster available.", show_alert=True)
        return

    raw_text = event.get("raw_text", "")
    caption = raw_text[:1024] if raw_text else None

    image_url = f"http://api:8000{image}"
    content = await fetch_image(image_url)
    if content:
        await q.message.reply_photo(photo=content, caption=caption)
    else:
        await q.answer("Failed to load poster.", show_alert=True)
