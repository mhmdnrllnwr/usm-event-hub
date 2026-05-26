import os
from typing import Optional
from datetime import datetime, timezone, timedelta
from bson import ObjectId
import dateparser
from motor.motor_asyncio import AsyncIOMotorClient
from models import EventCreate

MONGO_DETAILS = os.getenv("MONGO_DETAILS", "mongodb://mongodb:27017")

client = AsyncIOMotorClient(MONGO_DETAILS)
database = client.event_hub
event_collection = database.get_collection("events_collection")

_INDEXES_ENSURED = False

DATE_FORMATS = [
    "%d %B %Y",      # 15 August 2026
    "%d %b %Y",       # 15 Aug 2026
    "%B %d, %Y",      # August 15, 2026
    "%b %d, %Y",      # Aug 15, 2026
    "%d/%m/%Y",       # 15/08/2026
    "%Y-%m-%d",       # 2026-08-15
]


async def ensure_indexes():
    global _INDEXES_ENSURED
    if _INDEXES_ENSURED:
        return
    await event_collection.create_index([("_status", 1), ("_parsed_start", 1)])
    await event_collection.create_index([("creator_id", 1)])
    await event_collection.create_index([("title", "text")])
    _INDEXES_ENSURED = True


def _fast_parse_date(date_str: str) -> Optional[datetime]:
    """Try known date formats first. Falls back to dateparser."""
    if not date_str or date_str == "TBD":
        return None
    for fmt in DATE_FORMATS:
        try:
            return datetime.strptime(date_str, fmt)
        except ValueError:
            continue
    parsed = dateparser.parse(date_str)
    return parsed.replace(tzinfo=None) if parsed and parsed.tzinfo else parsed


def _compute_status_static(event: dict) -> str:
    """Compute status from event dict without calling dateparser.parse."""
    date_str = event.get("end_date") or event.get("start_date")
    if not date_str or date_str == "TBD":
        return "upcoming"
    parsed = _fast_parse_date(date_str)
    if not parsed:
        return "upcoming"
    now = datetime.now(timezone.utc).replace(tzinfo=None) if parsed.tzinfo else datetime.now()
    return "active" if parsed.date() >= now.date() else "expired"


def compute_status(event: dict) -> str:
    return _compute_status_static(event)


def _matches_status(event: dict, status: str) -> bool:
    return _compute_status_static(event) == status


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
    await ensure_indexes()

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

    # Status: use pre-computed _status field for fast filtering.
    # Include docs without _status (old data) — they get post-filtered.
    status_post_filter = False
    if status:
        if query:
            # Merge status into query with $and
            query = {
                "$and": [
                    {k: v for k, v in query.items()},
                    {"$or": [{"_status": status}, {"_status": {"$exists": False}}]},
                ]
            }
        else:
            query["$or"] = [{"_status": status}, {"_status": {"$exists": False}}]
        status_post_filter = True

    # Count total matching docs
    total = await event_collection.count_documents(query)

    # Sort: use pre-computed _parsed_start when available, fall back to _id
    if sort == "date_asc":
        sort_tuple = [("_parsed_start", 1), ("_id", -1)]
    elif sort == "date_desc":
        sort_tuple = [("_parsed_start", -1), ("_id", -1)]
    else:
        sort_tuple = [("_id", -1)]

    # DB-level pagination
    skip = (page - 1) * per_page
    cursor = event_collection.find(query).sort(sort_tuple).skip(skip).limit(per_page)

    events = []
    async for document in cursor:
        document["_id"] = str(document["_id"])

        # Use pre-computed status if available
        if "_status" in document:
            document["status"] = document["_status"]
        else:
            document["status"] = _compute_status_static(document)

        # Clean up internal fields from output
        document.pop("_parsed_start", None)
        document.pop("_status", None)

        events.append(document)

    # Post-filter old docs that had no _status field (only if status filter active)
    if status_post_filter and status:
        events = [e for e in events if e["status"] == status]

    return {"events": events, "total": total, "page": page, "per_page": per_page}


async def get_event_by_id(event_id: str) -> dict | None:
    try:
        doc = await event_collection.find_one({"_id": ObjectId(event_id)})
    except Exception:
        return None
    if not doc:
        return None
    doc["_id"] = str(doc["_id"])
    if "_status" in doc:
        doc["status"] = doc["_status"]
        doc.pop("_status", None)
        doc.pop("_parsed_start", None)
    else:
        doc["status"] = _compute_status_static(doc)
    return doc


async def check_event_exists(title: str, start_date: Optional[str]) -> bool:
    event = await event_collection.find_one({"title": title, "start_date": start_date})
    return bool(event)


async def add_event(event_data: EventCreate):
    event_dict = event_data.model_dump()
    if event_dict.get("registration_link"):
        event_dict["registration_link"] = str(event_dict["registration_link"])

    # Pre-compute _status and _parsed_start for fast queries
    event_dict["_status"] = _compute_status_static(event_dict)
    parsed = _fast_parse_date(event_dict.get("start_date"))
    event_dict["_parsed_start"] = parsed.isoformat() if parsed else None

    new_event = await event_collection.insert_one(event_dict)
    return str(new_event.inserted_id)


async def update_event(event_id: str, update_data: dict) -> bool:
    # Recompute _status and _parsed_start if date fields changed
    if any(k in update_data for k in ("start_date", "end_date")):
        doc = await event_collection.find_one({"_id": ObjectId(event_id)})
        if doc:
            merged = {**doc, **update_data}
            update_data["_status"] = _compute_status_static(merged)
            parsed = _fast_parse_date(merged.get("start_date"))
            update_data["_parsed_start"] = parsed.isoformat() if parsed else None

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
