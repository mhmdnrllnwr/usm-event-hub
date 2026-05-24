import logging
from telegram import Update, InlineKeyboardMarkup, InlineKeyboardButton
from telegram.ext import ContextTypes
from helpers import format_event_compact, format_event, is_admin
from api_client import fetch_event
from keyboards import main_menu_markup

logger = logging.getLogger(__name__)


async def batch_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if context.user_data.get("batch_mode"):
        context.user_data["batch_mode"] = False
        context.user_data.pop("batch_results", None)
        context.user_data.pop("batch_summary_msg_id", None)
        await update.message.reply_text("Batch mode OFF. Events now show full cards.")
    else:
        context.user_data["batch_mode"] = True
        context.user_data["batch_results"] = []
        await update.message.reply_text(
            "🚀 <b>Batch mode ON.</b>\n\n"
            "Forward events one by one. I'll collect them silently.\n"
            "Send <b>/done</b> when finished to see the summary.",
            parse_mode="HTML",
        )


def _format_batch_event(data: dict, idx: int = 0) -> str:
    ext = data.get("extracted_data", {}) or {}
    if not ext and data.get("title"):
        ext = data
    flat = {
        "title": ext.get("title"),
        "status": ext.get("status"),
        "start_date": ext.get("start_date"),
        "end_date": ext.get("end_date"),
        "start_time": ext.get("start_time"),
        "end_time": ext.get("end_time"),
        "fee": ext.get("fee"),
        "venue": ext.get("venue"),
        "registration_link": ext.get("registration_link"),
    }
    card = format_event_compact(flat)
    if idx:
        return f"{idx}. {card}"
    return card


async def batch_done_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    results = context.user_data.get("batch_results", [])

    if not results:
        context.user_data["batch_mode"] = False
        context.user_data.pop("batch_results", None)
        context.user_data.pop("batch_summary_msg_id", None)
        await update.message.reply_text("No events in batch. Send /batch to start again.")
        return

    parts = [f"<b>Batch Summary ({len(results)} events)</b>\n"]
    for i, r in enumerate(results, 1):
        if r.get("status") == "saved":
            parts.append(_format_batch_event(r, i) + "\n")
        elif r.get("status") == "duplicate":
            title = r.get("title", "?")
            parts.append(f"⚠️ {title} — duplicate\n")
        else:
            parts.append(f"❌ Event {i} — failed\n")

    text = "\n".join(parts)

    kb = []
    for i, r in enumerate(results, 1):
        eid = r.get("event_id") or (r.get("extracted_data") or {}).get("id") or r.get("id")
        if eid:
            title = r.get("title", f"Event {i}")
            kb.append([
                InlineKeyboardButton(f"View {title[:20]}", callback_data=f"batch|view|{eid}"),
            ])

    kb.append([InlineKeyboardButton("Exit Batch Mode", callback_data="batch|exit")])
    kb.append([InlineKeyboardButton("Close", callback_data="close")])

    msg = await update.message.reply_text(
        text,
        parse_mode="HTML",
        reply_markup=InlineKeyboardMarkup(kb),
        disable_web_page_preview=True,
    )

    # Keep results for back-nav
    context.user_data["batch_summary_msg_id"] = msg.message_id
    context.user_data["batch_summary_chat_id"] = msg.chat_id
    context.user_data["batch_mode"] = False


async def _render_batch_summary(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    results = context.user_data.get("batch_results", [])

    if not results:
        await q.edit_message_text("Batch session expired. Send /batch to start again.")
        return

    parts = [f"<b>Batch Summary ({len(results)} events)</b>\n"]
    for i, r in enumerate(results, 1):
        if r.get("status") == "saved":
            parts.append(_format_batch_event(r, i) + "\n")
        elif r.get("status") == "duplicate":
            title = r.get("title", "?")
            parts.append(f"⚠️ {title} — duplicate\n")
        else:
            parts.append(f"❌ Event {i} — failed\n")

    text = "\n".join(parts)

    kb = []
    for i, r in enumerate(results, 1):
        eid = r.get("event_id") or (r.get("extracted_data") or {}).get("id") or r.get("id")
        if eid:
            title = r.get("title", f"Event {i}")
            kb.append([
                InlineKeyboardButton(f"View {title[:20]}", callback_data=f"batch|view|{eid}"),
            ])

    kb.append([InlineKeyboardButton("Exit Batch Mode", callback_data="batch|exit")])
    kb.append([InlineKeyboardButton("Close", callback_data="close")])

    await q.edit_message_text(
        text,
        parse_mode="HTML",
        reply_markup=InlineKeyboardMarkup(kb),
        disable_web_page_preview=True,
    )


async def handle_batch_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    data = q.data

    if data == "batch|exit":
        context.user_data["batch_mode"] = False
        context.user_data.pop("batch_results", None)
        context.user_data.pop("batch_summary_msg_id", None)
        context.user_data.pop("batch_summary_chat_id", None)
        await q.answer()
        await q.edit_message_text("Batch mode OFF. Events now show full cards.")

    elif data == "batch|summary":
        await q.answer()
        await _render_batch_summary(update, context)

    elif data.startswith("batch|view|"):
        await q.answer()
        parts = data.split("|")
        eid = parts[2]
        event = await fetch_event(eid)
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
            buttons.append([InlineKeyboardButton("View Poster", callback_data=f"poster|{eid}")])
        if can_edit:
            buttons.append([
                InlineKeyboardButton("Edit", callback_data=f"edit|start|{eid}"),
                InlineKeyboardButton("Delete", callback_data=f"delete|confirm|{eid}"),
            ])
        buttons.append([InlineKeyboardButton("Back to Batch", callback_data="batch|back_to_summary")])
        await q.edit_message_text(
            text, reply_markup=InlineKeyboardMarkup(buttons),
            parse_mode="HTML", disable_web_page_preview=True,
        )

    elif data == "batch|back_to_summary":
        await q.answer()
        await _render_batch_summary(update, context)