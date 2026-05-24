from telegram import Update, InlineKeyboardMarkup, InlineKeyboardButton
from telegram.ext import ContextTypes
from api_client import delete_event
from keyboards import main_menu_markup


async def handle_delete_confirm(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    parts = q.data.split("|")
    event_id = parts[2]

    cancel_data = f"batch|back_to_summary" if context.user_data.get("batch_summary_msg_id") else f"view|{event_id}"

    await q.edit_message_text(
        "❓ Delete this event?\n\nThis cannot be undone.",
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("✅ Yes, delete", callback_data=f"delete|yes|{event_id}"),
             InlineKeyboardButton("❌ Cancel", callback_data=cancel_data)],
        ]),
    )


async def handle_delete_execute(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    parts = q.data.split("|")
    event_id = parts[2]

    success = await delete_event(event_id)
    has_batch = bool(context.user_data.get("batch_summary_msg_id"))
    if has_batch:
        markup = InlineKeyboardMarkup([
            [InlineKeyboardButton("Back to Batch Summary", callback_data="batch|back_to_summary")],
        ])
    else:
        markup = main_menu_markup(update.effective_user.id)

    if success:
        await q.edit_message_text("✅ Event deleted.", reply_markup=markup)
    else:
        await q.edit_message_text("❌ Failed to delete event.", reply_markup=markup)
