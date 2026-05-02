# api/engine/config.py

# Phrases that are almost NEVER titles
NEGATIVE_TITLE_KEYWORDS = [
    "d-day", "days to go", "happening now", "announcement", 
    "theme", "update", "reminder", "registration", "greetings", "calling all"
]

# Venue Mapping
VENUE_KEYWORDS = {
    "online": ["webex", "google meet", "zoom", "teams", "fb live", "youtube live"],
    "physical_indicators": ["dewan", "dud", "bilik", "foyer", "padang", "kompleks", "pusat", "dk"],
    "ignore_list": ["mycsd", "earn", "provided", "points", "register", "whatsapp"]
}