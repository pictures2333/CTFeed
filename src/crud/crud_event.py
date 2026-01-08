from typing import List, Optional, Tuple
from datetime import datetime, timedelta
import logging

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload
import sqlalchemy

from src.database.model import Event
from src.config import settings

# logger
logger = logging.getLogger("uvicorn")

# create
async def create_event(
    db:AsyncSession,
    # event attrbutes
    event_id:Optional[int],
    title:str,
    start:Optional[int],
    finish:Optional[int],
) -> Optional[Event]:
    """
    create event
    
    create a CTFTime event needs title, event_id, start, finish
    create a custom event only needs title (title as channel name)
    """
    event = Event(title=title)
    
    if not(event_id is None):
        if start is None or finish is None:
            return None
        event.event_id = event_id
        event.start = start
        event.finish = finish
    
    try:
        db.add(event)
        await db.commit()
        await db.refresh(event)
        return event
    except Exception as e:
        await db.rollback()
        logger.error(f"failed to create event: {str(e)}")
        return None


# read
async def read_ctftime_event(
    db:AsyncSession,
    include_archived:Optional[bool]=True,
    id:Optional[int]=None,
    event_id:Optional[int]=None,
    channel_id:Optional[int]=None,
    finish_after:Optional[int]=(datetime.now() + timedelta(days=settings.DATABASE_SEARCH_DAYS)).timestamp(),
) -> Tuple[List[Event], Exception]:
    try:
        query = sqlalchemy.select(Event)
        query = query.options(selectinload(Event.users))
        query = query.options(selectinload(Event.challenges))
        
        if not include_archived:
            query = query.where(Event.archived == False)
        
        if not(event_id is None):
            query = query.where(Event.event_id == event_id)
        else:
            # where event_id != null -> CTFTime events
            query = query.where(Event.event_id != None)
            
        if not(id is None):
            query = query.where(Event.id == id)
        
        if not(channel_id is None):
            query = query.where(Event.channel_id == channel_id)
            
        if not(finish_after is None):
            query = query.where(Event.finish >= finish_after)
        
        query = query.order_by(sqlalchemy.desc(Event.finish))
        result = await db.execute(query)
        return result.scalars().all(), None
    except Exception as e:
        logger.error(f"failed to read events: {str(e)}")
        return [], e
    
    
async def read_custom_event(
    db:AsyncSession,
    include_archived:Optional[bool]=True,
    id:Optional[int]=None,
    channel_id:Optional[int]=None,
) -> Tuple[List[Event], Exception]:
    try:
        query = sqlalchemy.select(Event)
        query = query.options(selectinload(Event.users))
        query = query.options(selectinload(Event.challenges))
        
        if not include_archived:
            query = query.where(Event.archived == False)
            
        # event_id is None -> custom events
        query = query.where(Event.event_id == None)
        
        if not(channel_id is None):
            query = query.where(Event.channel_id == channel_id)
            
        if not(id is None):
            query = query.where(Event.id == id)
            
        result = await db.execute(query)
        return result.scalars().all(), None
    except Exception as e:
        logger.error(f"failed to read events: {str(e)}")
        return [], e
    

async def read_ctftime_event_need_archive(
    db:AsyncSession,
    finish_before:Optional[int]=(datetime.now() + timedelta(days=settings.DATABASE_SEARCH_DAYS)).timestamp(),
) -> Tuple[List[Event], Exception]:
    try:
        query = sqlalchemy.select(Event) \
            .options(selectinload(Event.users)) \
            .options(selectinload(Event.challenges)) \
            .where(Event.archived == False) \
            .where(Event.finish < finish_before)
        result = await db.execute(query)
        return result.scalars().all(), None
    except Exception as e:
        logger.error(f"failed to read events: {str(e)}")
        return [], e


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
) -> Optional[Event]:
    try:
        # find
        query = sqlalchemy.select(Event).where(Event.id == id)
        event = (await db.execute(query)).scalar_one_or_none()
        if event is None:
            return None
        
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
    except Exception as e:
        await db.rollback()
        logger.error(f"failed to update event(id={id}): {str(e)}")
        return None


# delete
async def delete_event(
    db:AsyncSession,
    id:int,
) -> Exception:
    try:
        stmt = sqlalchemy.delete(Event).where(Event.id == id)
        await db.execute(stmt)
        await db.commit()
        return None
    except Exception as e:
        await db.rollback()
        logger.error(f"failed to delete event: {str(e)}")
        return e