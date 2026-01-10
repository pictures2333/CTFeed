from typing import Optional, List, Dict, Any
from datetime import datetime
import logging

from sqlalchemy.ext.asyncio import AsyncSession
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
async def _join_channel(session:AsyncSession, channel:discord.TextChannel, event_db:Event, member:discord.Member):
    """
    Only join channel
    """
    discord_joined = False
    try:
        # check database
        if await crud.read_user_in_event(session, event_db.id, member.id):
            raise HTTPException(status_code=409, detail=f"member {member.name} (id={member.id}) has joined the channel")
        
        # discord
        await channel.set_permissions(member, view_channel=True)
        discord_joined = True
                
        # update database
        await crud.join_event(session, event_db.id, member.id)
    except Exception as e:
        # rollback
        if discord_joined:
            await channel.set_permissions(member, view_channel=False)
                
        # raise exception
        if isinstance(e, HTTPException):
            raise
        logger.error(f"user (id={member.id}) failed to join channel (id={channel.id}) of event (id={event_db.id}): {str(e)}")
        raise HTTPException(status_code=500, detail=f"user (id={member.id}) failed to join channel (id={channel.id}) of event (id={event_db.id})")
            
    # send notification
    try:
        await channel.send(embed=discord.Embed(
            color=discord.Color.green(),
            title=f"{member.display_name} joined the channel"
        ))
    except Exception as e:
        logger.error(f"failed to send notification to channel (id={channel.id}): {str(e)}")
        # ignore exception
            
    return


async def create_and_join_channel(bot:commands.Bot, member:discord.Member, event_db_id:int):
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
        
        # check whether channel was created
        if (channel_id := event_db.channel_id) is None or \
            (channel := guild.get_channel(channel_id)) is None:
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
                guild.me: discord.PermissionOverwrite(view_channel=True)
            }
            
            sc:Optional[discord.ScheduledEvent] = None
            channel:Optional[discord.TextChannel] = None
            try:
                # clear old users
                # ensure database and the ACL of discord channel is synced
                await crud.delete_user_in_event(session, event_db.id)
                
                # create scheduled event - todo
                if ctftime_event:
                    sc = await guild.create_scheduled_event(
                        location=f"https://ctftime.org/event/{event_db.event_id}",
                        name=event_db.title,
                        start_time=datetime.fromtimestamp(event_db.start),
                        end_time=datetime.fromtimestamp(event_db.finish),
                    )
                    if sc is None:
                        raise RuntimeError(f"failed to create scheduled event on Discord")
                
                # create channel
                channel = await guild.create_text_channel(event_db.title, category=category, overwrites=overwrites)
                
                # update database
                if ctftime_event:
                    event_db = await crud.update_event(session, id=event_db.id, channel_id=channel.id, scheduled_event_id=sc.id)
                else:
                    event_db = await crud.update_event(session, id=event_db.id, channel_id=channel.id)
            except Exception as e:
                # rollback
                if not(channel is None):
                    await channel.delete(reason="rollback")
                
                if not(sc is None):
                    await sc.delete()
                
                # raise exception
                logger.error(f"failed to create channel for event (id={event_db.id}): {str(e)}")
                raise HTTPException(status_code=500, detail=f"failed to create channel for event (id={event_db.id})")
            
            logger.info(f"User {member.name} (id={member.id}) created channel {channel.name} (id={channel.id})")
            
            try:
                # send notification
                if ctftime_event:
                    embed = await create_event_embed(event_api, f"{member.display_name} raised {event_db.title}")
                else:
                    embed = discord.Embed(
                        color=discord.Color.green(),
                        title=f"{member.display_name} created the channel"
                    )
                await channel.send(embed=embed)
            except Exception as e:
                logger.error(f"failed to send notification to channel (id={channel.id}): {str(e)}")
                # ignore exception
        
        # channel created -> join
        await _join_channel(session, channel, event_db, member)
        
        return


async def create_custom_event(bot:commands.Bot, title:str):
    """
    Create a custom event
    
    Raises:
        HTTPException
    """
    # get guild
    guild:discord.Guild = bot.get_guild(settings.GUILD_ID)
    if guild is None:
        errmsg = f"invalid guild id={settings.GUILD_ID}"
        logger.error(errmsg)
        raise HTTPException(status_code=500, detail=errmsg)
    
    # get announcement channel
    anno_channel:discord.TextChannel = guild.get_channel(settings.ANNOUNCEMENT_CHANNEL_ID)
    if anno_channel is None:
        errmsg = f"Can not get channnel id={settings.ANNOUNCEMENT_CHANNEL_ID} from guild {guild.name} (id={guild.id})"
        logger.error(errmsg)
        raise HTTPException(status_code=500, detail=errmsg)
    
    # database
    async with get_db() as session:
        try:
            event_db = await crud.create_event(session, title=title)
        except Exception as e:
            logger.error(f"failed to create an event on database: {str(e)}")
            raise HTTPException(status_code=500, detail="failed to create an event on database")
    
    # send notification
    view = discord.ui.View(timeout=None)
    view.add_item(
        discord.ui.Button(
            label='Join',
            style=discord.ButtonStyle.blurple,
            custom_id=f"ctf_join_channel:event:{event_db.id}",
            emoji=settings.EMOJI,
        )
    )
    try:
        await anno_channel.send(embed=discord.Embed(
            color=discord.Color.green(),
            title=f"Click the button to join {title}"
        ), view=view)
    except Exception as e:
        logger.error(f"failed to send notification to announcement channel: {str(e)}")
        # ignore exception
    
    return