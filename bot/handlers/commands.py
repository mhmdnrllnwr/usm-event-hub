from telegram import Update, InlineKeyboardMarkup, InlineKeyboardButton
from telegram.ext import ContextTypes, ConversationHandler
from config import ITEMS_PER_PAGE, IDLE, SEARCHING
from api_client import fetch_events
from helpers import is_admin, format_event_compact
from keyboards import main_menu_markup, admin_markup


async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    intro = (
        "\U0001f44b <b>Welcome to USM Event Hub!</b>\n\n"
        "I collect and organize event announcements from USM.\n\n"
        "Use buttons below to browse events, search, or manage your submissions."
    )
    from .menu import send_main_menu
    await send_main_menu(update, context, text=intro)


async def browse_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    data = await fetch_events({"per_page": ITEMS_PER_PAGE, "page": 1, "status": "active", "sort": "date_asc"})
    if data is None:
        await update.message.reply_text("❌ Error contacting API.", reply_markup=main_menu_markup(update.effective_user.id))
        return

    events = data.get("events", [])
    total = data.get("total", 0)
    total_pages = max(1, (total + ITEMS_PER_PAGE - 1) // ITEMS_PER_PAGE)

    if not events:
        await update.message.reply_text("\U0001f645 No active events right now.", reply_markup=main_menu_markup(update.effective_user.id))
        return

    from .browse import render_event_list
    text, reply_markup = render_event_list(events, 1, total_pages, total, "Active Events")
    await update.message.reply_text(text, reply_markup=reply_markup, parse_mode="HTML", disable_web_page_preview=True)


async def search_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("What are you looking for? Type a keyword (e.g. 'Hackathon'):")
    return SEARCHING


async def handle_search_input(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyword = update.message.text.strip()
    if not keyword:
        await update.message.reply_text("Keyword cannot be empty.")
        return SEARCHING

    await update.message.reply_text(f"Searching for '{keyword}'...")

    data = await fetch_events({"search": keyword, "per_page": ITEMS_PER_PAGE, "sort": "date_asc"})
    if data is None:
        await update.message.reply_text("❌ Error contacting API.", reply_markup=main_menu_markup(update.effective_user.id))
        return ConversationHandler.END

    events = data.get("events", [])
    total = data.get("total", 0)

    if not events:
        await update.message.reply_text(
            f"No events found for '{keyword}'.", reply_markup=main_menu_markup(update.effective_user.id),
        )
        return ConversationHandler.END

    total_pages = max(1, (total + ITEMS_PER_PAGE - 1) // ITEMS_PER_PAGE)
    context.user_data["search_keyword"] = keyword

    lines = [f"<b>Search results</b> — Page 1/{total_pages} ({total}) found\n"]
    for i, ev in enumerate(events, 1):
        lines.append(f"{i}. {format_event_compact(ev)}\n")

    text = "\n".join(lines)

    nav = []
    if total_pages > 1:
        nav.append(InlineKeyboardButton("Next ▶️", callback_data="searchpage|2"))

    kb = [nav] if nav else []
    for ev in events[:5]:
        eid = ev["_id"]
        kb.append([InlineKeyboardButton(f"\U0001f50d {ev.get('title', '?')[:30]}", callback_data=f"view|{eid}")])
    kb.append([InlineKeyboardButton("\U0001f519 Main Menu", callback_data="menu")])

    await update.message.reply_text(text, reply_markup=InlineKeyboardMarkup(kb), parse_mode="HTML", disable_web_page_preview=True)
    return ConversationHandler.END


async def handle_search_page(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    parts = q.data.split("|")
    page = int(parts[1])
    keyword = context.user_data.get("search_keyword", "")

    data = await fetch_events({"search": keyword, "per_page": ITEMS_PER_PAGE, "page": page, "sort": "date_asc"})
    if data is None:
        await q.edit_message_text("❌ Error contacting API.", reply_markup=main_menu_markup(update.effective_user.id))
        return

    events = data.get("events", [])
    total = data.get("total", 0)
    total_pages = max(1, (total + ITEMS_PER_PAGE - 1) // ITEMS_PER_PAGE)

    if not events:
        await q.edit_message_text(f"No more results.", reply_markup=main_menu_markup(update.effective_user.id))
        return

    lines = [f"<b>Search results</b> — Page {page}/{total_pages} ({total}) found\n"]
    start = (page - 1) * ITEMS_PER_PAGE + 1
    for i, ev in enumerate(events, start):
        lines.append(f"{i}. {format_event_compact(ev)}\n")
    text = "\n".join(lines)

    nav = []
    if page > 1:
        nav.append(InlineKeyboardButton("◀️ Prev", callback_data=f"searchpage|{page-1}"))
    if page < total_pages:
        nav.append(InlineKeyboardButton("Next ▶️", callback_data=f"searchpage|{page+1}"))

    kb = [nav] if nav else []
    for ev in events[:5]:
        eid = ev["_id"]
        kb.append([InlineKeyboardButton(f"\U0001f50d {ev.get('title', '?')[:30]}", callback_data=f"view|{eid}")])
    kb.append([InlineKeyboardButton("\U0001f519 Main Menu", callback_data="menu")])

    await q.edit_message_text(text, reply_markup=InlineKeyboardMarkup(kb), parse_mode="HTML", disable_web_page_preview=True)


async def myevents_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    data = await fetch_events({"creator_id": uid, "per_page": ITEMS_PER_PAGE, "page": 1, "sort": "date_asc"})
    if data is None:
        await update.message.reply_text("❌ Error contacting API.", reply_markup=main_menu_markup(update.effective_user.id))
        return

    events = data.get("events", [])
    total = data.get("total", 0)
    total_pages = max(1, (total + ITEMS_PER_PAGE - 1) // ITEMS_PER_PAGE)

    if not events:
        await update.message.reply_text(
            "\U0001f4ed You haven't submitted any events yet.\n\nForward an event announcement to add one!",
            reply_markup=main_menu_markup(update.effective_user.id),
        )
        return

    lines = [f"<b>My Events</b> — Page 1/{total_pages} ({total}) total\n"]
    for i, ev in enumerate(events, 1):
        lines.append(f"{i}. {format_event_compact(ev)}\n")

    text = "\n".join(lines)

    nav = []
    if total_pages > 1:
        nav.append(InlineKeyboardButton("Next ▶️", callback_data=f"myevents|2"))

    kb = [nav] if nav else []
    for ev in events[:5]:
        eid = ev["_id"]
        kb.append([InlineKeyboardButton(f"\U0001f50d {ev.get('title', '?')[:30]}", callback_data=f"view|{eid}")])
    kb.append([InlineKeyboardButton("\U0001f519 Main Menu", callback_data="menu")])

    await update.message.reply_text(text, reply_markup=InlineKeyboardMarkup(kb), parse_mode="HTML")


async def admin_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.effective_user.id):
        await update.message.reply_text("⛔ Access denied.", reply_markup=main_menu_markup(update.effective_user.id))
        return

    await update.message.reply_text(
        "\U0001f6e0 **Admin Panel**",
        reply_markup=admin_markup(),
        parse_mode="HTML",
    )


async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = (
        "\U0001f4ac <b>USM Event Hub - Help</b>\n\n"
        "\U0001f447 <b>How to use:</b>\n"
        "• <b>Forward</b> an event announcement → bot extracts & saves\n"
        "• <b>Browse</b> all events with filters\n"
        "• <b>Search</b> by keyword\n"
        "• <b>My Events</b> shows events you submitted\n\n"
        "\U0001f4cc <b>Commands:</b>\n"
        "/start - Main menu\n"
        "/browse - Browse all events\n"
        "/search - Search events\n"
        "/myevents - Your events\n"
        "/help - This message\n"
        "/batch - Toggle batch mode (collect events silently)"
    )
    if is_admin(update.effective_user.id):
        text += "\n/admin - Admin panel"

    await update.message.reply_text(text, parse_mode="HTML")




async def handle_cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data.clear()
    await update.message.reply_text("Cancelled.", reply_markup=main_menu_markup(update.effective_user.id))
    return ConversationHandler.END
