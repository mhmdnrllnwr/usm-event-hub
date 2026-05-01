"""
FILE FUNCTION: The entry point for the FastAPI application.
WHAT YOU CAN DO HERE: 
- Add new endpoints (e.g., @app.get("/search")).
- Change the URL paths.
- Add security headers or middleware.
WHEN TO CHANGE: When you need to create a new way for the Bot to talk to the API.
"""
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from models import EventCreate
from database import add_event
from engine.regex_handler import extract_links, extract_dates, check_mycsd, extract_times, extract_fee
from engine.nlp_handler import extract_entities

app = FastAPI(title="USM Event Hub API")

class RawTelegramMessage(BaseModel):
    text: str

@app.post("/events/process")
async def process_raw_message(data: RawTelegramMessage):
    raw_text = data.text
    if not raw_text:
        raise HTTPException(status_code=400, detail="No text provided")

    # Run the Engine
    nlp_results = extract_entities(raw_text)
    links = extract_links(raw_text)
    dates = extract_dates(raw_text)
    times = extract_times(raw_text) # Grabs all times found
    
    # Logic for handling multiple dates/times
    start_date = dates[0] if len(dates) > 0 else "TBD"
    
    if len(dates) > 1:
        end_date = dates[1]
    elif len(dates) == 1:
        end_date = start_date
    else:
        end_date = None
    
    start_time = times[0] if len(times) > 0 else None
    end_time = times[1] if len(times) > 1 else None # Grabs second time if exists

    # Assemble the Event
    event_data = EventCreate(
        title=nlp_results["title"],
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

    event_id = await add_event(event_data)
    return {"status": "success", "extracted_data": event_data, "id": event_id}