import html
from telegram import Update, InlineKeyboardMarkup, InlineKeyboardButton
from telegram.ext import ContextTypes
from config import IDLE, EDIT_FIELD
from api_client import fetch_event, update_event
from keyboards import main_menu_markup, edit_field_keyboard

EDIT_FIELDS = [
    ("title", "\U0001f4dd Title"),
    ("start_date", "\U0001f5d3 Start Date"),
    ("end_date", "\U0001f5d3 End Date"),
    ("start_time", "\U0001f552 Start Time"),
    ("end_time", "\U0001f552 End Time"),
    ("venue", "\U0001f4cd Venue"),
    ("fee", "\U0001f4b0 Fee"),
    ("registration_link", "\U0001f517 Reg. Link"),
    ("has_mycsd", "\U0001f31f MyCSD"),
]


async def handle_edit_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    parts = q.data.split("|")
    event_id = parts[2]

    event = await fetch_event(event_id)
    if not event:
        await q.edit_message_text("❌ Event not found.")
        return

    title = event.get("title", "?")
    context.user_data["edit_event_id"] = event_id
    context.user_data["edit_updates"] = {}

    text = f"✏️ Edit <b>{html.escape(title)}</b>\n\nChoose field to edit:"
    await q.edit_message_text(text, reply_markup=edit_field_keyboard(event_id, EDIT_FIELDS), parse_mode="HTML")
    return IDLE


async def handle_edit_field_pick(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    parts = q.data.split("|")
    field = parts[2]
    event_id = parts[3]
    context.user_data["edit_field"] = field
    context.user_data["edit_event_id"] = event_id

    field_labels = dict(EDIT_FIELDS)
    label = field_labels.get(field, field)

    if field == "has_mycsd":
        updates = context.user_data.get("edit_updates", {})
        current = updates.get("has_mycsd", False)
        updates["has_mycsd"] = not current
        context.user_data["edit_updates"] = updates
        await q.answer(f"MyCSD set to {not current}", show_alert=True)
        return await show_edit_picker(update, context, event_id)

    await q.edit_message_text(
        f"Send me the new <b>{label}</b>:\n\nOr /cancel to cancel.",
        parse_mode="HTML",
    )
    return EDIT_FIELD


async def handle_edit_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    field = context.user_data.get("edit_field")
    event_id = context.user_data.get("edit_event_id")
    value = update.message.text.strip()

    if not value:
        await update.message.reply_text("Value cannot be empty. Try again or /cancel.")
        return EDIT_FIELD

    updates = context.user_data.get("edit_updates", {})
    updates[field] = value
    context.user_data["edit_updates"] = updates

    await update.message.reply_text(f"✅ {field} updated.", reply_markup=edit_field_keyboard(event_id, EDIT_FIELDS))
    return IDLE


async def show_edit_picker(update: Update, context: ContextTypes.DEFAULT_TYPE, event_id: str):
    q = update.callback_query
    await q.edit_message_text(
        "✏️ Choose field to edit:",
        reply_markup=edit_field_keyboard(event_id, EDIT_FIELDS),
    )
    return IDLE


async def handle_edit_done(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    event_id = context.user_data.get("edit_event_id")
    updates = context.user_data.get("edit_updates", {})

    has_batch = bool(context.user_data.get("batch_summary_msg_id"))

    if not updates:
        markup = InlineKeyboardMarkup([
            [InlineKeyboardButton("Back to Batch Summary", callback_data="batch|back_to_summary")],
        ]) if has_batch else main_menu_markup(update.effective_user.id)
        await q.edit_message_text("No changes made.", reply_markup=markup)
        context.user_data.pop("edit_event_id", None)
        context.user_data.pop("edit_updates", None)
        context.user_data.pop("edit_field", None)
        return IDLE

    success, err = await update_event(event_id, updates)
    if success:
        buttons = [[InlineKeyboardButton("View Event", callback_data=f"view|{event_id}")]]
        if has_batch:
            buttons.append([InlineKeyboardButton("Back to Batch Summary", callback_data="batch|back_to_summary")])
        else:
            buttons.append([InlineKeyboardButton("Main Menu", callback_data="menu")])
        await q.edit_message_text(
            "✅ Event updated successfully!",
            reply_markup=InlineKeyboardMarkup(buttons),
        )
    else:
        markup = InlineKeyboardMarkup([
            [InlineKeyboardButton("Back to Batch Summary", callback_data="batch|back_to_summary")],
        ]) if has_batch else main_menu_markup(update.effective_user.id)
        await q.edit_message_text(
            f"❌ Update failed: {err}",
            reply_markup=markup,
        )

    context.user_data.pop("edit_event_id", None)
    context.user_data.pop("edit_updates", None)
    context.user_data.pop("edit_field", None)
    return IDLE


async def handle_edit_cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data.pop("edit_event_id", None)
    context.user_data.pop("edit_updates", None)
    context.user_data.pop("edit_field", None)
    await update.message.reply_text("Edit cancelled.", reply_markup=main_menu_markup(update.effective_user.id))
    return IDLE


async def handle_edit_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    parts = q.data.split("|")
    action = parts[1] if len(parts) > 1 else ""

    if action == "start":
        return await handle_edit_start(update, context)
    elif action == "field":
        return await handle_edit_field_pick(update, context)
    elif action == "done":
        return await handle_edit_done(update, context)
    return IDLE
