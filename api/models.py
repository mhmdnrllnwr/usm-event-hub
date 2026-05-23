"""
FILE FUNCTION: Defines the 'shape' of your data using Pydantic.
WHAT YOU CAN DO HERE: 
- Add new fields to the Event (e.g., organizer, category).
- Change field types (e.g., change date from str to datetime).
- Set default values (like venue="Online" by default).
WHEN TO CHANGE: When the Telegram Bot starts finding new types of info you want to save.
"""
from pydantic import BaseModel, HttpUrl
from typing import Optional

class EventCreate(BaseModel):
    title: str
    image_url: Optional[str] = None
    start_date: Optional[str] = None
    end_date: Optional[str] = None
    start_time: Optional[str] = None
    end_time: Optional[str] = None
    venue: Optional[str] = None
    fee: Optional[str] = None
    registration_link: Optional[HttpUrl] = None
    has_mycsd: bool = False
    creator_id: Optional[int] = None
    raw_text: str