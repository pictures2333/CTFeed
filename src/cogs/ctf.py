from datetime import datetime, timedelta
import logging

from discord.ext import commands
import discord

from src.config import settings

# logging
logger = logging.getLogger("uvicorn")

# cog
class CTF(commands.Cog):
    def __init__(self, bot:commands.Bot):
        self.bot:commands.Bot = bot


def setup(bot:commands.Bot):
    bot.add_cog(CTF(bot))
