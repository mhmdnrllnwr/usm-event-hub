import os
import time
import html
import httpx
import logging
from telegram import Update, InlineKeyboardMarkup, InlineKeyboardButton
from telegram.ext import (
    ApplicationBuilder,
    ContextTypes,
    MessageHandler,
    CommandHandler,
    ConversationHandler,
    CallbackQueryHandler,
    filters,
)

logging.basicConfig(format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO)
logger = logging.getLogger(__name__)

TOKEN = os.getenv("BOT_TOKEN")
API_URL = "http://api:8000/events"
PROCESS_URL = "http://api:8000/events/process"
ADMIN_IDS = [int(x) for x in os.getenv("ADMIN_IDS", "").split(",") if x.strip()]
ITEMS_PER_PAGE = 5

# Conversation states
IDLE, SEARCHING, EDIT_FIELD, CREATE_TITLE, CREATE_FIELD = range(5)

# ── Helpers ──────────────────────────────────────────────────────────────────

def _format_date(start: str | None, end: str | None) -> str:
    if not start and not end:
        return "empty"
    if start and end and end != start:
        return f"{start} - {end}"
    return start or "empty"


def format_event(event: dict) -> str:
    title = html.escape(event.get("title", "Unknown Event"))
    date = html.escape(_format_date(event.get("start_date"), event.get("end_date")))

    st = event.get("start_time")
    et = event.get("end_time")
    if st and et:
        time_str = f"{html.escape(st)} – {html.escape(et)}"
    elif st:
        time_str = html.escape(st)
    else:
        time_str = "empty"

    fee = html.escape(event.get("fee") or "empty")
    venue = html.escape(event.get("venue") or "empty")

    link_raw = event.get("registration_link")
    if link_raw:
        link = html.escape(str(link_raw))
        link_line = f'\U0001f517 <b>Link:</b> <a href="{link}">Register/More Info</a>'
    else:
        link_line = "\U0001f517 <b>Link:</b> empty"

    mycsd = "Yes" if event.get("has_mycsd") else "No"
    status = event.get("status", "upcoming")
    icon = {"active": "\U0001f7e2", "expired": "\U0001f534", "upcoming": "\U0001f7e1"}
    default_icon = "\U0001f7e1"
    badge = f"{icon.get(status, default_icon)} <b>{status.upper()}</b>\n"

    return (
        f"\U0001f4c5 <b>{title}</b>\n"
        f"{badge}"
        f"\U0001f5d3 <b>Date:</b> {date}\n"
        f"\U0001f552 <b>Time:</b> {time_str}\n"
        f"\U0001f4b0 <b>Fee:</b> {fee}\n"
        f"\U0001f4cd <b>Venue:</b> {venue}\n"
        f"\U0001f31f <b>MyCSD:</b> {mycsd}\n"
        f"{link_line}\n"
    )


def is_admin(user_id: int) -> bool:
    return user_id in ADMIN_IDS


# ── Main Menu ────────────────────────────────────────────────────────────────

def main_menu_markup(uid: int):
    buttons = [
        [InlineKeyboardButton("\U0001f4c5 List Events", callback_data="list_active"),
         InlineKeyboardButton("\U0001f50d Search Event", callback_data="search"),
         InlineKeyboardButton("\U0001f4cb My Events", callback_data="myevents|1")],
    ]
    if is_admin(uid):
        buttons.append([InlineKeyboardButton("\U0001f6e0 Admin Panel", callback_data="admin|panel")])
    return InlineKeyboardMarkup(buttons)


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

    async with httpx.AsyncClient(timeout=30.0) as client:
        try:
            resp = await client.get(API_URL, params={"per_page": 50})
            data = resp.json()
        except Exception:
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

    # Per-event action rows
    kb_buttons = []
    for ev in events[:5]:
        short_id = ev["_id"]
        kb_buttons.append([InlineKeyboardButton(f"✏️ {ev.get('title', '?')[:30]}", callback_data=f"edit|start|{short_id}")])

    # Close + menu rows
    kb_buttons.append([InlineKeyboardButton("❌ Close", callback_data="close")])
    menu_rows = main_menu_markup(uid).inline_keyboard
    kb_buttons.extend(menu_rows)

    if update.callback_query:
        msg = update.callback_query.message
        if msg and msg.text:
            await update.callback_query.edit_message_text(
                event_text,
                reply_markup=InlineKeyboardMarkup(kb_buttons),
                parse_mode="HTML",
                disable_web_page_preview=True,
            )
        else:
            await update.callback_query.message.reply_text(
                event_text,
                reply_markup=InlineKeyboardMarkup(kb_buttons),
                parse_mode="HTML",
                disable_web_page_preview=True,
            )
    elif update.message:
        await update.message.reply_text(
            event_text,
            reply_markup=InlineKeyboardMarkup(kb_buttons),
            parse_mode="HTML",
            disable_web_page_preview=True,
        )


# ── Browse / Filter / Paginate ───────────────────────────────────────────────

def browse_filters_keyboard(current: dict):
    def btn(label, key, value, data):
        active = current.get(key) == value
        display = f"✅ {label}" if active else label
        return InlineKeyboardButton(display, callback_data=data)

    row1 = [
        btn("All", "status", None, "bfilter|status|"),
        btn("Active", "status", "active", "bfilter|status|active"),
        btn("Upcoming", "status", "upcoming", "bfilter|status|upcoming"),
        btn("Expired", "status", "expired", "bfilter|status|expired"),
    ]
    row2 = [
        btn("Free", "fee", "free", "bfilter|fee|free"),
        btn("Paid", "fee", "paid", "bfilter|fee|paid"),
        btn("MyCSD", "mycsd", True, "bfilter|mycsd|1"),
    ]
    row3 = [InlineKeyboardButton("\U0001f504 Reset Filters", callback_data="bfilter|reset")]
    row4 = [InlineKeyboardButton("\U0001f519 Back to Menu", callback_data="menu")]
    return InlineKeyboardMarkup([row1, row2, row3, row4])


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


async def show_browse(update: Update, context: ContextTypes.DEFAULT_TYPE, page: int = 1):
    filters = context.user_data.get("browse_filters", {})
    params = _build_browse_params(filters)
    params["page"] = str(page)
    params["per_page"] = str(ITEMS_PER_PAGE)

    q = update.callback_query
    await q.answer()

    async with httpx.AsyncClient(timeout=30.0) as client:
        try:
            resp = await client.get(API_URL, params=params)
            data = resp.json()
        except Exception:
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
    for ev in events:
        title = ev.get("title", "?")
        status = ev.get("status", "?")
        icon = {"active": "\U0001f7e2", "expired": "\U0001f534", "upcoming": "\U0001f7e1"}
        s = icon.get(status, "\U0001f7e1")
        lines.append(f"{s} <code>{html.escape(str(ev['_id'])[-6:])}</code> {html.escape(title)}")

    text = "\n".join(lines)

    # Navigation row
    nav = []
    if page > 1:
        nav.append(InlineKeyboardButton("◀️ Prev", callback_data=f"browse|{page-1}"))
    nav.append(InlineKeyboardButton("❌ Close", callback_data="close"))
    if page < total_pages:
        nav.append(InlineKeyboardButton(f"Next ▶️", callback_data=f"browse|{page+1}"))

    # Per-event action row
    action_row = []
    for ev in events[:3]:  # max 3 action buttons to avoid overflow
        short_id = ev["_id"]
        action_row.append(InlineKeyboardButton(f"\U0001f50d {ev.get('title', '?')[:20]}", callback_data=f"view|{short_id}"))

    kb_buttons = [nav, action_row] if action_row else [nav]
    kb_buttons.append([InlineKeyboardButton("\U0001f519 Back to Menu", callback_data="menu")])

    await q.edit_message_text(
        text,
        reply_markup=InlineKeyboardMarkup(kb_buttons),
        parse_mode="HTML",
        disable_web_page_preview=True,
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
        # Refresh browse view
        await show_browse(update, context, page=page)
    else:
        await send_main_menu(update, context)


# ── List Active Events ───────────────────────────────────────────────────────

async def handle_list_active(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()

    async with httpx.AsyncClient(timeout=30.0) as client:
        try:
            resp = await client.get(API_URL, params={"per_page": 50, "status": "active"})
            data = resp.json()
        except Exception:
            if q.message and q.message.text:
                await q.edit_message_text("❌ Error contacting API.", reply_markup=main_menu_markup(update.effective_user.id))
            else:
                await q.message.reply_text("❌ Error contacting API.", reply_markup=main_menu_markup(update.effective_user.id))
            return

    events = data.get("events", [])

    if not events:
        if q.message and q.message.text:
            await q.edit_message_text("\U0001f645 No active events right now.", reply_markup=main_menu_markup(update.effective_user.id))
        else:
            await q.message.reply_text("\U0001f645 No active events right now.", reply_markup=main_menu_markup(update.effective_user.id))
        return

    lines = [f"\U0001f7e2 <b>Active Events</b> — {len(events)} total\n"]
    for ev in events:
        title = ev.get("title", "?")
        lines.append(f"\U0001f7e2 {html.escape(title)}")
    text = "\n".join(lines)

    # Action buttons for first 5 events
    kb_buttons = []
    for ev in events[:5]:
        kb_buttons.append([InlineKeyboardButton(f"\U0001f50d {ev.get('title', '?')[:30]}", callback_data=f"view|{ev['_id']}")])
    kb_buttons.append([InlineKeyboardButton("❌ Close", callback_data="close")])
    kb_buttons.append([InlineKeyboardButton("\U0001f519 Main Menu", callback_data="menu")])

    if q.message and q.message.text:
        await q.edit_message_text(text, reply_markup=InlineKeyboardMarkup(kb_buttons), parse_mode="HTML", disable_web_page_preview=True)
    else:
        await q.message.reply_text(text, reply_markup=InlineKeyboardMarkup(kb_buttons), parse_mode="HTML", disable_web_page_preview=True)


# ── View Details ─────────────────────────────────────────────────────────────

async def handle_view_event(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    parts = q.data.split("|")
    event_id = parts[1]

    async with httpx.AsyncClient(timeout=30.0) as client:
        try:
            resp = await client.get(f"{API_URL}/{event_id}")
            data = resp.json()
            event = data.get("event")
        except Exception:
            await q.edit_message_text("❌ Event not found.", reply_markup=main_menu_markup(update.effective_user.id))
            return

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
        buttons.append([InlineKeyboardButton("\U0001f4f8 View Selected Event", callback_data=f"poster|{event_id}")])

    if can_edit:
        buttons.append([InlineKeyboardButton("✏️ Edit", callback_data=f"edit|start|{event_id}"),
                        InlineKeyboardButton("\U0001f5d1 Delete", callback_data=f"delete|confirm|{event_id}")])

    buttons.append([InlineKeyboardButton("\U0001f519 Back to List", callback_data="menu")])

    await q.edit_message_text(
        text,
        reply_markup=InlineKeyboardMarkup(buttons),
        parse_mode="HTML",
        disable_web_page_preview=True,
    )


async def handle_view_poster(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    parts = q.data.split("|")
    event_id = parts[1]

    async with httpx.AsyncClient(timeout=30.0) as client:
        try:
            resp = await client.get(f"{API_URL}/{event_id}")
            data = resp.json()
            event = data.get("event")
        except Exception:
            await q.edit_message_text("❌ Event not found.", reply_markup=main_menu_markup(update.effective_user.id))
            return

    image = event.get("image_url") if event else None
    if not image:
        await q.answer("No poster available.", show_alert=True)
        return

    raw_text = event.get("raw_text", "") if event else ""
    caption = raw_text[:1024] if raw_text else None

    image_url = f"http://api:8000{image}"
    async with httpx.AsyncClient(timeout=30.0) as client:
        try:
            resp = await client.get(image_url)
            await q.message.reply_photo(photo=resp.content, caption=caption)
        except Exception:
            await q.answer("Failed to load poster.", show_alert=True)


# ── Delete ───────────────────────────────────────────────────────────────────

async def handle_delete_confirm(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    parts = q.data.split("|")
    event_id = parts[2]

    await q.edit_message_text(
        f"❓ Delete this event?\n\nThis cannot be undone.",
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

    async with httpx.AsyncClient(timeout=30.0) as client:
        try:
            resp = await client.delete(f"{API_URL}/{event_id}")
            if resp.status_code == 200:
                await q.edit_message_text(
                    "✅ Event deleted.",
                    reply_markup=main_menu_markup(update.effective_user.id),
                )
            else:
                await q.edit_message_text(
                    "❌ Failed to delete event.",
                    reply_markup=main_menu_markup(update.effective_user.id),
                )
        except Exception:
            await q.edit_message_text(
                "❌ Error contacting API.",
                reply_markup=main_menu_markup(update.effective_user.id),
            )


# ── Edit Flow (ConversationHandler) ──────────────────────────────────────────

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


def edit_field_keyboard(event_id: str):
    buttons = []
    for key, label in EDIT_FIELDS:
        buttons.append([InlineKeyboardButton(label, callback_data=f"edit|field|{key}|{event_id}")])
    buttons.append([InlineKeyboardButton("✅ Done Editing", callback_data=f"edit|done|{event_id}")])
    return InlineKeyboardMarkup(buttons)


async def handle_edit_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    parts = q.data.split("|")
    event_id = parts[2]

    async with httpx.AsyncClient(timeout=30.0) as client:
        try:
            resp = await client.get(f"{API_URL}/{event_id}")
            event = resp.json().get("event", {})
        except Exception:
            await q.edit_message_text("❌ Event not found.")
            return

    title = event.get("title", "?")
    context.user_data["edit_event_id"] = event_id
    context.user_data["edit_updates"] = {}

    lines = [f"✏️ Edit <b>{html.escape(title)}</b>", "", "Choose field to edit:"]
    text = "\n".join(lines)

    await q.edit_message_text(text, reply_markup=edit_field_keyboard(event_id), parse_mode="HTML")
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
        # Toggle
        updates = context.user_data.get("edit_updates", {})
        current = updates.get("has_mycsd", False)
        updates["has_mycsd"] = not current
        context.user_data["edit_updates"] = updates
        await q.answer(f"MyCSD set to {not current}", show_alert=True)
        return await show_edit_picker(update, context, event_id)

    # For other fields, ask user to type new value
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

    await update.message.reply_text(f"✅ {field} updated.", reply_markup=edit_field_keyboard(event_id))
    return IDLE


async def show_edit_picker(update: Update, context: ContextTypes.DEFAULT_TYPE, event_id: str):
    q = update.callback_query
    await q.edit_message_text(
        "✏️ Choose field to edit:",
        reply_markup=edit_field_keyboard(event_id),
    )
    return IDLE


async def handle_edit_done(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    event_id = context.user_data.get("edit_event_id")
    updates = context.user_data.get("edit_updates", {})

    if not updates:
        await q.edit_message_text("No changes made.", reply_markup=main_menu_markup(update.effective_user.id))
        context.user_data.pop("edit_event_id", None)
        context.user_data.pop("edit_updates", None)
        context.user_data.pop("edit_field", None)
        return IDLE

    async with httpx.AsyncClient(timeout=30.0) as client:
        try:
            resp = await client.put(f"{API_URL}/{event_id}", json=updates)
            if resp.status_code == 200:
                await q.edit_message_text(
                    "✅ Event updated successfully!",
                    reply_markup=InlineKeyboardMarkup([
                        [InlineKeyboardButton("\U0001f50d View Event", callback_data=f"view|{event_id}")],
                        [InlineKeyboardButton("\U0001f519 Main Menu", callback_data="menu")],
                    ]),
                )
            else:
                await q.edit_message_text(
                    f"❌ Update failed: {resp.text}",
                    reply_markup=main_menu_markup(update.effective_user.id),
                )
        except Exception:
            await q.edit_message_text("❌ Error contacting API.", reply_markup=main_menu_markup(update.effective_user.id))

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
    """Route edit callback_data to the right handler."""
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


# ── My Events ────────────────────────────────────────────────────────────────

async def handle_my_events(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    uid = update.effective_user.id
    page = 1
    parts = q.data.split("|")
    if len(parts) > 1:
        page = int(parts[1])

    async with httpx.AsyncClient(timeout=30.0) as client:
        try:
            resp = await client.get(API_URL, params={"creator_id": uid, "page": page, "per_page": ITEMS_PER_PAGE})
            data = resp.json()
        except Exception:
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

    # Action buttons for first 3 events
    actions = []
    for ev in events[:3]:
        eid = ev["_id"]
        actions.append(InlineKeyboardButton(f"\U0001f50d {ev.get('title', '?')[:20]}", callback_data=f"view|{eid}"))

    kb = [nav] if nav else []
    if actions:
        kb.append(actions)
    kb.append([InlineKeyboardButton("❌ Close", callback_data="close")])
    kb.append([InlineKeyboardButton("\U0001f519 Main Menu", callback_data="menu")])

    await q.edit_message_text(
        text,
        reply_markup=InlineKeyboardMarkup(kb),
        parse_mode="HTML",
    )


# ── Admin Panel ──────────────────────────────────────────────────────────────

async def handle_admin_panel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()

    if not is_admin(update.effective_user.id):
        await q.edit_message_text("⛔ Access denied.", reply_markup=main_menu_markup(update.effective_user.id))
        return

    await q.edit_message_text(
        "\U0001f6e0 <b>Admin Panel</b>",
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("➕ Create Event", callback_data="create|start")],
            [InlineKeyboardButton("\U0001f4ca Bot Status", callback_data="admin|status")],
            [InlineKeyboardButton("\U0001f519 Back to Menu", callback_data="menu")],
        ]),
        parse_mode="HTML",
    )


async def handle_admin_status(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()

    async with httpx.AsyncClient(timeout=30.0) as client:
        try:
            resp = await client.get(API_URL, params={"per_page": 1})
            total = resp.json().get("total", 0)
            status_text = f"\U0001f4ca <b>Total events:</b> {total}\n✅ <b>API:</b> Online\n✅ <b>DB:</b> Connected"
        except Exception:
            status_text = "❌ <b>API:</b> Offline"

    await q.edit_message_text(
        status_text,
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("\U0001f519 Back", callback_data="admin|panel")],
        ]),
        parse_mode="HTML",
    )


# ── Create Event (Admin) ─────────────────────────────────────────────────────

async def handle_create_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    context.user_data["create_data"] = {}
    await q.edit_message_text(
        "Send the event <b>title</b>:",
        parse_mode="HTML",
    )
    return CREATE_TITLE


async def handle_create_title(update: Update, context: ContextTypes.DEFAULT_TYPE):
    title = update.message.text.strip()
    if not title:
        await update.message.reply_text("Title cannot be empty\\. Try again or /cancel\\.")
        return CREATE_TITLE

    context.user_data["create_data"] = {"title": title}
    await show_create_field_picker(update, context)
    return CREATE_FIELD


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


def create_field_keyboard():
    buttons = []
    for key, label in CREATE_FIELDS:
        buttons.append([InlineKeyboardButton(f"➕ {label}", callback_data=f"create|add|{key}")])
    buttons.append([InlineKeyboardButton("✅ Save & Publish", callback_data="create|save")])
    buttons.append([InlineKeyboardButton("❌ Cancel", callback_data="menu")])
    return InlineKeyboardMarkup(buttons)


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
        await update.callback_query.edit_message_text(text, reply_markup=create_field_keyboard(), parse_mode="HTML")
    elif update.message:
        await update.message.reply_text(text, reply_markup=create_field_keyboard(), parse_mode="HTML")


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

    async with httpx.AsyncClient(timeout=30.0) as client:
        try:
            resp = await client.post(API_URL, json=payload)
            if resp.status_code == 200:
                result = resp.json()
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
                detail = resp.json().get("detail", "Unknown error")
                await q.edit_message_text(
                    f"❌ <b>Failed:</b> {html.escape(str(detail))}",
                    reply_markup=main_menu_markup(update.effective_user.id),
                    parse_mode="HTML",
                )
        except Exception:
            await q.edit_message_text("❌ Error contacting API.", reply_markup=main_menu_markup(update.effective_user.id))

    context.user_data.pop("create_data", None)
    context.user_data.pop("create_field", None)
    return IDLE


async def handle_create_cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data.pop("create_data", None)
    context.user_data.pop("create_field", None)
    await update.message.reply_text("Event creation cancelled.", reply_markup=main_menu_markup(update.effective_user.id))
    return IDLE


# ── Close ────────────────────────────────────────────────────────────────────

async def handle_close(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    await q.delete_message()


# ── Command Handlers ─────────────────────────────────────────────────────────

async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    intro = (
        "\U0001f44b <b>Welcome to USM Event Hub!</b>\n\n"
        "I collect and organize event announcements from USM.\n\n"
        "Use buttons below to browse events, search, or manage your submissions."
    )
    await send_main_menu(update, context, text=intro)


async def browse_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["browse_filters"] = {}
    context.user_data["browse_page"] = 1
    async with httpx.AsyncClient(timeout=30.0) as client:
        try:
            resp = await client.get(API_URL, params={"per_page": ITEMS_PER_PAGE})
            data = resp.json()
        except Exception:
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
        lines.append(f"{s} <code>{html.escape(str(ev['_id'])[-6:])}</code> {html.escape(title)}")

    text = "\n".join(lines)

    nav = []
    if total_pages > 1:
        nav.append(InlineKeyboardButton(f"Next ▶️", callback_data="browse|2"))
    nav.append(InlineKeyboardButton("❌ Close", callback_data="close"))

    actions = []
    for ev in events[:3]:
        eid = ev["_id"]
        actions.append(InlineKeyboardButton(f"\U0001f50d {ev.get('title', '?')[:20]}", callback_data=f"view|{eid}"))

    kb = [nav, actions] if actions else [nav]
    kb.append([InlineKeyboardButton("\U0001f519 Main Menu", callback_data="menu")])

    await update.message.reply_text(
        text,
        reply_markup=InlineKeyboardMarkup(kb),
        parse_mode="HTML",
        disable_web_page_preview=True,
    )


async def search_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("What are you looking for? Type a keyword (e.g. 'Hackathon'):")
    return SEARCHING


async def handle_search_input(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyword = update.message.text.strip()
    if not keyword:
        await update.message.reply_text("Keyword cannot be empty.")
        return SEARCHING

    await update.message.reply_text(f"Searching for '{keyword}'...")

    async with httpx.AsyncClient(timeout=30.0) as client:
        try:
            resp = await client.get(API_URL, params={"search": keyword, "per_page": ITEMS_PER_PAGE})
            data = resp.json()
        except Exception:
            await update.message.reply_text("❌ Error contacting API.", reply_markup=main_menu_markup(update.effective_user.id))
            return ConversationHandler.END

    events = data.get("events", [])
    total = data.get("total", 0)

    if not events:
        await update.message.reply_text(
            f"No events found for '{keyword}'.",
            reply_markup=main_menu_markup(update.effective_user.id),
        )
        return ConversationHandler.END

    lines = [f"<b>Search results</b> — {total} found\n"]
    for ev in events:
        title = ev.get("title", "?")
        status = ev.get("status", "?")
        icon = {"active": "\U0001f7e2", "expired": "\U0001f534", "upcoming": "\U0001f7e1"}
        s = icon.get(status, "\U0001f7e1")
        lines.append(f"{s} <code>{html.escape(str(ev['_id'])[-6:])}</code> {html.escape(title)}")

    text = "\n".join(lines)

    actions = []
    for ev in events[:3]:
        eid = ev["_id"]
        actions.append(InlineKeyboardButton(f"\U0001f50d {ev.get('title', '?')[:20]}", callback_data=f"view|{eid}"))

    kb = [actions] if actions else []
    kb.append([InlineKeyboardButton("\U0001f519 Main Menu", callback_data="menu")])

    await update.message.reply_text(
        text,
        reply_markup=InlineKeyboardMarkup(kb),
        parse_mode="HTML",
        disable_web_page_preview=True,
    )
    return ConversationHandler.END


async def myevents_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    async with httpx.AsyncClient(timeout=30.0) as client:
        try:
            resp = await client.get(API_URL, params={"creator_id": uid, "per_page": ITEMS_PER_PAGE})
            data = resp.json()
        except Exception:
            await update.message.reply_text("❌ Error contacting API.", reply_markup=main_menu_markup(update.effective_user.id))
            return

    events = data.get("events", [])
    total = data.get("total", 0)

    if not events:
        await update.message.reply_text(
            "\U0001f4ed You haven’t submitted any events yet.\n\nForward an event announcement to add one!",
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

    await update.message.reply_text(
        text,
        reply_markup=InlineKeyboardMarkup(kb),
        parse_mode="HTML",
    )


async def admin_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.effective_user.id):
        await update.message.reply_text("⛔ Access denied.", reply_markup=main_menu_markup(update.effective_user.id))
        return

    await update.message.reply_text(
        "\U0001f6e0 **Admin Panel**",
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("➕ Create Event", callback_data="create|start")],
            [InlineKeyboardButton("\U0001f4ca Bot Status", callback_data="admin|status")],
            [InlineKeyboardButton("\U0001f519 Main Menu", callback_data="menu")],
        ]),
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


# ── Push Handler (Forward message) ───────────────────────────────────────────

async def handle_push_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    raw_text = ""
    file_id = None

    if update.message.photo:
        file_id = update.message.photo[-1].file_id
        raw_text = update.message.caption or ""
    elif update.message.text:
        raw_text = update.message.text

    if not raw_text:
        return

    uid = update.effective_user.id
    await context.bot.send_chat_action(chat_id=update.effective_chat.id, action="typing")

    async with httpx.AsyncClient(timeout=30.0) as client:
        try:
            payload = {"text": raw_text, "image_url": file_id, "creator_id": uid}
            resp = await client.post(PROCESS_URL, json=payload)

            if resp.status_code == 200:
                data = resp.json()
                ext = data.get("extracted_data", {})
                eid = data.get("id")

                st = ext.get("start_time")
                et = ext.get("end_time")
                time_str = f"{st} – {et}" if st and et else (st or "empty")

                fee_d = ext.get("fee") or "empty"
                venue_d = ext.get("venue") or "empty"
                link_d = ext.get("registration_link") or "empty"
                status = ext.get("status", "upcoming")
                icon = {"active": "\U0001f7e2", "expired": "\U0001f534", "upcoming": "\U0001f7e1"}
                si = icon.get(status, "\U0001f7e1")
                tag = f"{si} <b>{status.upper()}</b>\n"

                reply = (
                    f"✅ <b>EVENT CAPTURED</b>\n{tag}"
                    f"━━━━━━━━━━━━━━━━━━━━\n"
                    f"\U0001f4dd <b>Title:</b> {ext.get('title')}\n"
                    f"\U0001f5d3 <b>Date:</b> {_format_date(ext.get('start_date'), ext.get('end_date'))}\n"
                    f"\U0001f552 <b>Time:</b> {time_str}\n"
                    f"\U0001f4b0 <b>Fee:</b> {fee_d}\n"
                    f"\U0001f4cd <b>Venue:</b> {venue_d}\n"
                    f"\U0001f517 <b>Link:</b> {link_d}\n"
                    f"━━━━━━━━━━━━━━━━━━━━\n"
                    f"\U0001f194 <code>ID: {eid}</code>"
                )

                view_kb = InlineKeyboardMarkup([
                    [InlineKeyboardButton("✏️ Edit", callback_data=f"edit|start|{eid}"),
                     InlineKeyboardButton("\U0001f5d1 Delete", callback_data=f"delete|confirm|{eid}")],
                ])

                if file_id:
                    await update.message.reply_photo(photo=file_id, caption=reply, parse_mode="HTML", reply_markup=view_kb)
                else:
                    await update.message.reply_text(reply, parse_mode="HTML", disable_web_page_preview=True, reply_markup=view_kb)

            elif resp.status_code == 409:
                await update.message.reply_text("⚠️ <b>Event already exists!</b>", parse_mode="HTML")
            else:
                await update.message.reply_text("❌ Failed to process event.")

        except Exception as e:
            logger.error(f"Error handling push: {e}")
            await update.message.reply_text("\U0001f50c Connection Error: API is offline or an error occurred.")


# ── Catch-all callback router ────────────────────────────────────────────────

async def handle_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    data = q.data
    logger.info(f"Callback: {data}")

    if data.startswith("browse|"):
        return await handle_browse_callback(update, context)
    elif data.startswith("bfilter|"):
        return await handle_browse_filter(update, context)
    elif data.startswith("view|"):
        return await handle_view_event(update, context)
    elif data.startswith("poster|"):
        return await handle_view_poster(update, context)
    elif data.startswith("delete|"):
        action = data.split("|")[1]
        if action == "confirm":
            return await handle_delete_confirm(update, context)
        elif action == "yes":
            return await handle_delete_execute(update, context)
    elif data.startswith("edit|"):
        return await handle_edit_callback(update, context)
    elif data.startswith("myevents|"):
        return await handle_my_events(update, context)
    elif data == "list_active":
        return await handle_list_active(update, context)
    elif data.startswith("admin|"):
        action = data.split("|")[1] if len(data.split("|")) > 1 else ""
        if action == "status":
            return await handle_admin_status(update, context)
        else:
            return await handle_admin_panel(update, context)
    elif data.startswith("create|"):
        action = data.split("|")[1]
        if action == "start":
            return await handle_create_start(update, context)
        elif action == "add":
            return await handle_create_add(update, context)
        elif action == "save":
            return await handle_create_save(update, context)
    elif data == "search":
        await q.answer()
        await q.edit_message_text("What are you looking for? Type a keyword (e.g. 'Hackathon'):")
        return SEARCHING
    elif data.startswith("mainpage|") or data == "menu":
        await q.answer()
        intro = (
            "\U0001f44b <b>Welcome to USM Event Hub!</b>\n\n"
            "I collect and organize event announcements from USM.\n\n"
            "Use buttons below to browse events, search, or manage your submissions."
        )
        return await send_main_menu(update, context, text=intro)
    elif data == "close":
        return await handle_close(update, context)

    return IDLE


# ── Main ─────────────────────────────────────────────────────────────────────

def wait_for_api():
    max_retries = 30
    for attempt in range(1, max_retries + 1):
        try:
            resp = httpx.get(API_URL, timeout=5)
            if resp.status_code == 200:
                logger.info("API ready")
                return
        except Exception as e:
            logger.warning(f"API not ready (attempt {attempt}/{max_retries}): {e}")
            time.sleep(2)
    logger.error("API not available. Exiting.")
    exit(1)


if __name__ == "__main__":
    application = ApplicationBuilder().token(TOKEN).build()
    wait_for_api()

    # Edit conversation
    edit_conv = ConversationHandler(
        entry_points=[CallbackQueryHandler(handle_edit_callback, pattern="^edit\\|start\\|")],
        states={
            IDLE: [CallbackQueryHandler(handle_edit_callback, pattern="^edit\\|")],
            EDIT_FIELD: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, handle_edit_text),
                CallbackQueryHandler(handle_edit_callback, pattern="^edit\\|"),
            ],
        },
        fallbacks=[CommandHandler("cancel", handle_edit_cancel)],
        allow_reentry=True,
    )

    # Create conversation (admin)
    create_conv = ConversationHandler(
        entry_points=[CallbackQueryHandler(handle_create_start, pattern="^create\\|start$")],
        states={
            CREATE_TITLE: [MessageHandler(filters.TEXT & ~filters.COMMAND, handle_create_title)],
            CREATE_FIELD: [CallbackQueryHandler(handle_create_add, pattern="^create\\|add\\|"),
                          CallbackQueryHandler(handle_create_save, pattern="^create\\|save$"),
                          MessageHandler(filters.TEXT & ~filters.COMMAND, handle_create_field_text)],
        },
        fallbacks=[CommandHandler("cancel", handle_create_cancel)],
        allow_reentry=True,
    )

    # Search conversation
    search_conv = ConversationHandler(
        entry_points=[
            CommandHandler("search", search_command),
            CallbackQueryHandler(handle_callback, pattern="^search$"),
        ],
        states={
            SEARCHING: [MessageHandler(filters.TEXT & ~filters.COMMAND, handle_search_input)],
        },
        fallbacks=[CommandHandler("cancel", handle_cancel)],
    )

    application.add_handler(CommandHandler("start", start_command))
    application.add_handler(CommandHandler("browse", browse_command))
    application.add_handler(CommandHandler("myevents", myevents_command))
    application.add_handler(CommandHandler("admin", admin_command))
    application.add_handler(CommandHandler("help", help_command))
    application.add_handler(search_conv)
    application.add_handler(edit_conv)
    application.add_handler(create_conv)
    application.add_handler(CallbackQueryHandler(handle_callback))
    application.add_handler(MessageHandler((filters.TEXT | filters.PHOTO) & ~filters.COMMAND, handle_push_message))

    logger.info("Bot is running...")
    application.run_polling()
