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
    start_date: str
    end_date: Optional[str] = None
    start_time: Optional[str] = None
    end_time: Optional[str] = None
    venue: Optional[str] = "Online"
    fee: Optional[str] = "Free"
    registration_link: HttpUrl
    has_mycsd: bool = False
    raw_text: str