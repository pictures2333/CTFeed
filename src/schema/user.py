from __future__ import annotations
from typing import List, Optional

from pydantic import BaseModel, ConfigDict

from src.database.model import Skills, Status, RhythmGames

# post
class UpdateUser(BaseModel):
    status:Optional[Status]=None
    skills:Optional[List[Skills]]=None
    rhythm_games:Optional[List[RhythmGames]]=None


# get
class DiscordUser(BaseModel):
    display_name:str
    id:int
    name:str


class UserSimple(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    
    discord_id:int
    
    status:Status
    skills:List[Skills]
    rhythm_games:List[RhythmGames]
    
    discord:Optional[DiscordUser]=None


class User(UserSimple):
    events:List["EventSimple"]
