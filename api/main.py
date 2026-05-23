import unicodedata
import os
import re
import logging
from fastapi.staticfiles import StaticFiles
from fastapi import FastAPI, HTTPException, Query
from pydantic import BaseModel
from typing import Optional
from models import EventCreate
from database import add_event, check_event_exists, get_events, get_event_by_id, update_event, delete_event, compute_status
from engine.regex_handler import extract_links, extract_dates, check_mycsd, extract_times, extract_fee
from engine.nlp_handler import extract_entities
from engine.config import TITLE_CONFIDENCE_THRESHOLD
from engine.ai_handler import validate_title, validate_event
from utils.image_handler import download_telegram_image

app = FastAPI(title="USM Event Hub API")
logger = logging.getLogger(__name__)


def validate_date(date_str: str | None) -> str | None:
    if not date_str:
        return None
    if date_str == "TBD":
        return "TBD"
    has_day = bool(re.search(r'(?<!\d)\d{1,2}(?!\d)', date_str))
    has_month = bool(re.search(r'[A-Za-z]{3,}', date_str))
    has_year = bool(re.search(r'\b\d{4}\b', date_str))
    return date_str if (has_day and has_month and has_year) else None


UPLOAD_DIR = "static/posters"
os.makedirs(UPLOAD_DIR, exist_ok=True)
app.mount("/static", StaticFiles(directory="static"), name="static")


class RawTelegramMessage(BaseModel):
    text: str
    image_url: Optional[str] = None
    creator_id: Optional[int] = None


class EventUpdate(BaseModel):
    title: Optional[str] = None
    start_date: Optional[str] = None
    end_date: Optional[str] = None
    start_time: Optional[str] = None
    end_time: Optional[str] = None
    venue: Optional[str] = None
    fee: Optional[str] = None
    registration_link: Optional[str] = None
    has_mycsd: Optional[bool] = None


@app.get("/events")
async def fetch_events(
    search: Optional[str] = Query(None),
    fee: Optional[str] = Query(None),
    paid: Optional[bool] = Query(None),
    has_mycsd: Optional[bool] = Query(None),
    creator_id: Optional[int] = Query(None),
    status: Optional[str] = Query(None),
    page: int = Query(1, ge=1),
    per_page: int = Query(10, ge=1, le=50),
):
    free_only = fee and fee.lower() == "free"
    paid_only = paid is True
    mycsd_only = has_mycsd is True

    result = await get_events(
        search_term=search,
        free_only=free_only,
        paid_only=paid_only,
        mycsd_only=mycsd_only,
        creator_id=creator_id,
        status=status,
        page=page,
        per_page=per_page,
    )
    return {"status": "success", **result}


@app.get("/events/{event_id}")
async def fetch_event(event_id: str):
    event = await get_event_by_id(event_id)
    if not event:
        raise HTTPException(status_code=404, detail="Event not found")
    return {"status": "success", "event": event}


@app.post("/events/process")
async def process_raw_message(data: RawTelegramMessage):
    raw_text = unicodedata.normalize('NFKC', data.text)

    if not raw_text:
        raise HTTPException(status_code=400, detail="No text provided")

    nlp_results = extract_entities(raw_text)

    title_scores = nlp_results.get("title_scores", [])
    if title_scores and max(title_scores) < TITLE_CONFIDENCE_THRESHOLD:
        candidates = nlp_results.get("title_candidates", [])
        if candidates:
            ai_title = await validate_title(candidates, raw_text)
            if ai_title and ai_title != nlp_results["title"]:
                logger.info(f"AI corrected title: '{nlp_results['title']}' -> '{ai_title}'")
                nlp_results["title"] = ai_title

    links = extract_links(raw_text)
    dates = nlp_results.get("date_spacy", [])
    times = nlp_results.get("time_spacy", [])

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

    if len(dates) > 0:
        first_date_str = dates[0]
        first_date_str = re.sub(r'[-–—]', '-', first_date_str)

        if re.search(r'\s+(to|hingga)\s+', first_date_str, re.IGNORECASE):
            parts = re.split(r'\s+(?:to|hingga)\s+', first_date_str, flags=re.IGNORECASE)
            start_date = parts[0].strip()
            end_date = parts[1].strip()
        elif "-" in first_date_str:
            parts = first_date_str.split("-")
            p1 = parts[0].strip()
            p2 = parts[1].strip()
            p1_words = p1.split()
            if len(p1_words) >= 2 and any(char.isalpha() for char in p1):
                start_date = p1
                end_date = p2
                if not re.search(r'\b\d{4}\b', start_date):
                    year_match = re.search(r'(\b\d{4}\b)', end_date)
                    if year_match:
                        start_date = f"{start_date} {year_match.group(1)}"
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
            start_date = first_date_str
            end_date = first_date_str
    else:
        start_date = None
        end_date = None

    start_date = validate_date(start_date)
    end_date = validate_date(end_date)

    start_time = times[0] if len(times) > 0 else None
    end_time = times[1] if len(times) > 1 else None

    local_image_path = None
    if data.image_url:
        local_image_path = await download_telegram_image(
            data.image_url,
            os.getenv("BOT_TOKEN")
        )

    event_data = EventCreate(
        title=nlp_results["title"],
        image_url=local_image_path,
        start_date=start_date,
        end_date=end_date,
        start_time=start_time,
        end_time=end_time,
        venue=nlp_results.get("venue").split('\n')[0].strip() if nlp_results.get("venue") else None,
        fee=extract_fee(raw_text),
        registration_link=links[0] if links else None,
        has_mycsd=check_mycsd(raw_text),
        creator_id=data.creator_id,
        raw_text=raw_text,
    )

    is_duplicate = await check_event_exists(event_data.title, event_data.start_date)
    if is_duplicate:
        raise HTTPException(status_code=409, detail="Event already exists")

    event_id = await add_event(event_data)
    extracted = event_data.model_dump()
    extracted["status"] = compute_status(extracted)

    return {
        "status": "success",
        "extracted_data": extracted,
        "id": str(event_id),
    }


@app.post("/events")
async def create_event_manual(data: EventCreate):
    is_duplicate = await check_event_exists(data.title, data.start_date)
    if is_duplicate:
        raise HTTPException(status_code=409, detail="Event already exists")
    event_id = await add_event(data)
    return {"status": "success", "id": str(event_id)}


@app.put("/events/{event_id}")
async def update_event_endpoint(event_id: str, data: EventUpdate):
    existing = await get_event_by_id(event_id)
    if not existing:
        raise HTTPException(status_code=404, detail="Event not found")

    update_data = {k: v for k, v in data.model_dump().items() if v is not None}
    if not update_data:
        raise HTTPException(status_code=400, detail="No fields to update")

    if "registration_link" in update_data:
        update_data["registration_link"] = str(update_data["registration_link"])

    success = await update_event(event_id, update_data)
    if not success:
        raise HTTPException(status_code=500, detail="Failed to update event")

    updated = await get_event_by_id(event_id)
    return {"status": "success", "event": updated}


@app.delete("/events/{event_id}")
async def delete_event_endpoint(event_id: str):
    existing = await get_event_by_id(event_id)
    if not existing:
        raise HTTPException(status_code=404, detail="Event not found")

    success = await delete_event(event_id)
    if not success:
        raise HTTPException(status_code=500, detail="Failed to delete event")

    return {"status": "success", "message": "Event deleted"}
