import logging
from typing import Optional

from discord.ext import commands
import discord

from src.database import model
from src.backend import security
from src.backend import config

# logging
logger = logging.getLogger("uvicorn")

# view
class ConfigMenu(discord.ui.View):
    def __init__(self, bot:commands.Bot):
        super().__init__(timeout=None)
        
        self.bot = bot
        self.selected_key: Optional[str] = None
        
    
    async def build_embed_and_view(self) -> discord.Embed:
        self.clear_items()
        
        # build embed
        try:
            config_info = await config.read_config(self.selected_key)
        except Exception as e:
            return discord.Embed(title=f"Fail to read config", description=str(e), color=discord.Color.red())
        
        if self.selected_key is None:
            embed = self._build_overview_embed(config_info)
        else:
            embed = self._build_detail_embed(config_info)
            
        embed.set_footer(text=f"Guild info: {config_info.guild_name} (id={config_info.guild_id})")
        
        # build view
        await self._build_view()
        
        return embed


    def _build_overview_embed(self, config_info) -> discord.Embed:
        color = discord.Color.green()
        invalid_count = 0
        for c in config_info.config:
            if not c.ok:
                color = discord.Color.red()
                invalid_count += 1

        embed = discord.Embed(
            title="Server Configuration",
            description=(
                "All settings are valid."
                if invalid_count == 0
                else f"{invalid_count} setting(s) need attention."
            ),
            color=color
        )
        for c in config_info.config:
            status = "OK" if c.ok else "INVALID"
            embed.add_field(
                name=f"[{status}] {c.key}",
                value=c.message,
                inline=False
            )
        return embed


    def _build_detail_embed(self, config_info) -> discord.Embed:
        c = config_info.config[0]
        status = "OK" if c.ok else "INVALID"
        embed = discord.Embed(
            title=f"Edit {c.key}",
            description=c.description,
            color=discord.Color.green() if c.ok else discord.Color.red()
        )
        embed.add_field(name="Status", value=status, inline=True)
        embed.add_field(name="Key", value=f"`{c.key}`", inline=True)
        embed.add_field(name="Current value", value=c.message, inline=False)
        return embed


    def _build_edit_select_kwargs(self, config_info:model.ConfigInfo) -> dict:
        kwargs = {
            "placeholder": f"Choose {self.selected_key}...",
            "min_values": 1,
            "max_values": 1,
            "row": 1,
            "select_type": config_info.select_type
        }
        if config_info.config_type == model.ConfigType.CHANNEL:
            kwargs["channel_types"] = [discord.ChannelType.text]
        elif config_info.config_type == model.ConfigType.CATEGORY:
            kwargs["channel_types"] = [discord.ChannelType.category]
        return kwargs


    async def _build_view(self):
        if self.selected_key is None:
            self.setting_select = discord.ui.Select(
                placeholder="Select a setting...",
                min_values=1,
                max_values=1,
                row=0,
                options=[
                    discord.SelectOption(
                        label=k,
                        value=k,
                        description=model.config_info[k].description[:100],
                        default=(k == self.selected_key)
                    )
                    for k in model.config_info
                ]
            )
            self.setting_select.callback = self.on_select_setting
            self.add_item(self.setting_select)
        else:
            selected_config_info = model.config_info[self.selected_key]
            self.edit = discord.ui.Select(**self._build_edit_select_kwargs(selected_config_info))
            self.edit.callback = self.on_edit
            self.add_item(self.edit)

            self.back = discord.ui.Button(
                label="Back",
                style=discord.ButtonStyle.grey,
                row=2
            )
            self.back.callback = self.on_back
            self.add_item(self.back)

        self.refresh = discord.ui.Button(
            label="Refresh",
            style=discord.ButtonStyle.grey,
            row=2
        )
        self.refresh.callback = self.on_refresh
        self.add_item(self.refresh)
        
        return


    async def on_select_setting(self, interaction:discord.Interaction):
        # check permission
        if not (await security.discord_check_administrator(interaction)):
            return
        
        # check argument
        try:
            key = str(self.setting_select.values[0])
        except Exception:
            await interaction.response.send_message("Invalid arguments", ephemeral=True)
            return

        if key not in model.config_info:
            await interaction.response.send_message("Invalid arguments", ephemeral=True)
            return
        
        # return
        self.selected_key = key
        embed = await self.build_embed_and_view()
        await interaction.response.edit_message(embed=embed, view=self)
        return


    async def on_back(self, interaction:discord.Interaction):
        # check permission
        if not (await security.discord_check_administrator(interaction)):
            return

        self.selected_key = None
        embed = await self.build_embed_and_view()
        await interaction.response.edit_message(embed=embed, view=self)
        return


    async def on_refresh(self, interaction:discord.Interaction):
        # check permission
        if not (await security.discord_check_administrator(interaction)):
            return

        embed = await self.build_embed_and_view()
        await interaction.response.edit_message(embed=embed, view=self)
        return


    async def on_edit(self, interaction:discord.Interaction):
        # check permission
        if not (await security.discord_check_administrator(interaction)):
            return

        selected_key = self.selected_key
        if selected_key is None:
            await interaction.response.send_message("Select a setting first", ephemeral=True)
            return

        # check argument
        try:
            value = self.edit.values[0].id
        except Exception:
            await interaction.response.send_message("Invalid arguments", ephemeral=True)
            return
        
        # update
        try:
            await config.update_config((selected_key, value))
        except Exception as e:
            await interaction.response.send_message(f"fail to update config (key={selected_key}): {str(e)}", ephemeral=True)
            return
        
        # logging
        logger.info(f"User {interaction.user.name} (id={interaction.user.id}) updated Config (key={selected_key}) to value={value}")
        
        # return
        self.selected_key = selected_key
        embed = await self.build_embed_and_view()
        await interaction.response.edit_message(embed=embed, view=self)
        return


class Config(commands.Cog):
    def __init__(self, bot:commands.Bot):
        self.bot:commands.Bot = bot
    
    
    @discord.slash_command(name="config", description="Config Panel")
    async def config_menu(self, ctx:discord.ApplicationContext):
        # check permission
        if not (await security.discord_check_administrator(ctx)):
            return
        
        view = ConfigMenu(self.bot)
        embed = await view.build_embed_and_view()
        await ctx.response.send_message(embed=embed, view=view, ephemeral=True)
        return
        

def setup(bot:commands.Bot):
    bot.add_cog(Config(bot))
