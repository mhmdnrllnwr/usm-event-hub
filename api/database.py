"""
FILE FUNCTION: Handles the connection to MongoDB and data operations.
WHAT YOU CAN DO HERE: 
- Change the Database or Collection names.
- Add logic to check for duplicates before saving.
- Create functions to 'Search' or 'Delete' events.
WHEN TO CHANGE: When you want to change HOW data is stored or retrieved.
"""
import os
from motor.motor_asyncio import AsyncIOMotorClient
from models import EventCreate # Ensure NO DOT here

MONGO_DETAILS = os.getenv("MONGO_DETAILS", "mongodb://mongodb:27017")

client = AsyncIOMotorClient(MONGO_DETAILS)
database = client.event_hub
event_collection = database.get_collection("events_collection")

async def check_event_exists(title: str, start_date: str) -> bool:
    event = await event_collection.find_one({"title": title, "start_date": start_date})
    return bool(event)

async def add_event(event_data: EventCreate):
    event_dict = event_data.model_dump() # Using model_dump() for Pydantic v2
    event_dict["registration_link"] = str(event_dict["registration_link"])
    
    new_event = await event_collection.insert_one(event_dict)
    return str(new_event.inserted_id)