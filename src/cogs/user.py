from typing import Optional, List, Tuple, Literal
from datetime import datetime, timedelta
import logging

from discord.ext import commands
import discord

from src.config import settings
from src.database.database import get_db
from src.database.model import Event, User, Skills, RhythmGames, Status
from src import crud
from src.backend import security

# logging
logger = logging.getLogger("uvicorn")

# view
class UserMenuView(discord.ui.View):
    def __init__(self, bot:commands.Bot, discord_id:int, db_user:User):
        super().__init__(timeout=None)
        self.bot = bot
        self.discord_id = discord_id
        
        self.update_button_and_select_menu(db_user)
    
    
    def build_embed(self, db_user:User, member:discord.Member) -> discord.Embed:
        color = discord.Color.green() if db_user.status == Status.online else discord.Color.red()
        embed = discord.Embed(title=f"{member.display_name} (discord_id={member.id})", color=color)
        embed.add_field(name="Status", value=db_user.status.value, inline=False)
        skills = "" if len(db_user.skills) != 0 else "(null)"
        for s in db_user.skills:
            skills += f"{s.value}\n"
        embed.add_field(name="Skills", value=f"```\n{skills}\n```", inline=False)
        rhythm_games = "" if len(db_user.rhythm_games) != 0 else "(null)"
        for r in db_user.rhythm_games:
            rhythm_games += f"{r.value}\n"
        embed.add_field(name="Rhythm Games", value=f"```\n{rhythm_games}\n```", inline=False)
        
        return embed
    
    
    def update_button_and_select_menu(self, db_user:User):
        self.skills.options = [
            discord.SelectOption(
                label=i.value,
                value=i.value,
                default=(i in db_user.skills),
            ) for i in Skills
        ]
        
        self.rhythm_games.options = [
            discord.SelectOption(
                label=i.value,
                value=i.value,
                default=(i in db_user.rhythm_games),
            ) for i in RhythmGames
        ]
        
        self.change_status.style = discord.ButtonStyle.green if db_user.status == Status.online else discord.ButtonStyle.danger

    
    @discord.ui.button(label="Change Status", row=1)
    async def change_status(self, button:discord.Button, interaction:discord.Interaction):
        # check user
        u = await security.check_permission(interaction, False)
        if u is None:
            return
        db_user, member = u
        
        # database
        status = Status.online if db_user.status == Status.offline else Status.offline
        async with get_db() as session:
            try:
                db_user = await crud.update_user(session, member.id, status=status)
            except Exception as e:
                logger.error(f"failed to update user on database: {str(e)}")
                await interaction.response.send_message(f"failed to update user on database", ephemeral=True)
                return
        
        self.update_button_and_select_menu(db_user)
        await interaction.response.edit_message(embed=self.build_embed(db_user, member), view=self)

    
    @discord.ui.select(placeholder="Change skills", min_values=0, max_values=len(Skills), row=2,
                       options=[discord.SelectOption(label=i.value, value=i.value, default=True) for i in Skills])
    async def skills(self, select:discord.ui.Select, interaction:discord.Interaction):
        # check user
        u = await security.check_permission(interaction, False)
        if u is None:
            return
        db_user, member = u
        
        # check arguments
        try:
            skills = [Skills(i) for i in select.values]
        except:
            await interaction.response.send_message("Invalid argument", ephemeral=True)
            return
        
        # database
        async with get_db() as session:
            try:
                db_user = await crud.update_user(session, member.id, skills=skills)
            except Exception as e:
                logger.error(f"failed to update user on database: {str(e)}")
                await interaction.response.send_message(f"failed to update user on database", ephemeral=True)
                return
        
        self.update_button_and_select_menu(db_user)
        await interaction.response.edit_message(embed=self.build_embed(db_user, member), view=self)

    
    @discord.ui.select(placeholder="Change rhythm games", min_values=0, max_values=len(RhythmGames), row=3,
                       options=[discord.SelectOption(label=i.value, value=i.value, default=True) for i in RhythmGames])
    async def rhythm_games(self, select:discord.ui.Select, interaction:discord.Interaction):
        # check user
        u = await security.check_permission(interaction, False)
        if u is None:
            return
        db_user, member = u
        
        # check arguments
        try:
            rhythm_games = [RhythmGames(i) for i in select.values]
        except:
            await interaction.response.send_message("Invalid argument", ephemeral=True)
            return
        
        # database
        async with get_db() as session:
            try:
                db_user = await crud.update_user(session, member.id, rhythm_games=rhythm_games)
            except Exception as e:
                logger.error(f"failed to update user on database: {str(e)}")
                await interaction.response.send_message(f"failed to update user on database", ephemeral=True)
                return
        
        self.update_button_and_select_menu(db_user)
        await interaction.response.edit_message(embed=self.build_embed(db_user, member), view=self)


# cog
class UserMenu(commands.Cog):
    def __init__(self, bot:commands.Bot):
        self.bot:commands.Bot = bot
        
    
    @discord.slash_command(name="user_menu", description="show your information")
    async def user_menu(self, ctx:discord.ApplicationContext):
        # check user
        u = await security.check_permission(ctx, False)
        if u is None:
            return
        db_user, member = u
        
        view = UserMenuView(self.bot, member.id, db_user)
        await ctx.response.send_message(embed=view.build_embed(db_user, member), view=view, ephemeral=True)
        return


def setup(bot:commands.Bot):
    bot.add_cog(UserMenu(bot))
