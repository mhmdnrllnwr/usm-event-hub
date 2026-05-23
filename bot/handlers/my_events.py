import html
from telegram import Update, InlineKeyboardMarkup, InlineKeyboardButton
from telegram.ext import ContextTypes
from config import ITEMS_PER_PAGE
from api_client import fetch_events
from keyboards import main_menu_markup


async def handle_my_events(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    uid = update.effective_user.id
    page = 1
    parts = q.data.split("|")
    if len(parts) > 1:
        page = int(parts[1])

    data = await fetch_events({"creator_id": uid, "page": page, "per_page": ITEMS_PER_PAGE})
    if data is None:
        await q.edit_message_text("❌ Error contacting API.", reply_markup=main_menu_markup(uid))
        return

    events = data.get("events", [])
    total = data.get("total", 0)
    total_pages = max(1, (total + ITEMS_PER_PAGE - 1) // ITEMS_PER_PAGE)

    if not events:
        await q.edit_message_text(
            "\U0001f4ed You haven't submitted any events yet.\n\nForward an event announcement to add one!",
            reply_markup=main_menu_markup(uid),
        )
        return

    lines = [f"<b>My Events</b> — Page {page}/{total_pages} ({total}) total\n"]
    for ev in events:
        title = ev.get("title", "?")
        lines.append(f"• {html.escape(title)}")
    text = "\n".join(lines)

    nav = []
    if page > 1:
        nav.append(InlineKeyboardButton("◀️ Prev", callback_data=f"myevents|{page-1}"))
    if page < total_pages:
        nav.append(InlineKeyboardButton(f"Next ▶️", callback_data=f"myevents|{page+1}"))

    actions = []
    for ev in events[:3]:
        eid = ev["_id"]
        actions.append(InlineKeyboardButton(f"\U0001f50d {ev.get('title', '?')[:20]}", callback_data=f"view|{eid}"))

    kb = [nav] if nav else []
    if actions:
        kb.append(actions)
    kb.append([InlineKeyboardButton("\U0001f519 Main Menu", callback_data="menu")])
    kb.append([InlineKeyboardButton("❌ Close", callback_data="close")])

    await q.edit_message_text(text, reply_markup=InlineKeyboardMarkup(kb), parse_mode="HTML")
