from datetime import datetime

from sqlalchemy.ext.asyncio import AsyncSession
from fastapi import HTTPException

from src.backend import security
from src.schema import User, DiscordUser, EventSimple

import logging
logger = logging.getLogger("uvicorn")

async def get_user(discord_id:int) -> User:
    try:
        u = await security.auto_register_and_check_user(discord_id, False, False)
    except:
        raise HTTPException(status_code=404, detail=f"invalid user (discord_id={discord_id})")
    db_user, member = u
    
    time_now = int(datetime.now().timestamp())
    
    events = []
    for event in db_user.events:
        _ = EventSimple(
            id=event.id,
            archived=event.archived,
            title=event.title,
            channel_id=event.channel_id,
            scheduled_event_id=event.scheduled_event_id,
            type="custom" if event.event_id is None else "ctftime"
        )
        if not(event.event_id is None):
            # ctftime events
            _.event_id = event.event_id
            _.start = event.start
            _.finish = event.finish
            _.now_running = (True if event.start <= time_now and event.finish >= time_now else False)
        events.append(_)
    
    return User(
        discord_id=db_user.discord_id,
        status=db_user.status,
        skills=db_user.skills,
        rhythm_games=db_user.rhythm_games,
        events=events,
        discord=DiscordUser(
            display_name=member.display_name,
            id=member.id,
            name=member.name
        )
    )
