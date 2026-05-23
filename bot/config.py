import os

TOKEN = os.getenv("BOT_TOKEN")
API_URL = "http://api:8000/events"
PROCESS_URL = "http://api:8000/events/process"
ADMIN_IDS = [int(x) for x in os.getenv("ADMIN_IDS", "").split(",") if x.strip()]
ITEMS_PER_PAGE = 5

# Conversation states
IDLE, SEARCHING, EDIT_FIELD, CREATE_TITLE, CREATE_FIELD = range(5)
