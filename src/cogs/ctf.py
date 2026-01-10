from typing import Optional, List, Tuple, Literal
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
async def in_event_channel(ctx:discord.ApplicationContext) -> Optional[Event]:
    """
    Check whether the command is used in an event channel
    """
    guild:discord.Guild = ctx.guild
    
    async with get_db() as session:
        try:
            events_db = await crud.read_event(session, type=None, archived=True, channel_id=ctx.channel_id)
        except Exception as e:
            logger.error(f"failed to get event (channel_id={ctx.channel_id}) from database: {str(e)}")
            return None
        
    if len(events_db) == 0:
        return None
        
    return events_db[0]


# views
class CTFmenu(discord.ui.View):
    def __init__(self, bot:commands.Bot, type:Literal["ctftime", "custom"], events:List[Event]):
        super().__init__(timeout=None)
        self.bot = bot
        self.type = type
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
            if self.type == "ctftime":
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
            elif self.type == "custom":
                description += f"**[Database ID: {event.id}] {event.title}**\n"
                description += "\n"
        
        if self.type == "ctftime":
            type = "CTFTime"
        elif self.type == "custom":
            type = "Custom"

        embed = discord.Embed(
            title=f"{settings.EMOJI} {type} events ({start} / {len(self.events)})",
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
                    description=f"Database ID: {event.id}" + \
                        (f" | CTFTime event ID: {event.event_id}" if self.type == "ctftime" else ""),
                    value=f"{event.id}"
                )
                for event in _events
            ]
        else:
            self.select_menu.disabled = True
    
    
    @discord.ui.button(label="⬅️", style=discord.ButtonStyle.blurple, row=2)
    async def prev_button(self, button:discord.ui.Button, interaction:discord.Interaction): # endpoint
        # check user
        u = await security.check_permission(interaction, False)
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
        u = await security.check_permission(interaction, False)
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
        u = await security.check_permission(interaction, False)
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
        try:
            await join_channel.create_and_join_channel(self.bot, member, event_db_id)
        except Exception as e:
            await interaction.followup.send(str(e), ephemeral=True)
            return
        
        await interaction.followup.send("Done", ephemeral=True)
        return


# CTFTime event
class CTFTimeEventMenu(CTFmenu):
    def __init__(self, bot:commands.Bot, events:List[Event]):
        super().__init__(bot, "ctftime", events)
    
    
    @discord.ui.button(label="Custom events", style=discord.ButtonStyle.gray, row=2)
    async def custom_events(self, button:discord.Button, interaction:discord.Interaction):
        async with get_db() as session:
            try:
                events = await crud.read_event(session, type="custom", archived=False)
            except Exception as e:
                logger.error(f"failed to get events from database: {str(e)}")
                await interaction.response.send_message("failed to get events from database", ephemeral=True)
                return

        view = CustomEventMenu(self.bot, events)

        await interaction.response.send_message(embed=view.build_embed(), view=view, ephemeral=True)


# custom event
class CreateCustomEventModal(discord.ui.Modal):
    def __init__(self, bot:commands.Bot, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        
        self.bot = bot
        
        self.add_item(discord.ui.InputText(label="Event title", style=discord.InputTextStyle.short))


    async def callback(self, interaction: discord.Interaction):
        await interaction.response.defer()
        title = self.children[0].value
        
        try:
            await join_channel.create_custom_event(self.bot, title)
        except Exception as e:
            await interaction.followup.send(content=str(e), ephemeral=True)
        
        await interaction.followup.send(content="Done", ephemeral=True)


class CustomEventMenu(CTFmenu):
    def __init__(self, bot:commands.Bot, events:List[Event]):
        super().__init__(bot, "custom", events)
        
    
    @discord.ui.button(label="Create custom event", style=discord.ButtonStyle.gray, row=2)
    async def create_custom_event(self, button:discord.Button, interaction:discord.Interaction):
        await interaction.response.send_modal(CreateCustomEventModal(bot=self.bot, title="Create custom event"))


# functions
async def ctf_event_menu(
    bot:commands.Bot,
    ctx:discord.ApplicationContext,
    db_user:Event,
    member:discord.Member
):
    async with get_db() as session:
        try:
            events = await crud.read_event(session, type="ctftime", archived=False)
        except Exception as e:
            logger.error(f"failed to get events from database: {str(e)}")
            await ctx.response.send_message("failed to get events from database", ephemeral=True)
            return
    
    view = CTFTimeEventMenu(bot, events)
    
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
        u = await security.check_permission(ctx, False)
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
