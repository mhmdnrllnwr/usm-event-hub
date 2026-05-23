import html
from telegram import Update, InlineKeyboardMarkup, InlineKeyboardButton
from telegram.ext import ContextTypes, ConversationHandler
from config import ITEMS_PER_PAGE, IDLE, SEARCHING
from api_client import fetch_events
from helpers import is_admin
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
    context.user_data["browse_filters"] = {}
    context.user_data["browse_page"] = 1

    data = await fetch_events({"per_page": ITEMS_PER_PAGE})
    if data is None:
        await update.message.reply_text("❌ Error contacting API.", reply_markup=main_menu_markup(update.effective_user.id))
        return

    events = data.get("events", [])
    total = data.get("total", 0)
    total_pages = max(1, (total + ITEMS_PER_PAGE - 1) // ITEMS_PER_PAGE)

    if not events:
        await update.message.reply_text("\U0001f645 No events yet.", reply_markup=main_menu_markup(update.effective_user.id))
        return

    lines = [f"<b>Events</b> — Page 1/{total_pages} ({total}) total\n"]
    for ev in events:
        title = ev.get("title", "?")
        status = ev.get("status", "?")
        icon = {"active": "\U0001f7e2", "expired": "\U0001f534", "upcoming": "\U0001f7e1"}
        s = icon.get(status, "\U0001f7e1")
        lines.append(f"{s} {html.escape(title)}")

    text = "\n".join(lines)

    nav = []
    if total_pages > 1:
        nav.append(InlineKeyboardButton(f"Next ▶️", callback_data="browse|2"))

    actions = []
    for ev in events[:3]:
        eid = ev["_id"]
        actions.append(InlineKeyboardButton(f"\U0001f50d {ev.get('title', '?')[:20]}", callback_data=f"view|{eid}"))

    kb = [nav, actions] if actions else [nav]
    kb.append([InlineKeyboardButton("\U0001f519 Main Menu", callback_data="menu")])
    kb.append([InlineKeyboardButton("❌ Close", callback_data="close")])

    await update.message.reply_text(text, reply_markup=InlineKeyboardMarkup(kb), parse_mode="HTML", disable_web_page_preview=True)


async def search_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("What are you looking for? Type a keyword (e.g. 'Hackathon'):")
    return SEARCHING


async def handle_search_input(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyword = update.message.text.strip()
    if not keyword:
        await update.message.reply_text("Keyword cannot be empty.")
        return SEARCHING

    await update.message.reply_text(f"Searching for '{keyword}'...")

    data = await fetch_events({"search": keyword, "per_page": ITEMS_PER_PAGE})
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

    lines = [f"<b>Search results</b> — {total} found\n"]
    for ev in events:
        title = ev.get("title", "?")
        status = ev.get("status", "?")
        icon = {"active": "\U0001f7e2", "expired": "\U0001f534", "upcoming": "\U0001f7e1"}
        s = icon.get(status, "\U0001f7e1")
        lines.append(f"{s} {html.escape(title)}")

    text = "\n".join(lines)

    actions = []
    for ev in events[:3]:
        eid = ev["_id"]
        actions.append(InlineKeyboardButton(f"\U0001f50d {ev.get('title', '?')[:20]}", callback_data=f"view|{eid}"))

    kb = [actions] if actions else []
    kb.append([InlineKeyboardButton("\U0001f519 Main Menu", callback_data="menu")])

    await update.message.reply_text(text, reply_markup=InlineKeyboardMarkup(kb), parse_mode="HTML", disable_web_page_preview=True)
    return ConversationHandler.END


async def myevents_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    data = await fetch_events({"creator_id": uid, "per_page": ITEMS_PER_PAGE})
    if data is None:
        await update.message.reply_text("❌ Error contacting API.", reply_markup=main_menu_markup(update.effective_user.id))
        return

    events = data.get("events", [])
    total = data.get("total", 0)

    if not events:
        await update.message.reply_text(
            "\U0001f4ed You haven't submitted any events yet.\n\nForward an event announcement to add one!",
            reply_markup=main_menu_markup(update.effective_user.id),
        )
        return

    lines = [f"<b>My Events</b> — {total} total\n"]
    for ev in events:
        title = ev.get("title", "?")
        lines.append(f"• {html.escape(title)}")
    text = "\n".join(lines)

    actions = []
    for ev in events[:3]:
        eid = ev["_id"]
        actions.append(InlineKeyboardButton(f"\U0001f50d {ev.get('title', '?')[:20]}", callback_data=f"view|{eid}"))

    kb = [actions] if actions else []
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
        "/help - This message"
    )
    if is_admin(update.effective_user.id):
        text += "\n/admin - Admin panel"

    await update.message.reply_text(text, parse_mode="HTML")


async def handle_cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data.clear()
    await update.message.reply_text("Cancelled.", reply_markup=main_menu_markup(update.effective_user.id))
    return ConversationHandler.END
