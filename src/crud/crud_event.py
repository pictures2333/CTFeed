from typing import List, Optional, Literal
from datetime import datetime, timedelta

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload
import sqlalchemy

from src.database.model import Event
from src.config import settings

# create
async def create_event(
    db:AsyncSession,
    # event attrbutes
    title:str,
    event_id:Optional[int]=None,
    start:Optional[int]=None,
    finish:Optional[int]=None,
) -> Event:
    """
    create event
    - CTFTime event
        - title
        - event_id (from CTFTime)
        - start
        - finish
    - Custom event
        - title (as channel name)
    """
    event = Event(title=title)
    
    # argument check
    if not(event_id is None):
        # CTFTime
        if start is None or finish is None:
            raise ValueError("start and finish should not be None")
        event.event_id = event_id
        event.start = start
        event.finish = finish
    
    try:
        db.add(event)
        await db.commit()
        await db.refresh(event)
        return event
    except:
        await db.rollback()
        raise


# read
async def read_event(
    db:AsyncSession,
    type:Optional[Literal["ctftime", "custom"]]=None,
    archived:Optional[bool]=None,
    id:Optional[int]=None,
    channel_id:Optional[int]=None,
    # only for CTFTime events
    event_id:Optional[int]=None,
    finish_after:int=(datetime.now() + timedelta(days=settings.DATABASE_SEARCH_DAYS)).timestamp(),
) -> List[Event]:
    query = sqlalchemy.select(Event) \
        .options(selectinload(Event.users)) \
        .options(selectinload(Event.challenges))
    
    # arguments
    if not(id is None):
        query = query.where(Event.id == id)
    
    if not(channel_id is None):
        query = query.where(Event.channel_id == channel_id)
    
    if not(archived is None):
        # True, False
        # None -> query both archived and not archived
        query = query.where(Event.archived == archived)
    
    if not(type is None):
        if type == "ctftime":
            if not(event_id is None):
                query = query.where(Event.event_id == event_id)
            else:
                query = query.where(Event.event_id != None)
                
            query = query.where(Event.finish >= finish_after)
            query = query.order_by(sqlalchemy.asc(Event.finish))
        elif type == "custom":
            query = query.where(Event.event_id == None)
        else:
            raise ValueError("type should be ctftime or custom")
    
    result = await db.execute(query)
    return result.scalars().all()


async def read_ctftime_event_need_archive(
    db:AsyncSession,
    finish_before:int=(datetime.now() + timedelta(days=settings.DATABASE_SEARCH_DAYS)).timestamp(),
) -> List[Event]:
    query = sqlalchemy.select(Event) \
        .options(selectinload(Event.users)) \
        .options(selectinload(Event.challenges)) \
        .where(Event.archived == False) \
        .where(Event.finish < finish_before)
    result = await db.execute(query)
    return result.scalars().all()


# update
async def update_event(
    db:AsyncSession,
    id:int,
    archived:Optional[bool]=None,
    title:Optional[str]=None,
    start:Optional[int]=None,
    finish:Optional[int]=None,
    channel_id:Optional[int]=None,
    scheduled_event_id:Optional[int]=None,
) -> Event:
    try:
        # find
        query = sqlalchemy.select(Event).where(Event.id == id)
        event = (await db.execute(query)).scalar_one_or_none()
        if event is None:
            # not found -> deleted
            return
        
        # update
        if not(archived is None):
            event.archived = archived
        
        if not(title is None):
            event.title = title
        
        if not(start is None):
            event.start = start
            
        if not(finish is None):
            event.finish = finish
        
        if not(channel_id is None):
            event.channel_id = channel_id
            
        if not(scheduled_event_id is None):
            event.scheduled_event_id = scheduled_event_id
        
        # commit
        await db.commit()
        await db.refresh(event)
        return event
    except:
        await db.rollback()
        raise


# delete
async def delete_event(db:AsyncSession, id:int):
    try:
        stmt = sqlalchemy.delete(Event).where(Event.id == id)
        await db.execute(stmt)
        await db.commit()
    except:
        await db.rollback()
        raise