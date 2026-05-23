# api/engine/config.py
import os

# Phrases that are almost NEVER titles
NEGATIVE_TITLE_KEYWORDS = [
    "d-day", "days to go", "happening now", "announcement", 
    "theme", "update", "reminder", "registration", "greetings", "calling all"
]

# Labels for Dates and Times
DATE_LABELS = ["Date", "Tarikh", "Hari", "Period", "Tempoh"]
TIME_LABELS = ["Time", "Masa", "Waktu"]

# Labels used to find Venue information
VENUE_LABELS = ["Venue", "Location", "Place", "Tempat", "Lokasi", "Platform"]

VENUE_KEYWORDS = {
    "online": ["webex", "google meet", "zoom", "teams", "fb live"],
    "physical_indicators": ["dewan", "dud", "bilik", "foyer", "padang", "kompleks", "pusat", "dk"],
    "ignore_list": ["mycsd", "earn", "provided", "points", "register", "whatsapp"]
}

# --- AI Title Validation ---
DEEPSEEK_API_KEY_ENV = "DEEPSEEK_API_KEY"
DEEPSEEK_MODEL = "deepseek-chat"
DEEPSEEK_API_URL = "https://api.deepseek.com/v1/chat/completions"
DEEPSEEK_TIMEOUT_SECONDS = 10
TITLE_CONFIDENCE_THRESHOLD = 6

# --- Admin Configuration ---
ADMIN_IDS = [int(x) for x in os.getenv("ADMIN_IDS", "").split(",") if x.strip()]

# --- Labels used to find Fee information

# Labels used to find Fee information
FEE_LABELS = ["Fee", "Yuran", "Harga", "Bayaran","Fees"]

CURRENCY_PREFIXES = ["RM", "MYR", "$"]

FREE_KEYWORDS = ["Free", "Percuma"]