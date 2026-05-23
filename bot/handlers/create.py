import html
from telegram import Update, InlineKeyboardMarkup, InlineKeyboardButton
from telegram.ext import ContextTypes
from config import IDLE, CREATE_TITLE, CREATE_FIELD
from api_client import create_event
from keyboards import main_menu_markup, create_field_keyboard

CREATE_FIELDS = [
    ("start_date", "\U0001f5d3 Start Date"),
    ("end_date", "\U0001f5d3 End Date"),
    ("start_time", "\U0001f552 Start Time"),
    ("end_time", "\U0001f552 End Time"),
    ("venue", "\U0001f4cd Venue"),
    ("fee", "\U0001f4b0 Fee"),
    ("registration_link", "\U0001f517 Reg. Link"),
    ("has_mycsd", "\U0001f31f MyCSD"),
]


async def handle_create_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    context.user_data["create_data"] = {}
    await q.edit_message_text("Send the event <b>title</b>:", parse_mode="HTML")
    return CREATE_TITLE


async def handle_create_title(update: Update, context: ContextTypes.DEFAULT_TYPE):
    title = update.message.text.strip()
    if not title:
        await update.message.reply_text("Title cannot be empty\\. Try again or /cancel\\.")
        return CREATE_TITLE

    context.user_data["create_data"] = {"title": title}
    await show_create_field_picker(update, context)
    return CREATE_FIELD


async def show_create_field_picker(update: Update, context: ContextTypes.DEFAULT_TYPE):
    data = context.user_data.get("create_data", {})
    title = data.get("title", "?")
    lines = [f"✅ <b>Title:</b> {html.escape(title)}", "", "Add details or publish:"]
    for key, label in CREATE_FIELDS:
        val = data.get(key)
        if val is not None:
            if key == "has_mycsd":
                lines.append(f"✅ {label}: Yes" if val else f"❌ {label}: No")
            else:
                lines.append(f"✅ {label}: {html.escape(str(val))}")

    text = "\n".join(lines)

    if update.callback_query:
        await update.callback_query.edit_message_text(text, reply_markup=create_field_keyboard(CREATE_FIELDS), parse_mode="HTML")
    elif update.message:
        await update.message.reply_text(text, reply_markup=create_field_keyboard(CREATE_FIELDS), parse_mode="HTML")


async def handle_create_add(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    parts = q.data.split("|")
    field = parts[2]
    context.user_data["create_field"] = field

    if field == "has_mycsd":
        data = context.user_data.get("create_data", {})
        data["has_mycsd"] = not data.get("has_mycsd", False)
        context.user_data["create_data"] = data
        await show_create_field_picker(update, context)
        return CREATE_FIELD

    field_labels = dict(CREATE_FIELDS)
    await q.edit_message_text(
        f"Send the <b>{html.escape(field_labels.get(field, field))}</b>:\n\nOr /cancel to cancel.",
        parse_mode="HTML",
    )
    return CREATE_FIELD


async def handle_create_field_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    field = context.user_data.get("create_field")
    value = update.message.text.strip()

    if not value:
        await update.message.reply_text("Value cannot be empty. Try again or /cancel.")
        return CREATE_FIELD

    data = context.user_data.get("create_data", {})
    data[field] = value
    context.user_data["create_data"] = data

    await show_create_field_picker(update, context)
    return CREATE_FIELD


async def handle_create_save(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()

    data = context.user_data.get("create_data", {})
    if not data.get("title"):
        await q.edit_message_text("Title is required\\.", reply_markup=main_menu_markup(update.effective_user.id))
        context.user_data.pop("create_data", None)
        return IDLE

    payload = {
        "title": data["title"],
        "start_date": data.get("start_date"),
        "end_date": data.get("end_date"),
        "start_time": data.get("start_time"),
        "end_time": data.get("end_time"),
        "venue": data.get("venue"),
        "fee": data.get("fee"),
        "registration_link": data.get("registration_link"),
        "has_mycsd": data.get("has_mycsd", False),
        "creator_id": update.effective_user.id,
        "raw_text": "",
    }

    result, err = await create_event(payload)
    if result:
        eid = result.get("id")
        await q.edit_message_text(
            "✅ <b>Event created successfully!</b>",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("✏️ Edit", callback_data=f"edit|start|{eid}"),
                 InlineKeyboardButton("\U0001f5d1 Delete", callback_data=f"delete|confirm|{eid}")],
            ]),
            parse_mode="HTML",
        )
    else:
        await q.edit_message_text(
            f"❌ <b>Failed:</b> {html.escape(str(err))}",
            reply_markup=main_menu_markup(update.effective_user.id),
            parse_mode="HTML",
        )

    context.user_data.pop("create_data", None)
    context.user_data.pop("create_field", None)
    return IDLE


async def handle_create_cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data.pop("create_data", None)
    context.user_data.pop("create_field", None)
    await update.message.reply_text("Event creation cancelled.", reply_markup=main_menu_markup(update.effective_user.id))
    return IDLE
