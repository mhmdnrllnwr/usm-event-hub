from telegram import Update
from telegram.ext import ContextTypes
from api_client import fetch_events
from helpers import is_admin
from keyboards import main_menu_markup, admin_markup


async def handle_admin_panel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()

    if not is_admin(update.effective_user.id):
        await q.edit_message_text("⛔ Access denied.", reply_markup=main_menu_markup(update.effective_user.id))
        return

    await q.edit_message_text(
        "\U0001f6e0 <b>Admin Panel</b>",
        reply_markup=admin_markup(),
        parse_mode="HTML",
    )


async def handle_admin_status(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()

    data = await fetch_events({"per_page": 1})
    if data is not None:
        total = data.get("total", 0)
        status_text = f"\U0001f4ca <b>Total events:</b> {total}\n✅ <b>API:</b> Online\n✅ <b>DB:</b> Connected"
    else:
        status_text = "❌ <b>API:</b> Offline"

    from telegram import InlineKeyboardMarkup, InlineKeyboardButton
    await q.edit_message_text(
        status_text,
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("\U0001f519 Back", callback_data="admin|panel")],
        ]),
        parse_mode="HTML",
    )
