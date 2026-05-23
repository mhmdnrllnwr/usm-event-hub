from telegram import Update, InlineKeyboardMarkup, InlineKeyboardButton
from telegram.ext import ContextTypes
from api_client import delete_event
from keyboards import main_menu_markup


async def handle_delete_confirm(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    parts = q.data.split("|")
    event_id = parts[2]

    await q.edit_message_text(
        "❓ Delete this event?\n\nThis cannot be undone.",
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("✅ Yes, delete", callback_data=f"delete|yes|{event_id}"),
             InlineKeyboardButton("❌ Cancel", callback_data=f"view|{event_id}")],
        ]),
    )


async def handle_delete_execute(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    parts = q.data.split("|")
    event_id = parts[2]

    success = await delete_event(event_id)
    if success:
        await q.edit_message_text("✅ Event deleted.", reply_markup=main_menu_markup(update.effective_user.id))
    else:
        await q.edit_message_text("❌ Failed to delete event.", reply_markup=main_menu_markup(update.effective_user.id))
