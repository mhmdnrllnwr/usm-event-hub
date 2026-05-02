import unicodedata
import os
import re
from fastapi.staticfiles import StaticFiles
from fastapi import FastAPI, HTTPException, Query
from pydantic import BaseModel
from typing import Optional
from models import EventCreate
from database import add_event, check_event_exists, get_events
from engine.regex_handler import extract_links, extract_dates, check_mycsd, extract_times, extract_fee
from engine.nlp_handler import extract_entities
from utils.image_handler import download_telegram_image

app = FastAPI(title="USM Event Hub API")

# Create the directory if it doesn't exist
UPLOAD_DIR = "static/posters"
os.makedirs(UPLOAD_DIR, exist_ok=True)

# Mount the static directory
app.mount("/static", StaticFiles(directory="static"), name="static")

# Model for incoming data from the Telegram Bot
class RawTelegramMessage(BaseModel):
    text: str
    image_url: Optional[str] = None

@app.get("/events")
async def fetch_events(
    search: Optional[str] = Query(None, description="Search regex on title"),
    fee: Optional[str] = Query(None, description="Filter for 'Free'"),
    has_mycsd: Optional[bool] = Query(None, description="Boolean flag for mycsd requirement")
):
    free_only = False
    if fee and fee.lower() == "free":
        free_only = True
        
    mycsd_only = False
    if has_mycsd is True:
        mycsd_only = True
        
    events = await get_events(search_term=search, free_only=free_only, mycsd_only=mycsd_only)
    return {"status": "success", "events": events}

@app.post("/events/process")
async def process_raw_message(data: RawTelegramMessage):
    # STEP 0: NORMALIZE FANCY FONTS
    # This converts mathematical/fancy symbols (e.g., 𝟏𝟕𝐭𝐡) into standard text
    raw_text = unicodedata.normalize('NFKC', data.text)
    
    if not raw_text:
        raise HTTPException(status_code=400, detail="No text provided")

    # 1. Run NLP Engine
    nlp_results = extract_entities(raw_text)
    
    # 2. Run Regex Engine to find all candidates
    links = extract_links(raw_text)
    
    # Use spaCy for dates and times as it's more accurate for context than broad dateparser
    dates = nlp_results.get("date_spacy", [])
    times = nlp_results.get("time_spacy", [])
    
    # 3. ADVANCED DATE LOGIC
    # This handles ranges (12-13 April) and mirrors single dates
    if len(dates) > 0:
        first_date_str = dates[0]
        
        # Check if already stated as a range "X to Y" or "X hingga Y"
        if re.search(r'\s+(to|hingga)\s+', first_date_str, re.IGNORECASE):
            parts = re.split(r'\s+(?:to|hingga)\s+', first_date_str, flags=re.IGNORECASE)
            start_date = parts[0].strip()
            end_date = parts[1].strip()
        # Scenario A: Detect a range like "12-13 April 2025"
        elif "-" in first_date_str:
            try:
                parts = first_date_str.split() # Result: ['12-13', 'April', '2025']
                day_range = parts[0].split("-") # Result: ['12', '13']
                month_year = " ".join(parts[1:]) # Result: "April 2025"
                
                start_date = f"{day_range[0]} {month_year}"
                end_date = f"{day_range[1]} {month_year}"
            except Exception:
                # Fallback if splitting fails (e.g. weird spacing)
                start_date = first_date_str
                end_date = first_date_str
        else:
            # Scenario B: Single date found (13 April 2025)
            # We mirror it to avoid picking up the registration deadline (dates[1])
            start_date = first_date_str
            end_date = first_date_str
    else:
        # Scenario C: No date found
        start_date = "TBD"
        end_date = None
    
    # 4. Time Logic (Supports a.m./p.m. with dots)
    start_time = times[0] if len(times) > 0 else None
    end_time = times[1] if len(times) > 1 else None

    # NEW: Download the image if it exists
    local_image_path = None
    if data.image_url: # This is currently holding the file_id
        local_image_path = await download_telegram_image(
            data.image_url, 
            os.getenv("BOT_TOKEN")
        )

    # 5. Build Final Event Object
    event_data = EventCreate(
        title=nlp_results["title"],
        image_url=local_image_path, 
        start_date=start_date,
        end_date=end_date,
        start_time=start_time,
        end_time=end_time,
        venue=nlp_results["venue"],
        fee=extract_fee(raw_text),
        registration_link=links[0] if links else "https://t.me/usm_hub",
        has_mycsd=check_mycsd(raw_text),
        raw_text=raw_text
    )

    # 5.5 Check for duplicates
    is_duplicate = await check_event_exists(event_data.title, event_data.start_date)
    if is_duplicate:
        raise HTTPException(status_code=409, detail="Event already exists")

    # 6. Save to MongoDB
    event_id = await add_event(event_data)
    
    return {
        "status": "success", 
        "extracted_data": event_data, 
        "id": str(event_id)
    }