import unicodedata
import os
import re
import logging
from fastapi.staticfiles import StaticFiles
from fastapi import FastAPI, HTTPException, Query
from pydantic import BaseModel
from typing import Optional
from models import EventCreate
from database import add_event, check_event_exists, get_events, compute_status
from engine.regex_handler import extract_links, extract_dates, check_mycsd, extract_times, extract_fee
from engine.nlp_handler import extract_entities
from engine.config import TITLE_CONFIDENCE_THRESHOLD
from engine.ai_handler import validate_title, validate_event
from utils.image_handler import download_telegram_image

app = FastAPI(title="USM Event Hub API")
logger = logging.getLogger(__name__)


def validate_date(date_str: str | None) -> str | None:
    """Return date if it has day+month+year, else None."""
    if not date_str:
        return None
    if date_str == "TBD":
        return "TBD"
    has_day = bool(re.search(r'(?<!\d)\d{1,2}(?!\d)', date_str))
    has_month = bool(re.search(r'[A-Za-z]{3,}', date_str))
    has_year = bool(re.search(r'\b\d{4}\b', date_str))
    return date_str if (has_day and has_month and has_year) else None

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

    # 1.5 AI Title Validation (if confidence is low)
    title_scores = nlp_results.get("title_scores", [])
    if title_scores and max(title_scores) < TITLE_CONFIDENCE_THRESHOLD:
        candidates = nlp_results.get("title_candidates", [])
        if candidates:
            ai_title = await validate_title(candidates, raw_text)
            if ai_title and ai_title != nlp_results["title"]:
                logger.info(f"AI corrected title: '{nlp_results['title']}' -> '{ai_title}'")
                nlp_results["title"] = ai_title

    # 2. Run Regex Engine to find all candidates
    links = extract_links(raw_text)
    
    # Use spaCy for dates and times as it's more accurate for context than broad dateparser
    dates = nlp_results.get("date_spacy", [])
    times = nlp_results.get("time_spacy", [])

    # 2.5 AI Date & Time Validation (if heuristic missed dates or times)
    if not dates or not times:
        candidates = nlp_results.get("title_candidates", [])
        extracted_for_ai = {
                "date_raw": dates[0] if dates else None,
                "time_raw": times[0] if times else None,
            }
            ai_result = await validate_event(candidates, raw_text, extracted_for_ai)
            if ai_result:
                if ai_result["title"] and ai_result["title"] != nlp_results["title"]:
                    logger.info(f"AI corrected title: '{nlp_results['title']}' -> '{ai_result['title']}'")
                    nlp_results["title"] = ai_result["title"]

                if ai_result["date"]:
                    dates.insert(0, ai_result["date"])
                    logger.info(f"AI added date: '{ai_result['date']}'")

                if ai_result["time"]:
                    times.insert(0, ai_result["time"])
                    logger.info(f"AI added time: '{ai_result['time']}'")

    # 3. ADVANCED DATE LOGIC
    # This handles ranges (12-13 April) and mirrors single dates
    if len(dates) > 0:
        first_date_str = dates[0]
        # Normalize en-dashes/em-dashes to hyphens
        first_date_str = re.sub(r'[-–—]', '-', first_date_str)
        
        # Check if already stated as a range "X to Y" or "X hingga Y"
        if re.search(r'\s+(to|hingga)\s+', first_date_str, re.IGNORECASE):
            parts = re.split(r'\s+(?:to|hingga)\s+', first_date_str, flags=re.IGNORECASE)
            start_date = parts[0].strip()
            end_date = parts[1].strip()
        # Scenario A: Detect a range using hyphens
        elif "-" in first_date_str:
            parts = first_date_str.split("-")
            p1 = parts[0].strip()
            p2 = parts[1].strip()
            
            # Use a simpler rule: if the first part is explicitly longer than 2 words, it's a full date object.
            # e.g., "1 May 2026" (3 words) vs "12" (1 word)
            p1_words = p1.split()
            if len(p1_words) >= 2 and any(char.isalpha() for char in p1):
                start_date = p1
                end_date = p2
                # If p1 has month but no year, borrow year from p2
                if not re.search(r'\b\d{4}\b', start_date):
                    year_match = re.search(r'(\b\d{4}\b)', end_date)
                    if year_match:
                        start_date = f"{start_date} {year_match.group(1)}"
            # If the first part is just a number (like "12 - 13 April 2025")
            else:
                try:
                    month_year = " ".join(p2.split()[1:])
                    if month_year:
                        start_date = f"{p1} {month_year}".strip()
                    else:
                        start_date = p1
                    end_date = p2
                except Exception:
                    start_date = first_date_str
                    end_date = first_date_str
        else:
            # Scenario B: Single date found (13 April 2025)
            # We mirror it to avoid picking up the registration deadline (dates[1])
            start_date = first_date_str
            end_date = first_date_str
    else:
        # Scenario C: No date found
        start_date = None
        end_date = None

    # Validate: reject incomplete dates
    start_date = validate_date(start_date)
    end_date = validate_date(end_date)

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
        #vanue code need change
        venue=nlp_results.get("venue").split('\n')[0].strip() if nlp_results.get("venue") else None,
        fee=extract_fee(raw_text),
        registration_link=links[0] if links else None,
        has_mycsd=check_mycsd(raw_text),
        raw_text=raw_text
    )

    # 5.5 Check for duplicates
    is_duplicate = await check_event_exists(event_data.title, event_data.start_date)
    if is_duplicate:
        raise HTTPException(status_code=409, detail="Event already exists")

    # 6. Save to MongoDB
    event_id = await add_event(event_data)

    extracted = event_data.model_dump()
    extracted["status"] = compute_status(extracted)

    return {
        "status": "success",
        "extracted_data": extracted,
        "id": str(event_id)
    }