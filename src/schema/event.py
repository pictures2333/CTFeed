from __future__ import annotations

from typing import Optional, List
from pydantic import BaseModel, ConfigDict

class EventSimple(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    
    id:int
    archived:bool
    
    event_id:Optional[int]=None
    title:Optional[str]=None
    start:Optional[int]=None
    finish:Optional[int]=None
    
    channel_id:Optional[int]=None
    scheduled_event_id:Optional[int]=None


class Event(EventSimple):
    users:List["User"]
    #challenges
