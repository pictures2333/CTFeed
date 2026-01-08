from typing import Optional, Tuple, Dict, Any
from datetime import datetime
import logging

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
async def join_channel(bot:commands.Bot, member:discord.Member, event_db_id:int) -> Tuple[Exception, int]:
    """
    Join channel or create channel
    
    returns:
    - Exception and error_code
    """
    
    # get guild
    guild:discord.Guild = bot.get_guild(settings.GUILD_ID)
    if guild is None:
        logger.error(f"invalid guild id={settings.GUILD_ID}")
        return Exception(f"invalid guild id={settings.GUILD_ID}"), 500
    
    # get category
    category_id = settings.CTF_CHANNEL_CATETORY_ID
    category:discord.CategoryChannel = discord.utils.get(guild.categories, id=category_id)
    if category_id is None:
        logger.error(f"can not get category id={settings.ARCHIVE_CATEGORY_ID} from guild {guild.name} (id={guild.id})")
        return Exception(f"can not get category id={settings.ARCHIVE_CATEGORY_ID} from guild {guild.name} (id={guild.id})"), 500
    
    async with get_db() as session:
        # get event from database
        # include_archived=False -> you can't join archived events
        custom_event = 0
        event_db, err = await crud.read_ctftime_event(session, id=event_db_id, include_archived=False)
        if not(err is None):
            return Exception(f"failed to get known events from database: {str(err)}"), 500
        if len(event_db) == 0:
            # maybe custom event
            custom_event = 1
            event_db, err = await crud.read_custom_event(session, id=event_db_id, include_archived=False)
            if not(err is None):
                return Exception(f"failed to get known events from database: {str(err)}"), 500
            if len(event_db) == 0:
                return Exception(f"event id={event_db_id} not found"), 404
        event_db = event_db[0]
        
        # create or join
        if not((channel_id := event_db.channel_id) is None) and \
            not((channel := guild.get_channel(channel_id)) is None):
            # exists -> join
            try:
                if channel.permissions_for(member).view_channel == True:
                    return Exception(f"member {member.name} (id={member.id}) has joined the channel"), 400
                
                await channel.set_permissions(member, view_channel=True)
                await channel.send(embed=discord.Embed(
                    color=discord.Color.green(),
                    title=f"{member.display_name} joined the channel"
                ))
                
                logger.info(f"user {member.name} (id={member.id}) joined channel {channel.name} (id={channel.id}) of event {event_db.title} (id={event_db.id}, event_id={event_db.event_id})")
                return None, 200
            except Exception as e:
                logger.error(f"failed to join channel (id={channel_id}): {str(e)}")
                return Exception(f"failed to join channel (id={channel_id}): {str(e)}"), 500
        else:
            # not exists -> create
            event_api:Optional[Dict[str, Any]] = None
            # get event from CTFTime (CTFTime event)
            if not custom_event:
                events_api, err = await ctf_api.fetch_ctf_events(event_db.event_id)
                if not(err is None):
                    return Exception(f"failed to get event (event_id={event_db.event_id}) from CTFTime: {str(e)}"), 500
                if len(events_api) == 0:
                    return Exception(f"event (event_id={event_db.event_id}) not found (on CTFTime)"), 404
                event_api = events_api[0]
            
            overwrites = {
                guild.default_role: discord.PermissionOverwrite(view_channel=False),
                member: discord.PermissionOverwrite(view_channel=True),
                guild.me: discord.PermissionOverwrite(view_channel=True)
            }
            
            try:
                # create scheduled event
                if not custom_event:
                    sc:discord.ScheduledEvent = await guild.create_scheduled_event(
                        location=guild.name,
                        name=event_db.title,
                        start_time=datetime.fromtimestamp(event_db.start),
                        end_time=datetime.fromtimestamp(event_db.finish),
                    )
                    if sc is None:
                        raise Exception(f"failed to create scheduled event on Discord")
                
                # create channel
                new_channel = await guild.create_text_channel(event_db.title, category=category, overwrites=overwrites)
                
                if not custom_event:
                    event_db = await crud.update_event(session, id=event_db.id, channel_id=new_channel.id, scheduled_event_id=sc.id)
                else:
                    event_db = await crud.update_event(session, id=event_db.id, channel_id=new_channel.id)
                if event_db is None:
                    # rollback
                    if not custom_event:
                        await sc.delete()
                    await new_channel.delete()
                    # raise excpetion
                    raise Exception(f"failed to update event on database")
                
                # send notification
                if not custom_event:
                    embed = await create_event_embed(event_api, f"{member.display_name} raised {event_db.title}")
                else:
                    embed = discord.Embed(
                        color=discord.Color.green(),
                        title=f"{member.display_name} created the channel"
                    )
                await new_channel.send(embed=embed)
                
                logger.info(f"User {member.name} (id={member.id}) created and joined channel {new_channel.name} (id={new_channel.id})")
            except Exception as e:
                return Exception(f"failed to create channel for event (id={event_db.id}): {str(e)}"), 500

            return None, 200
