from typing import Optional, List, Dict, Any
from datetime import datetime
import logging

from fastapi import HTTPException
from discord.ext import commands
import discord

from src.database.model import Event
from src.database.database import get_db
from src import crud
from src.utils import ctf_api
from src.utils.embed_creator import create_event_embed
from src.config import settings

# logging
logger = logging.getLogger("uvicorn")

# functions
async def join_channel(bot:commands.Bot, member:discord.Member, event_db_id:int):
    """
    Join channel or create channel
    
    Raises:
        HTTPException
    """
    # get guild
    guild:discord.Guild = bot.get_guild(settings.GUILD_ID)
    if guild is None:
        errmsg = f"invalid guild id={settings.GUILD_ID}"
        logger.error(errmsg)
        raise HTTPException(status_code=500, detail=errmsg)
    
    # get category
    category_id = settings.CTF_CHANNEL_CATETORY_ID
    category:discord.CategoryChannel = discord.utils.get(guild.categories, id=category_id)
    if category_id is None:
        errmsg = f"can not get category id={settings.ARCHIVE_CATEGORY_ID} from guild {guild.name} (id={guild.id})"
        logger.error(errmsg)
        raise HTTPException(status_code=500, detail=errmsg)
    
    async with get_db() as session:
        # get event from database
        # archived=False -> Can not join archived events
        # type=None -> both ctftime and custom
        try:
            events_db:List[Event] = await crud.read_event(session, id=event_db_id, archived=False)
        except Exception as e:
            logger.error(f"failed to get event (id={event_db_id}) from database: {str(e)}")
            raise HTTPException(status_code=500, detail=f"failed to get event (id={event_db_id}) from database")
        if len(events_db) == 0:
            raise HTTPException(status_code=404, detail=f"event (id={event_db_id}) not found")
        event_db:Event = events_db[0]
        ctftime_event = False if event_db.event_id is None else True
        
        # create or join
        if not((channel_id := event_db.channel_id) is None) and \
            not((channel := guild.get_channel(channel_id)) is None):
            # exists -> join
            if channel.permissions_for(member).view_channel == True:
                raise HTTPException(status_code=409, detail=f"member {member.name} (id={member.id}) has joined the channel")
            
            try:
                await channel.set_permissions(member, view_channel=True)
            except Exception as e:
                logger.error(f"failed to join channel (id={channel_id}): {str(e)}")
                raise HTTPException(status_code=500, detail=f"failed to join channel (id={channel_id})")
            logger.info(f"user {member.name} (id={member.id}) joined channel {channel.name} (id={channel.id}) of event {event_db.title} (id={event_db.id}, event_id={event_db.event_id})")
                
            try:
                await channel.send(embed=discord.Embed(
                    color=discord.Color.green(),
                    title=f"{member.display_name} joined the channel"
                ))
            except Exception as e:
                logger.error(f"failed to send notification to channel (id={channel_id}): {str(e)}")
                # ignore exception
            
            return
        else:
            # not exists -> create
            event_api:Optional[Dict[str, Any]] = None
            # get event from CTFTime (CTFTime event)
            if ctftime_event:
                try:
                    events_api = await ctf_api.fetch_ctf_events(event_db.event_id)
                except Exception as e:
                    logger.error(f"failed to get event (event_id={event_db.event_id} from CTFTime API: {str(e)}")
                    raise HTTPException(status_code=500, detail=f"failed to get event (event_id={event_db.event_id}) from CTFTime API")
                if len(events_api) == 0:
                    raise HTTPException(status_code=404, detail=f"event (event_id={event_db.event_id}) not found (on CTFTime)")
                event_api = events_api[0]
            
            overwrites = {
                guild.default_role: discord.PermissionOverwrite(view_channel=False),
                member: discord.PermissionOverwrite(view_channel=True),
                guild.me: discord.PermissionOverwrite(view_channel=True)
            }
            
            sc:Optional[discord.ScheduledEvent] = None
            new_channel:Optional[discord.TextChannel] = None
            try:
                # create scheduled event
                if ctftime_event:
                    sc = await guild.create_scheduled_event(
                        location=guild.name,
                        name=event_db.title,
                        start_time=datetime.fromtimestamp(event_db.start),
                        end_time=datetime.fromtimestamp(event_db.finish),
                    )
                    if sc is None:
                        raise RuntimeError(f"failed to create scheduled event on Discord")
                
                # create channel
                new_channel = await guild.create_text_channel(event_db.title, category=category, overwrites=overwrites)
                
                # update database
                if ctftime_event:
                    event_db = await crud.update_event(session, id=event_db.id, channel_id=new_channel.id, scheduled_event_id=sc.id)
                else:
                    event_db = await crud.update_event(session, id=event_db.id, channel_id=new_channel.id)
            except Exception as e:
                # rollback
                if not(new_channel is None):
                    await new_channel.delete(reason="rollback")
                
                if not(sc is None):
                    await sc.delete()
                
                # raise exception
                logger.error(f"failed to create channel for event (id={event_db.id}): {str(e)}")
                raise HTTPException(status_code=500, detail=f"failed to create channel for event (id={event_db.id})")
            
            logger.info(f"User {member.name} (id={member.id}) created and joined channel {new_channel.name} (id={new_channel.id})")
            
            try:
                # send notification
                if ctftime_event:
                    embed = await create_event_embed(event_api, f"{member.display_name} raised {event_db.title}")
                else:
                    embed = discord.Embed(
                        color=discord.Color.green(),
                        title=f"{member.display_name} created the channel"
                    )
                await new_channel.send(embed=embed)
            except Exception as e:
                logger.error(f"failed to send notification to channel (id={new_channel.id}): {str(e)}")
                # ignore exception
            
            return
