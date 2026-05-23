import html
import httpx
from telegram import Update, InlineKeyboardMarkup, InlineKeyboardButton
from telegram.ext import ContextTypes
from config import API_URL, ITEMS_PER_PAGE
from api_client import fetch_events
from helpers import format_event
from keyboards import main_menu_markup


async def send_main_menu(update: Update, context: ContextTypes.DEFAULT_TYPE, text: str = None):
    uid = update.effective_user.id
    if text:
        msg = text
        kb = main_menu_markup(uid)
        if update.callback_query:
            await update.callback_query.edit_message_text(msg, reply_markup=kb, parse_mode="HTML")
        elif update.message:
            await update.message.reply_text(msg, reply_markup=kb, parse_mode="HTML")
        return

    data = await fetch_events({"per_page": 50})
    if data is None:
        msg = "❌ Error contacting API."
        kb = main_menu_markup(uid)
        if update.callback_query:
            await update.callback_query.edit_message_text(msg, reply_markup=kb, parse_mode="HTML")
        elif update.message:
            await update.message.reply_text(msg, reply_markup=kb, parse_mode="HTML")
        return

    events = data.get("events", [])
    total = data.get("total", 0)

    if not events:
        msg = "\U0001f645 No events yet.\n\nForward an event announcement to add one!"
        kb = main_menu_markup(uid)
        if update.callback_query:
            await update.callback_query.edit_message_text(msg, reply_markup=kb, parse_mode="HTML")
        elif update.message:
            await update.message.reply_text(msg, reply_markup=kb, parse_mode="HTML")
        return

    lines = [f"<b>Events</b> — {total} total\n"]
    for ev in events:
        title = ev.get("title", "?")
        status = ev.get("status", "?")
        icon = {"active": "\U0001f7e2", "expired": "\U0001f534", "upcoming": "\U0001f7e1"}
        s = icon.get(status, "\U0001f7e1")
        lines.append(f"{s} <code>{html.escape(str(ev['_id'])[-6:])}</code> {html.escape(title)}")
    event_text = "\n".join(lines)

    kb_buttons = []
    for ev in events[:5]:
        short_id = ev["_id"]
        kb_buttons.append([InlineKeyboardButton(f"✏️ {ev.get('title', '?')[:30]}", callback_data=f"edit|start|{short_id}")])

    menu_rows = main_menu_markup(uid).inline_keyboard
    kb_buttons.extend(menu_rows)

    reply_kb = InlineKeyboardMarkup(kb_buttons)

    if update.callback_query:
        msg_obj = update.callback_query.message
        if msg_obj and msg_obj.text:
            await update.callback_query.edit_message_text(
                event_text, reply_markup=reply_kb, parse_mode="HTML", disable_web_page_preview=True,
            )
        else:
            await update.callback_query.message.reply_text(
                event_text, reply_markup=reply_kb, parse_mode="HTML", disable_web_page_preview=True,
            )
    elif update.message:
        await update.message.reply_text(
            event_text, reply_markup=reply_kb, parse_mode="HTML", disable_web_page_preview=True,
        )


async def handle_close(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    await q.delete_message()
