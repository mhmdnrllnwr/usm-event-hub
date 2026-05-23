from telegram import InlineKeyboardMarkup, InlineKeyboardButton
from config import ITEMS_PER_PAGE
from helpers import is_admin


def main_menu_markup(uid: int):
    buttons = [
        [InlineKeyboardButton("\U0001f4c5 List Events", callback_data="list_active"),
         InlineKeyboardButton("\U0001f50d Search Event", callback_data="search"),
         InlineKeyboardButton("\U0001f4cb My Events", callback_data="myevents|1")],
    ]
    if is_admin(uid):
        buttons.append([InlineKeyboardButton("\U0001f6e0 Admin Panel", callback_data="admin|panel")])
    buttons.append([InlineKeyboardButton("❌ Close", callback_data="close")])
    return InlineKeyboardMarkup(buttons)


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


def edit_field_keyboard(event_id: str, fields: list):
    buttons = []
    for key, label in fields:
        buttons.append([InlineKeyboardButton(label, callback_data=f"edit|field|{key}|{event_id}")])
    buttons.append([InlineKeyboardButton("✅ Done Editing", callback_data=f"edit|done|{event_id}")])
    return InlineKeyboardMarkup(buttons)


def create_field_keyboard(fields: list):
    buttons = []
    for key, label in fields:
        buttons.append([InlineKeyboardButton(f"➕ {label}", callback_data=f"create|add|{key}")])
    buttons.append([InlineKeyboardButton("✅ Save & Publish", callback_data="create|save")])
    buttons.append([InlineKeyboardButton("❌ Cancel", callback_data="menu")])
    return InlineKeyboardMarkup(buttons)


def admin_markup():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("➕ Create Event", callback_data="create|start")],
        [InlineKeyboardButton("\U0001f4ca Bot Status", callback_data="admin|status")],
        [InlineKeyboardButton("\U0001f519 Back to Menu", callback_data="menu")],
    ])
