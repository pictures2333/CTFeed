from typing import List, Dict, Any, Optional
from datetime import datetime, timedelta
import logging

from discord.ext import commands, tasks
import discord

from src.config import settings
from src.database.database import get_db
from src.database.model import Event
from src.utils import ctf_api
from src import crud
from src.utils.embed_creator import create_event_embed
from src.backend import join_channel, security

# logging
logger = logging.getLogger("uvicorn")

# utils
async def detect_event_new(anno_channel:discord.TextChannel):
    """
    Detect new CTF event on CTFTime
    """
    async with get_db() as session:
        try:
            all_events_api = await ctf_api.fetch_ctf_events()
        except Exception as e:
            logger.error(f"failed to get CTF events from CTFTime: {str(e)}, skipped...")
            return
        
        # get all events in database that finish after now+DATABASE_SEARCH_DAYS (for example (now-90))
        # archive=None 避免 archive 但還在追蹤範圍內導致漏掉
        try:
            known_events_db = await crud.read_event(session, type="ctftime", archived=None)
        except Exception as e:
            logger.error(f"failed to get known CTF events from database: {str(e)}, skipped...")
            return
        known_events_db_event_id = [ event.event_id for event in known_events_db ]
         
        for event_api in all_events_api:
            event_id = event_api["id"]
            if event_id not in known_events_db_event_id: # new event detected
                logger.info(f"new CTF event detected: {event_api["title"]}(event_id={event_id})")
                try:
                    # database
                    new_event_db = await crud.create_event(
                        session,
                        event_id=event_id,
                        title=event_api["title"],
                        start=datetime.fromisoformat(event_api["start"]).timestamp(),
                        finish=datetime.fromisoformat(event_api["finish"]).timestamp(),
                    )
                    
                    # send notification
                    embed = await create_event_embed(event_api, "New CTF event detected!")
                    view = discord.ui.View(timeout=None)
                    view.add_item(
                        discord.ui.Button(
                            label='Join',
                            style=discord.ButtonStyle.blurple,
                            custom_id=f"ctf_join_channel:event:{new_event_db.id}",
                            emoji=settings.EMOJI,
                        )
                    )
                    await anno_channel.send(embed=embed, view=view)
                except Exception as e:
                    logger.error(f"failed to create an event on database and send notification to announcement channel: {str(e)}")


async def update_event(guild:discord.Guild, anno_channel:discord.TextChannel, event_api:Dict[str, Any], event_db:Event):
    """
    Update an event on database, send notifications and edit it's scheduled event.
    """
    ntitle = event_api["title"]
    nstart = datetime.fromisoformat(event_api["start"])
    nfinish = datetime.fromisoformat(event_api["finish"])
    
    logger.info(f"Detected: {ntitle} (old: {event_db.title}) (id={event_db.id}, event_id={event_db.event_id}) was updated")
    
    async with get_db() as session:
        # update database
        try:
            event_db = await crud.update_event(
                session,
                id=event_db.id,
                title=ntitle,
                start=int(nstart.timestamp()),
                finish=int(nfinish.timestamp())
            )
        except Exception as e:
            logger.error(f"failed to update event (id={event_db.id}) on database: {str(e)}")
            return
        
        # 這裡之後的錯誤可以不用直接 return，因為不重要
        # scheduled event
        if not(event_db.channel_id is None):
            if not((sc_id := event_db.scheduled_event_id) is None) and \
                not((sc := guild.get_scheduled_event(sc_id)) is None):
                # exists -> edit
                try:
                    sc = await sc.edit(
                        reason="update detected",
                        location=f"https://ctftime.org/event/{event_db.event_id}",
                        name=ntitle,
                        start_time=nstart,
                        end_time=nfinish,
                    )
                    if sc is None:
                        raise Exception("sc.edit() returned None")
                except Exception as e:
                    logger.error(f"failed to edit scheduled event (id={sc_id}) on Discord: {str(e)}")
                    # ignore exception
            else:
                # not exists -> create
                sc:Optional[discord.ScheduledEvent] = None
                try:
                    # create scheduled event
                    sc:discord.ScheduledEvent = await guild.create_scheduled_event(
                        location=f"https://ctftime.org/event/{event_db.event_id}",
                        name=ntitle,
                        start_time=nstart,
                        end_time=nfinish,
                    )
                    if sc is None:
                        raise Exception("guild.create_scheduled_event() returned None")
                    
                    # update database
                    await crud.update_event(
                        session,
                        id=event_db.id,
                        scheduled_event_id=sc.id
                    )
                except Exception as e:
                    # log
                    logger.error(f"failed to create scheduled event of event (id={event_db.id}, event_id={event_db.event_id}): {str(e)}")
                    
                    # rollback
                    if not(sc is None):
                        await sc.delete()
                    
                    # ignore exception

        # send notification to announcement channel
        embed = await create_event_embed(event_api, "Update detected!")
        try:
            await anno_channel.send(embed=embed)
        except Exception as e:
            logger.error(f"failed to send notification to announcement channel: {str(e)}")
            # ignore exception
                        
        # send notification to private channel
        if not((channel_id := event_db.channel_id) is None) and \
            not((c := guild.get_channel(channel_id)) is None):
            try:
                await c.send(embed=embed)
            except Exception as e:
                logger.error(f"failed to send notification to channel (id={event_db.channel_id}): {str(e)}")
                # ignore exception


async def remove_event(guild:discord.Guild, anno_channel:discord.TextChannel, event_db:Event):
    """
    Delete an event on database, send notifications and remove it's scheduled event.
    """
    logger.info(f"Detected: {event_db.title} (id={event_db.id}, event_id={event_db.event_id}) was removed")
    
    # archive event
    async with get_db() as session:
        try:
            await crud.update_event(session, id=event_db.id, archived=True)
        except Exception as e:
            logger.error(f"failed to update (archive) event on database: {str(e)}")
            return
    
    # 這裡之後的錯誤可以不用直接 return，因為不重要
    # remove scheduled event
    if not((sc_id := event_db.scheduled_event_id) is None) and \
        not((sc := guild.get_scheduled_event(sc_id)) is None):
        try:
            await sc.delete()
        except Exception as e:
            logger.error(f"failed to remove scheduled event (id={sc_id}) of event (id={event_db.id}, event_id={event_db.event_id}): {str(e)}")
                    
    # send notification to announcement channel
    embed = discord.Embed(
        color=discord.Color.red(),
        title=f"{event_db.title} was removed",
        footer=discord.EmbedFooter(text=f"Event ID: {event_db.event_id}")
    )
    try:
        await anno_channel.send(embed=embed)
    except Exception as e:
        logger.error(f"failed to send notification to announcement channel: {str(e)}")
    
    # send notification to private channel
    if not((channel_id := event_db.channel_id) is None) and \
        not((c := guild.get_channel(channel_id)) is None):
        try:
            await c.send(embed=embed)
        except Exception as e:
            logger.error(f"failed to send notification to channel (id={event_db.channel_id}): {str(e)}")


async def detect_event_update_and_remove(guild:discord.Guild, anno_channel:discord.TextChannel):
    """
    Detect events which are not archived and finish after now+DATABASE_SEARCH_DAYS (for example: now+(-90))
    
    - detect updated
    - detect removed
    """
    try:
        async with get_db() as session:
            # archived=False -> do not track archived events
            known_events_db = await crud.read_event(session, type="ctftime", archived=False)
    except Exception as e:
        logger.error(f"failed to get known CTF events from database: {str(e)}, skipped...")
        return

    # check
    for event_db in known_events_db:
        try:
            events_api = await ctf_api.fetch_ctf_events(event_db.event_id)
        except Exception as e:
            logger.error(f"failed to get CTF event (id={event_db.event_id}) from CTFtime API: {str(e)}")
            continue
        
        if len(events_api) == 1:
            # check update
            event_api = events_api[0]
            ntitle = event_api["title"]
            nstart = datetime.fromisoformat(event_api["start"])
            nfinish = datetime.fromisoformat(event_api["finish"])
                
            if event_db.title != ntitle or \
                event_db.start != int(nstart.timestamp()) or \
                event_db.finish != int(nfinish.timestamp()):
                # update detected
                await update_event(
                    guild=guild,
                    anno_channel=anno_channel,
                    event_api=event_api,
                    event_db=event_db
                )
        else:
            # removed
            await remove_event(
                guild=guild,
                anno_channel=anno_channel,
                event_db=event_db
            )


async def auto_archive(guild:discord.Guild, anno_channel:discord.TextChannel, archive_category:discord.CategoryChannel):
    """
    find CTFTime events which finish before now+DATABASE_SEARCH_DAYS (for example: now+(-90)) and archive them
    """
    async with get_db() as session:
        try:
            need_archive = await crud.read_ctftime_event_need_archive(session)
        except Exception as e:
            logger.error(f"failed to get CTF events that need to be archived: {str(e)}, skipped...")
            return
    
        for event_db in need_archive:
            logger.info(f"Detected: {event_db.title} (id={event_db.id}, event_id={event_db.event_id}) need to be archived")
            
            # update database
            try:
                event_db = await crud.update_event(
                    session,
                    id=event_db.id,
                    archived=True,
                )
            except Exception as e:
                logger.error(f"failed to update (archive) CTF event (id={event_db.id}) on Database: {str(e)}")
                continue
            
            # remove scheduled event
            if not((sc_id := event_db.scheduled_event_id) is None) and \
                not((sc := guild.get_scheduled_event(sc_id)) is None):
                try:
                    await sc.delete()
                except Exception as e:
                    logger.error(f"failed to delete scheduled event (id={sc_id}) of event (id={event_db.id}, event_id={event_db.event_id}) on Discord")
                    # ignore exception
            
            # send notification to announcement channel
            embed = discord.Embed(
                color=discord.Color.red(),
                title=f"{event_db.title} was archived",
                footer=discord.EmbedFooter(text=f"Event ID: {event_db.event_id}")
            )
            try:
                await anno_channel.send(embed=embed)
            except Exception as e:
                logger.error(f"failed to send notification to announcement channel: {str(e)}")
                # ignore exception

            
            if not((channel_id := event_db.channel_id) is None) and \
                not((c := guild.get_channel(channel_id)) is None):
                # send notification to private channel
                try:
                    await c.send(embed=embed)
                except Exception as e:
                    logger.error(f"failed to send notification to channel (id={event_db.channel_id}): {str(e)}")
                    
                # move channel
                try:
                    await c.move(
                        category=archive_category,
                        beginning=True,
                        sync_permissions=True,
                        reason="archived"
                    )
                except Exception as e:
                    logger.error(f"failed to move channel (id={channel_id}) to category (id={settings.ARCHIVE_CATEGORY_ID})")
                    # ignore exception


async def recover_scheduled_events(guild:discord.Guild):
    """
    Detect events which are not archived and finish after now+DATABASE_SEARCH_DAYS (for example: now+(-90))
    
    - detect whether it's scheduled event is exists
    """
    async with get_db() as session:
        # archived=False -> do not track archived events
        try:
            known_events_db = await crud.read_event(session, type="ctftime", archived=False)
        except Exception as e:
            logger.error(f"failed to get known CTF events from database: {str(e)}, skipped...")
            return
    
        for event_db in known_events_db:
            if not(event_db.channel_id is None):
                if (sc_id := event_db.scheduled_event_id) is None or \
                    guild.get_scheduled_event(sc_id) is None:
                    # need recreate
                    logger.info(f"Detected: scheduled event of event (id={event_db.id}, event_id={event_db.event_id}) needs to be recreated")
                    
                    sc:Optional[discord.ScheduledEvent] = None
                    try:
                        # create scheduled event
                        sc:discord.ScheduledEvent = await guild.create_scheduled_event(
                            location=f"https://ctftime.org/event/{event_db.event_id}",
                            name=event_db.title,
                            start_time=datetime.fromtimestamp(event_db.start),
                            end_time=datetime.fromtimestamp(event_db.finish)
                        )
                        if sc is None:
                            raise Exception("guild.create_scheduled_event() returned None")
                        
                        # update database
                        await crud.update_event(
                            session,
                            id=event_db.id,
                            scheduled_event_id=sc.id
                        )
                    except Exception as e:
                        # logging
                        logger.error(f"failed to create scheduled event for event (id={event_db.id}, event_id={event_db.event_id}): {str(e)}")
                        
                        # rollback
                        if not(sc is None):
                            await sc.delete()


# cog
class CTFBGTask(commands.Cog):
    def __init__(self, bot:commands.Bot):
        self.bot:commands.Bot = bot
        
    
    @commands.Cog.listener()
    async def on_ready(self):
        # start background task
        self.task_checks.start()
    
    
    # background task
    @tasks.loop(minutes=settings.CHECK_INTERVAL_MINUTES)
    async def task_checks(self):
        # get guild
        guild:discord.Guild = self.bot.get_guild(settings.GUILD_ID)
        if guild is None:
            logger.error(f"invalid guild_id={settings.GUILD_ID}")
            return
        
        # get channel
        channel:discord.TextChannel = guild.get_channel(settings.ANNOUNCEMENT_CHANNEL_ID)
        if channel is None:
            logger.error(f"Can not get channnel id={settings.ANNOUNCEMENT_CHANNEL_ID} from guild {guild.name} (id={guild.id})")
            return
        
        # get archive category
        archive_category:discord.CategoryChannel = discord.utils.get(guild.categories, id=settings.ARCHIVE_CATEGORY_ID)
        if archive_category is None:
            logger.error(f"Can not get category id={settings.ARCHIVE_CATEGORY_ID} from guild {guild.name} (id={guild.id})")
            return
        
        # process
        await detect_event_new(channel)
        
        await detect_event_update_and_remove(guild, channel)
        
        await auto_archive(guild, channel, archive_category)
        
        await recover_scheduled_events(guild)
    
    
    @task_checks.before_loop
    async def before_task_checks(self):
        await self.bot.wait_until_ready()


    def cog_unload(self):
        self.task_checks.cancel()
    
    
    # interaction handler
    @commands.Cog.listener()
    async def on_interaction(self, interaction:discord.Interaction):
        if interaction.type != discord.InteractionType.component:
            return
        
        custom_id = interaction.data.get("custom_id")
        if custom_id is None:
            return
        
        if custom_id.startswith("ctf_join_channel:event:"):
            # check user
            try:
                db_user, member = await security.auto_register_and_check_user(
                    discord_id=interaction.user.id,
                    force_pm=False,
                    auto_register=True
                )
            except Exception as e:
                await interaction.response.send_message("Permission Denied", ephemeral=True)
            
            # get event db id
            try:
                _ = custom_id.split(":")
                event_db_id:int = int(_[2])
            except:
                await interaction.response.send_message("Invalid arguments", ephemeral=True)
                return
            
            # join channel
            await interaction.response.defer(ephemeral=True)
            try:
                await join_channel.create_and_join_channel(self.bot, member, event_db_id)
            except Exception as e:
                await interaction.followup.send(str(e), ephemeral=True)
                return
            
            await interaction.followup.send("Done.", ephemeral=True)


def setup(bot:commands.Bot):
    bot.add_cog(CTFBGTask(bot))