import html
from telegram import Update, InlineKeyboardMarkup, InlineKeyboardButton
from telegram.ext import ContextTypes
from config import ITEMS_PER_PAGE, API_URL
from api_client import fetch_events
from keyboards import browse_filters_keyboard, main_menu_markup
from helpers import is_admin, format_event_compact


def _build_browse_params(filters: dict) -> dict:
    params = {}
    if filters.get("status"):
        params["status"] = filters["status"]
    if filters.get("fee") == "free":
        params["fee"] = "free"
    if filters.get("fee") == "paid":
        params["paid"] = "true"
    if filters.get("mycsd"):
        params["has_mycsd"] = "true"
    return params


def render_event_list(events, page, total_pages, total, header):
    """Build event list text + keyboard. Returns (text, InlineKeyboardMarkup)."""
    lines = [f"<b>{html.escape(header)}</b> — Page {page}/{total_pages} ({total}) total\n"]
    start = (page - 1) * ITEMS_PER_PAGE + 1
    for i, ev in enumerate(events, start):
        lines.append(f"{i}. {format_event_compact(ev)}\n")
    text = "\n".join(lines)

    nav = []
    if page > 1:
        nav.append(InlineKeyboardButton("◀️ Prev", callback_data=f"list_active|{page-1}"))
    if page < total_pages:
        nav.append(InlineKeyboardButton("Next ▶️", callback_data=f"list_active|{page+1}"))

    kb_buttons = [nav] if nav else []
    for ev in events[:5]:
        kb_buttons.append([InlineKeyboardButton(f"\U0001f50d {ev.get('title', '?')[:30]}", callback_data=f"view|{ev['_id']}")])
    kb_buttons.append([InlineKeyboardButton("\U0001f519 Main Menu", callback_data="menu")])
    kb_buttons.append([InlineKeyboardButton("❌ Close", callback_data="close")])

    return text, InlineKeyboardMarkup(kb_buttons)


async def show_browse(update: Update, context: ContextTypes.DEFAULT_TYPE, page: int = 1):
    filters = context.user_data.get("browse_filters", {})
    params = _build_browse_params(filters)
    params["page"] = str(page)
    params["per_page"] = str(ITEMS_PER_PAGE)
    params["sort"] = "date_asc"

    q = update.callback_query
    await q.answer()

    data = await fetch_events(params)
    if data is None:
        await q.edit_message_text("❌ Error contacting API.", reply_markup=main_menu_markup(update.effective_user.id))
        return

    events = data.get("events", [])
    total = data.get("total", 0)
    total_pages = max(1, (total + ITEMS_PER_PAGE - 1) // ITEMS_PER_PAGE)

    if not events:
        text = "\U0001f645 No events found matching your criteria."
        kb = InlineKeyboardMarkup([
            [InlineKeyboardButton("\U0001f504 Reset Filters", callback_data="bfilter|reset")],
            [InlineKeyboardButton("\U0001f519 Back to Menu", callback_data="menu")],
        ])
        await q.edit_message_text(text, reply_markup=kb)
        return

    lines = [f"<b>Events</b> — Page {page}/{total_pages} ({total}) total\n"]
    start = (page - 1) * ITEMS_PER_PAGE + 1
    for i, ev in enumerate(events, start):
        lines.append(f"{i}. {format_event_compact(ev)}\n")

    text = "\n".join(lines)

    nav = []
    if page > 1:
        nav.append(InlineKeyboardButton("◀️ Prev", callback_data=f"browse|{page-1}"))
    if page < total_pages:
        nav.append(InlineKeyboardButton(f"Next ▶️", callback_data=f"browse|{page+1}"))

    action_row = []
    for ev in events[:5]:
        short_id = ev["_id"]
        action_row.append(InlineKeyboardButton(f"\U0001f50d {ev.get('title', '?')[:30]}", callback_data=f"view|{short_id}"))

    kb_buttons = [nav, action_row] if action_row else [nav]
    kb_buttons.append([InlineKeyboardButton("\U0001f519 Back to Menu", callback_data="menu")])
    kb_buttons.append([InlineKeyboardButton("❌ Close", callback_data="close")])

    await q.edit_message_text(
        text, reply_markup=InlineKeyboardMarkup(kb_buttons), parse_mode="HTML", disable_web_page_preview=True,
    )
    context.user_data["browse_page"] = page


async def handle_browse_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    parts = q.data.split("|")
    page = int(parts[1]) if len(parts) > 1 else 1
    await show_browse(update, context, page=page)


async def handle_browse_filter(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    parts = q.data.split("|")
    action = parts[1] if len(parts) > 1 else None
    value = parts[2] if len(parts) > 2 else None

    filters = context.user_data.get("browse_filters", {})

    if action == "reset":
        context.user_data["browse_filters"] = {}
    elif action == "mycsd":
        filters["mycsd"] = not filters.get("mycsd", False)
        context.user_data["browse_filters"] = filters
    elif action == "status":
        if value:
            filters["status"] = value
        else:
            filters.pop("status", None)
        context.user_data["browse_filters"] = filters
    elif action == "fee":
        if value:
            filters["fee"] = value
        else:
            filters.pop("fee", None)
        context.user_data["browse_filters"] = filters

    page = context.user_data.get("browse_page", 1)
    context.user_data["browse_filters"] = context.user_data.get("browse_filters", {})
    if q.message:
        await q.answer("Filters updated")
        await show_browse(update, context, page=page)
    else:
        from .menu import send_main_menu
        await send_main_menu(update, context)


async def handle_list_active(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    parts = q.data.split("|")
    page = int(parts[1]) if len(parts) > 1 else 1

    data = await fetch_events({"per_page": ITEMS_PER_PAGE, "page": page, "status": "active", "sort": "date_asc"})
    if data is None:
        if q.message and q.message.text:
            await q.edit_message_text("❌ Error contacting API.", reply_markup=main_menu_markup(update.effective_user.id))
        else:
            await q.message.reply_text("❌ Error contacting API.", reply_markup=main_menu_markup(update.effective_user.id))
        return

    events = data.get("events", [])
    total = data.get("total", 0)
    total_pages = max(1, (total + ITEMS_PER_PAGE - 1) // ITEMS_PER_PAGE)

    if not events:
        if q.message and q.message.text:
            await q.edit_message_text("\U0001f645 No active events right now.", reply_markup=main_menu_markup(update.effective_user.id))
        else:
            await q.message.reply_text("\U0001f645 No active events right now.", reply_markup=main_menu_markup(update.effective_user.id))
        return

    text, reply_markup = render_event_list(events, page, total_pages, total, "Active Events")

    if q.message and q.message.text:
        await q.edit_message_text(text, reply_markup=reply_markup, parse_mode="HTML", disable_web_page_preview=True)
    else:
        await q.message.reply_text(text, reply_markup=reply_markup, parse_mode="HTML", disable_web_page_preview=True)
