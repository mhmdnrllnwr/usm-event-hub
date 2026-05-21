"""
FILE FUNCTION: Handles the connection to MongoDB and data operations.
WHAT YOU CAN DO HERE: 
- Change the Database or Collection names.
- Add logic to check for duplicates before saving.
- Create functions to 'Search' or 'Delete' events.
WHEN TO CHANGE: When you want to change HOW data is stored or retrieved.
"""
import os
from typing import Optional
from datetime import datetime, timezone
import dateparser
from motor.motor_asyncio import AsyncIOMotorClient
from models import EventCreate # Ensure NO DOT here

MONGO_DETAILS = os.getenv("MONGO_DETAILS", "mongodb://mongodb:27017")

client = AsyncIOMotorClient(MONGO_DETAILS)
database = client.event_hub
event_collection = database.get_collection("events_collection")

async def get_events(search_term: str = None, free_only: bool = False, mycsd_only: bool = False):
    query = {}
    if search_term:
        query["$or"] = [
            {"title": {"$regex": search_term, "$options": "i"}},
            {"start_date": {"$regex": search_term, "$options": "i"}},
            {"$and": [{"end_date": {"$type": "string"}}, {"end_date": {"$regex": search_term, "$options": "i"}}]},
            {"$and": [{"venue": {"$type": "string"}}, {"venue": {"$regex": search_term, "$options": "i"}}]},
            {"$and": [{"fee": {"$type": "string"}}, {"fee": {"$regex": search_term, "$options": "i"}}]},
            {"raw_text": {"$regex": search_term, "$options": "i"}}
        ]
    if free_only:
        query["fee"] = {"$regex": "free|percuma|0", "$options": "i"}
    if mycsd_only:
        query["has_mycsd"] = True

    events = []
    cursor = event_collection.find(query).sort("_id", -1).limit(10)
    async for document in cursor:
        document["_id"] = str(document["_id"])
        document["status"] = compute_status(document)
        events.append(document)
    return events



def compute_status(event: dict) -> str:
    """Return 'active', 'expired', or 'upcoming' based on event dates."""
    date_str = event.get("end_date") or event.get("start_date")
    if not date_str or date_str == "TBD":
        return "upcoming"

    parsed = dateparser.parse(date_str)
    if not parsed:
        return "upcoming"

    now = datetime.now(timezone.utc).replace(tzinfo=None) if parsed.tzinfo else datetime.now()
    return "active" if parsed.date() >= now.date() else "expired"

async def check_event_exists(title: str, start_date: Optional[str]) -> bool:
    event = await event_collection.find_one({"title": title, "start_date": start_date})
    return bool(event)

async def add_event(event_data: EventCreate):
    event_dict = event_data.model_dump() # Using model_dump() for Pydantic v2
    if event_dict.get("registration_link"):
        event_dict["registration_link"] = str(event_dict["registration_link"])
    
    new_event = await event_collection.insert_one(event_dict)
    return str(new_event.inserted_id)