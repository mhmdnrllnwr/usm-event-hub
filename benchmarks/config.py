import os

# --- Sample Telegram Messages (3 complexity levels) ---

SAMPLE_MINIMAL = (
    "[Tech_Talk_2026]\n"
    "Date: 15 June 2026\n"
    "Time: 2pm\n"
    "Venue: Online"
)

SAMPLE_TYPICAL = (
    "Join us for *CREATIVE STRATEGIES FOR DYNAMIC PRESENTATION*\n\n"
    "\U0001f5d3️ 21 May 2026\n"
    "⏰ 8:00 PM – 10:00 PM\n"
    "\U0001f4bb Cisco Webex\n"
    "\U0001f4b0 Fee: Only RM1\n"
    "✅ MYCSD will be provided\n"
    "Register: https://forms.gle/abc123"
)

SAMPLE_COMPLEX = (
    "[HACKATHON 2026] - USM INTERNAL\n"
    "Announcement: Registration is now OPEN!\n"
    "D-Day: 30 days to go\n"
    "Tempoh Pertandingan: 11–31 Mei 2026\n"
    "Masa: 8.00 AM hingga 5.00 PM\n"
    "Platform: Google Meet\n"
    "Yuran: RM50 per team\n"
    "Link daftar: https://forms.gle/xyz\n"
    "MyCSD: 50 points\n"
    "For enquiries: 012-345 6789"
)

SAMPLE_EVENT_CREATE = {
    "title": "Benchmark Test Event",
    "start_date": "15 August 2026",
    "end_date": "15 August 2026",
    "start_time": "10:00 AM",
    "end_time": "12:00 PM",
    "venue": "Online",
    "fee": "Free",
    "registration_link": "https://example.com/register",
    "has_mycsd": True,
    "raw_text": "",
}

SAMPLE_EVENT_UPDATE = {
    "title": "Updated Benchmark Event",
    "venue": "DK1 Main Hall",
}

SAMPLE_EVENT_MINIMAL = {
    "_id": "000000000000000000000001",
    "title": "Benchmark Event",
    "start_date": "15 Aug 2026",
    "end_date": None,
    "start_time": None,
    "end_time": None,
    "venue": None,
    "fee": None,
    "registration_link": None,
    "has_mycsd": False,
    "raw_text": "Benchmark Event\n15 Aug 2026",
}

SAMPLE_EVENT_FULL = {
    "_id": "000000000000000000000002",
    "title": "Creative Strategies for Dynamic Presentation",
    "start_date": "21 May 2026",
    "end_date": "21 May 2026",
    "start_time": "8:00 PM",
    "end_time": "10:00 PM",
    "venue": "Cisco Webex",
    "fee": "RM1",
    "registration_link": "https://forms.gle/abc123",
    "has_mycsd": True,
    "raw_text": SAMPLE_TYPICAL,
}

SAMPLE_SAMPLES = {
    "minimal": SAMPLE_MINIMAL,
    "typical": SAMPLE_TYPICAL,
    "complex": SAMPLE_COMPLEX,
}

# --- Configuration ---

DEFAULT_API_URL = os.getenv("PERF_API_URL", "http://localhost:8000/events")
MONGO_DETAILS = os.getenv("PERF_MONGO_DETAILS", "mongodb://localhost:27017")

QUICK_ITERATIONS = 10
FULL_ITERATIONS = 100

PERF_DB_NAME = "event_hub"
PERF_COLLECTION_PREFIX = "perf_test_"
PERF_DATA_SIZES = [0, 10, 100, 1000]

HTTP_TIMEOUT = 30.0
AI_SAMPLE_ITERATIONS = 5
