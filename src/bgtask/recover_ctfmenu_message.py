import logging

import discord

from src.bot import get_guild
from src.database import database
from src.database import model
from src.backend import config
from src import crud
from src.backend import ctfmenu_message

# logging
logger = logging.getLogger("uvicorn")

# functions
async def _recover_ctfmenu_message():
    """
    Check ctfmenu message and try to recover it when it disappeared.
    """
    try:
        await ctfmenu_message.operate_message(
            guild=get_guild(),
            mode="recover"
        )
    except Exception as exc:
        logger.error(f"failed to recover ctfmenu message: {str(exc)}")
    
    return
