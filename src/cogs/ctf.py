from typing import Optional, List, Tuple
from datetime import datetime, timedelta
import logging

from discord.ext import commands
import discord

from src.config import settings
from src.database.database import get_db
from src.database.model import Event, User
from src import crud
from src.backend import security, join_channel

# logging
logger = logging.getLogger("uvicorn")

# utils
async def check_permission(ctx:discord.ApplicationContext, force_pm:bool=False) -> Optional[Tuple[User, discord.Member]]:
    u = await security.auto_register_and_check_user(
        discord_id=ctx.user.id,
        force_pm=force_pm,
        auto_register=True
    )
    if u is None:
        await ctx.response.send_message("Permission Denied", ephemeral=True)
        return None
    return u


async def in_event_channel(ctx:discord.ApplicationContext) -> Optional[Event]:
    """
    Check whether the command is used in an event channel
    """
    guild:discord.Guild = ctx.guild
    
    async with get_db() as session:
        event_db, err = await crud.read_ctftime_event(session, include_archived=True, channel_id=ctx.channel_id)
        if not(err is None):
            return None
        
        if len(event_db) == 0:
            # maybe custom event
            event_db, err = await crud.read_custom_event(session, include_archived=True, channel_id=ctx.channel_id)
            if not (err is None):
                return None
            if len(event_db) == 0:
                return None
            event_db = event_db[0]
        else:
            # ctftime event
            event_db = event_db[0]
        
    return event_db

# views
class CTFmenu(discord.ui.View):
    def __init__(self, bot:commands.Bot, events:List[Event]):
        super().__init__(timeout=None)
        self.bot = bot
        self.events = events
        
        # page control
        self.page = 0
        self.per_page = 7
        
        self.update_button_and_select_menu()
    
    
    def build_embed(self):
        start = self.page * self.per_page
        end = start + self.per_page
        
        time_now = datetime.now().timestamp()
        description = ""
        for event in self.events[start:end]:
            mark = ""
            if not(event.channel_id is None):
                mark += "[⭐️ channel created]"
            if event.start <= time_now and event.finish >= time_now:
                mark += "[🏃 now running]"

            description += f"**[Database ID: {event.id}] [{event.title}](https://ctftime.org/event/{event.event_id})**\n"
            if len(mark) > 0:
                description += mark + "\n"
            description += f"Start: <t:{event.start}:F> (<t:{event.start}:R>)\n"
            description += f"End: <t:{event.finish}:F> (<t:{event.finish}:R>)\n"
            description += "\n"
        
        embed = discord.Embed(
            title=f"{settings.EMOJI} CTF events tracked ({start} / {len(self.events)})",
            description=description,
            color=discord.Color.green()
        )
        
        return embed
    
    
    def update_button_and_select_menu(self):
        start = self.page * self.per_page
        end = start + self.per_page
        
        # prev button
        if self.page == 0:
            self.prev_button.disabled = True
        else:
            self.prev_button.disabled = False
        
        # next button
        if end >= len(self.events):
            self.next_button.disabled = True
        else:
            self.next_button.disabled = False
            
        # select menu
        _events = self.events[start:end]
        if len(_events) > 0:
            self.select_menu.options = [
                discord.SelectOption(
                    label=f"{event.title}",
                    description=f"Database ID: {event.id} | CTFTime event ID: {event.event_id}",
                    value=f"{event.id}"
                )
                for event in _events
            ]
        else:
            self.select_menu.disabled = True
    
    
    @discord.ui.button(label="⬅️", style=discord.ButtonStyle.blurple, row=2,)
    async def prev_button(self, button:discord.ui.Button, interaction:discord.Interaction): # endpoint
        # check user
        u = await check_permission(interaction, False)
        if u is None:
            return
        
        # operate
        if self.page > 0:
            self.page -= 1
        self.update_button_and_select_menu()
        
        await interaction.response.edit_message(
            embed=self.build_embed(),
            view=self,
        )
        
    
    @discord.ui.button(label="➡️", style=discord.ButtonStyle.blurple, row=2)
    async def next_button(self, button:discord.ui.Button, interaction:discord.Interaction): # endpoint
        # check user
        u = await check_permission(interaction, False)
        if u is None:
            return
        
        # operate
        if self.page * self.per_page + self.per_page < len(self.events):
            self.page += 1
        self.update_button_and_select_menu()
        
        await interaction.response.edit_message(
            embed=self.build_embed(),
            view=self
        )
        
    
    @discord.ui.select(placeholder="Join an event!", min_values=1, max_values=1, row=1, options=[discord.SelectOption(label="dummy")])
    async def select_menu(self, select:discord.ui.Select, interaction:discord.Interaction): # endpoint
        # check user
        u = await check_permission(interaction, False)
        if u is None:
            return
        db_user, member = u
        
        # check argument
        if len(select.values) != 1:
            return
        try:
            event_db_id = int(select.values[0])
        except:
            await interaction.response.send_message("Invalid argument", ephemeral=True)
            return
        
        # join channel
        await interaction.response.defer(ephemeral=True)
        err, code = await join_channel.join_channel(self.bot, member, event_db_id)
        if not(err is None):
            await interaction.followup.send(str(err), ephemeral=True)
            return
        
        await interaction.followup.send("Done", ephemeral=True)
        return


# functions
async def ctf_event_menu(
    bot:commands.Bot,
    ctx:discord.ApplicationContext,
    db_user:Event,
    member:discord.Member
):
    async with get_db() as session:
        events, err = await crud.read_ctftime_event(session, include_archived=False)
    if not(err is None):
        await ctx.response.send_message("failed to get events from database", ephemeral=True)
        return
    
    view = CTFmenu(bot, events)
    
    await ctx.response.send_message(embed=view.build_embed(), view=view, ephemeral=True)


# cog
class CTF(commands.Cog):
    def __init__(self, bot:commands.Bot):
        self.bot:commands.Bot = bot
        
    
    @discord.slash_command(name="ctf_menu", description="panel")
    async def ctf_menu(self, ctx:discord.ApplicationContext): # endpoint
        """
        multi function
        """
        # check user
        u = await check_permission(ctx, False)
        if u is None:
            return
        db_user, member = u
        
        # routing
        if not(await in_event_channel(ctx) is None):
            # todo
            await ctx.response.send_message("Not done", ephemeral=True)
        else:
            await ctf_event_menu(self.bot, ctx, db_user, member)


def setup(bot:commands.Bot):
    bot.add_cog(CTF(bot))
