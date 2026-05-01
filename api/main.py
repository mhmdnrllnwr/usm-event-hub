import unicodedata
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from typing import Optional
from models import EventCreate
from database import add_event
from engine.regex_handler import extract_links, extract_dates, check_mycsd, extract_times, extract_fee
from engine.nlp_handler import extract_entities

app = FastAPI(title="USM Event Hub API")

# Model for incoming data from the Telegram Bot
class RawTelegramMessage(BaseModel):
    text: str
    image_url: Optional[str] = None

@app.post("/events/process")
async def process_raw_message(data: RawTelegramMessage):
    # STEP 0: NORMALIZE FANCY FONTS
    # This converts mathematical/fancy symbols (e.g., 𝟏𝟕𝐭𝐡) into standard text
    raw_text = unicodedata.normalize('NFKC', data.text)
    
    if not raw_text:
        raise HTTPException(status_code=400, detail="No text provided")

    # 1. Run NLP Engine (Prioritizes first lines for Title)
    nlp_results = extract_entities(raw_text)
    
    # 2. Run Regex Engine to find all candidates
    links = extract_links(raw_text)
    dates = extract_dates(raw_text)
    times = extract_times(raw_text)
    
    # 3. ADVANCED DATE LOGIC
    # This handles ranges (12-13 April) and mirrors single dates
    if len(dates) > 0:
        first_date_str = dates[0]
        
        # Scenario A: Detect a range like "12-13 April 2025"
        if "-" in first_date_str:
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

    # 5. Build Final Event Object
    event_data = EventCreate(
        title=nlp_results["title"],
        image_url=data.image_url, 
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

    # 6. Save to MongoDB
    event_id = await add_event(event_data)
    
    return {
        "status": "success", 
        "extracted_data": event_data, 
        "id": str(event_id)
    }