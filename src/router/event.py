from typing import List, Literal, Optional
from datetime import datetime
import logging

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from discord.ext import commands

from src.backend import security
from src.backend import get_user
from src.backend import join_channel
from src.bot import get_bot
from src.database.database import fastapi_get_db
from src import schema
from src import crud

# logger
logger = logging.getLogger("uvicorn")

# router
router = APIRouter(prefix="/event")

# c
# create custom event
...

# r
@router.get("/")
@router.get("/{id}")
async def read_event(
    id:Optional[int]=None,
    type:Optional[Literal["ctftime", "custom"]]=None,
    archived:Optional[bool]=None,
    db:AsyncSession=Depends(fastapi_get_db),
    u=Depends(security.fastapi_check_user),
) -> List[schema.Event]:
    """
    type: ctftime, custom or None (all)
    
    archive: True, False or None (all)
    """
    time_now = int(datetime.now().timestamp())
    try:
        events = await crud.read_event(db, id=id, type=type, archived=archived)
        if len(events) == 0:
            raise HTTPException(status_code=404)
        
        result = []
        for event in events:
            users = []
            for u in event.users:
                try:
                    users.append(await get_user.get_user(u.discord_id))
                except:
                    users.append(schema.UserSimple(
                        discord_id=u.discord_id,
                        status=u.status,
                        skills=u.skills,
                        rhythm_games=u.rhythm_games,
                        discord=None
                    ))
            
            r = schema.Event(
                id=event.id,
                archived=event.archived,
                title=event.title,
                channel_id=event.channel_id,
                scheduled_event_id=event.scheduled_event_id,
                type="custom" if event.event_id is None else "ctftime",
                users=users,
            )
            if not(event.event_id is None):
                # ctftime events
                r.event_id = event.event_id
                r.start = event.start
                r.finish = event.finish
                r.now_running = (True if event.start <= time_now and event.finish >= time_now else False)
            
            result.append(r)
        
        return result
    except Exception as e:
        if isinstance(e, HTTPException):
            raise
        logger.error(f"failed to get events: {str(e)}")
        raise HTTPException(status_code=500, detail="failed to get events")
        

@router.get("/{id}/join")
async def join_event(
    id:int,
    u=Depends(security.fastapi_check_user),
    bot:commands.Bot=Depends(get_bot)
) -> schema.General:
    db_user, member = u
    await join_channel.create_and_join_channel(bot, member, id)
    return schema.General(success=True, message="ok")


# archive
