import os
from typing import Optional
from datetime import datetime, timezone
from bson import ObjectId
import dateparser
from motor.motor_asyncio import AsyncIOMotorClient
from models import EventCreate

MONGO_DETAILS = os.getenv("MONGO_DETAILS", "mongodb://mongodb:27017")

client = AsyncIOMotorClient(MONGO_DETAILS)
database = client.event_hub
event_collection = database.get_collection("events_collection")


def compute_status(event: dict) -> str:
    date_str = event.get("end_date") or event.get("start_date")
    if not date_str or date_str == "TBD":
        return "upcoming"
    parsed = dateparser.parse(date_str)
    if not parsed:
        return "upcoming"
    now = datetime.now(timezone.utc).replace(tzinfo=None) if parsed.tzinfo else datetime.now()
    return "active" if parsed.date() >= now.date() else "expired"


def _matches_status(event: dict, status: str) -> bool:
    return compute_status(event) == status


async def get_events(
    search_term: str = None,
    free_only: bool = False,
    paid_only: bool = False,
    mycsd_only: bool = False,
    creator_id: int = None,
    status: str = None,
    sort: str = None,
    page: int = 1,
    per_page: int = 10,
):
    query = {}
    if search_term:
        query["$or"] = [
            {"title": {"$regex": search_term, "$options": "i"}},
            {"start_date": {"$regex": search_term, "$options": "i"}},
            {"$and": [{"end_date": {"$type": "string"}}, {"end_date": {"$regex": search_term, "$options": "i"}}]},
            {"$and": [{"venue": {"$type": "string"}}, {"venue": {"$regex": search_term, "$options": "i"}}]},
            {"$and": [{"fee": {"$type": "string"}}, {"fee": {"$regex": search_term, "$options": "i"}}]},
            {"raw_text": {"$regex": search_term, "$options": "i"}},
        ]
    if free_only:
        query["fee"] = {"$regex": "free|percuma|0", "$options": "i"}
    if paid_only:
        query["fee"] = {"$regex": "paid", "$options": "i"}
    if mycsd_only:
        query["has_mycsd"] = True
    if creator_id is not None:
        query["creator_id"] = creator_id

    cursor = event_collection.find(query).sort("_id", -1)
    all_events = []
    async for document in cursor:
        document["_id"] = str(document["_id"])
        document["status"] = compute_status(document)
        all_events.append(document)

    # Date-aware sort: parse start_date strings into datetimes
    if sort == "date_asc":
        for e in all_events:
            d = e.get("start_date")
            if d and d != "TBD":
                parsed = dateparser.parse(d)
                e["_parsed_date"] = parsed if parsed else datetime.max
            else:
                e["_parsed_date"] = datetime.max
        all_events.sort(key=lambda e: e["_parsed_date"])
    elif sort == "date_desc":
        for e in all_events:
            d = e.get("start_date")
            if d and d != "TBD":
                parsed = dateparser.parse(d)
                e["_parsed_date"] = parsed if parsed else datetime.min
            else:
                e["_parsed_date"] = datetime.min
        all_events.sort(key=lambda e: e["_parsed_date"], reverse=True)

    # Post-filter by status (computed field, not in DB)
    if status:
        all_events = [e for e in all_events if _matches_status(e, status)]

    # Paginate
    start = (page - 1) * per_page
    page_events = all_events[start:start + per_page]
    total = len(all_events)

    return {"events": page_events, "total": total, "page": page, "per_page": per_page}


async def get_event_by_id(event_id: str) -> dict | None:
    try:
        doc = await event_collection.find_one({"_id": ObjectId(event_id)})
    except Exception:
        return None
    if not doc:
        return None
    doc["_id"] = str(doc["_id"])
    doc["status"] = compute_status(doc)
    return doc


async def check_event_exists(title: str, start_date: Optional[str]) -> bool:
    event = await event_collection.find_one({"title": title, "start_date": start_date})
    return bool(event)


async def add_event(event_data: EventCreate):
    event_dict = event_data.model_dump()
    if event_dict.get("registration_link"):
        event_dict["registration_link"] = str(event_dict["registration_link"])
    new_event = await event_collection.insert_one(event_dict)
    return str(new_event.inserted_id)


async def update_event(event_id: str, update_data: dict) -> bool:
    try:
        result = await event_collection.update_one(
            {"_id": ObjectId(event_id)},
            {"$set": update_data}
        )
        return result.matched_count > 0
    except Exception:
        return False


async def delete_event(event_id: str) -> bool:
    try:
        result = await event_collection.delete_one({"_id": ObjectId(event_id)})
        return result.deleted_count > 0
    except Exception:
        return False
