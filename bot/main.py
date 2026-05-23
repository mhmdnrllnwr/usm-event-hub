import time
import logging
import httpx
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, CallbackQueryHandler, ConversationHandler, filters

from config import TOKEN, API_URL, IDLE, SEARCHING, EDIT_FIELD, CREATE_TITLE, CREATE_FIELD
from handlers import (
    start_command,
    browse_command,
    search_command,
    myevents_command,
    admin_command,
    help_command,
    handle_cancel,
    handle_search_input,
    handle_edit_callback,
    handle_edit_text,
    edit_cancel,
    handle_create_start,
    handle_create_title,
    handle_create_add,
    handle_create_field_text,
    handle_create_save,
    create_cancel,
    handle_push_message,
    handle_callback,
)

logging.basicConfig(format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO)
logger = logging.getLogger(__name__)


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

    edit_conv = ConversationHandler(
        entry_points=[CallbackQueryHandler(handle_edit_callback, pattern="^edit\\|start\\|")],
        states={
            IDLE: [CallbackQueryHandler(handle_edit_callback, pattern="^edit\\|")],
            EDIT_FIELD: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, handle_edit_text),
                CallbackQueryHandler(handle_edit_callback, pattern="^edit\\|"),
            ],
        },
        fallbacks=[CommandHandler("cancel", edit_cancel)],
        allow_reentry=True,
    )

    create_conv = ConversationHandler(
        entry_points=[CallbackQueryHandler(handle_create_start, pattern="^create\\|start$")],
        states={
            CREATE_TITLE: [MessageHandler(filters.TEXT & ~filters.COMMAND, handle_create_title)],
            CREATE_FIELD: [
                CallbackQueryHandler(handle_create_add, pattern="^create\\|add\\|"),
                CallbackQueryHandler(handle_create_save, pattern="^create\\|save$"),
                MessageHandler(filters.TEXT & ~filters.COMMAND, handle_create_field_text),
            ],
        },
        fallbacks=[CommandHandler("cancel", create_cancel)],
        allow_reentry=True,
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
