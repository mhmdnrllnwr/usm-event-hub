import logging
from telegram import Update
from telegram.ext import ContextTypes
from config import IDLE, SEARCHING

logger = logging.getLogger(__name__)


async def handle_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    data = q.data
    logger.info(f"Callback: {data}")

    if data.startswith("browse|"):
        from .browse import handle_browse_callback
        return await handle_browse_callback(update, context)
    elif data.startswith("bfilter|"):
        from .browse import handle_browse_filter
        return await handle_browse_filter(update, context)
    elif data.startswith("view|"):
        from .view import handle_view_event
        return await handle_view_event(update, context)
    elif data.startswith("poster|"):
        from .view import handle_view_poster
        return await handle_view_poster(update, context)
    elif data.startswith("delete|"):
        action = data.split("|")[1]
        if action == "confirm":
            from .delete import handle_delete_confirm
            return await handle_delete_confirm(update, context)
        elif action == "yes":
            from .delete import handle_delete_execute
            return await handle_delete_execute(update, context)
    elif data.startswith("edit|"):
        from .edit import handle_edit_callback
        return await handle_edit_callback(update, context)
    elif data.startswith("myevents|"):
        from .my_events import handle_my_events
        return await handle_my_events(update, context)
    elif data.startswith("list_active"):
        from .browse import handle_list_active
        return await handle_list_active(update, context)
    elif data.startswith("admin|"):
        action = data.split("|")[1] if len(data.split("|")) > 1 else ""
        if action == "status":
            from .admin import handle_admin_status
            return await handle_admin_status(update, context)
        else:
            from .admin import handle_admin_panel
            return await handle_admin_panel(update, context)
    elif data.startswith("create|"):
        action = data.split("|")[1]
        if action == "start":
            from .create import handle_create_start
            return await handle_create_start(update, context)
        elif action == "add":
            from .create import handle_create_add
            return await handle_create_add(update, context)
        elif action == "save":
            from .create import handle_create_save
            return await handle_create_save(update, context)
    elif data.startswith("searchpage|"):
        from .commands import handle_search_page
        return await handle_search_page(update, context)
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
        from .menu import send_main_menu
        return await send_main_menu(update, context, text=intro)
    elif data.startswith("batch|"):
        await q.answer()
        from .batch import handle_batch_callback
        return await handle_batch_callback(update, context)
    elif data == "close":
        from .menu import handle_close
        return await handle_close(update, context)

    return IDLE
