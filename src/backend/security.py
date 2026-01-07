from typing import Optional, Tuple
import logging

from discord.ext import commands
from fastapi import Request, HTTPException
import discord

from src.bot import get_bot
from src.config import settings
from src.database.database import get_db
from src.database.model import User
from src import crud

# logging
logger = logging.getLogger("uvicorn")

# functions
async def discord_check_user(
    discord_id:int,
    force_pm:bool
) -> Optional[discord.Member]:
    """
    check a user
    - in the guild
    - hahs member role or pm role
    """
    bot:commands.Bot = await get_bot()
    try:
        # get guild
        guild = bot.get_guild(settings.GUILD_ID)
        if guild is None:
            logger.error(f"invalid guild id={settings.GUILD_ID}")
            return None
        
        # get member
        member = guild.get_member(discord_id)
        if member is None:
            return None
        
        # check role
        member_role = member.get_role(settings.MEMBER_ROLE_ID)
        pm_role = member.get_role(settings.PM_ROLE_ID)
        if force_pm and pm_role is None:
            return None
        if not force_pm and member_role is None and pm_role is None:
            return None
        
        return member
    except Exception as e:
        logger.error(f"error in discord_check_user(): {str(e)}")
        return None


async def check_user(
    discord_id:int,
    force_pm:bool=False,
) -> Tuple[Optional[User], Optional[discord.Member]]:
    """
    check a user
    - in database
    - discord_check_user(discord_id)
    
    returns:
    - db_user, member
    - None, None
    """
    try:
        # check database
        async with get_db() as db:
            users, err = await crud.read_user(db, discord_id)
        if not(err is None) or len(users) != 1:
            # error or not found
            return None, None
        
        # discord check user
        member = await discord_check_user(discord_id, force_pm)
        if member is None:
            return None, None
        return users[0], member
    except Exception as e:
        logger.error(f"error in check_user(): {str(e)}")
        return None, None


# for fastapi
async def fastapi_check_user(request:Request):
    try:
        discord_id = int(request.session["discord_id"])
    except:
        raise HTTPException(401)
    
    u = await check_user(discord_id, False)
    db_user, member = u
    if db_user is None or member is None:
        raise HTTPException(403)
    
    return db_user, member


async def fastapi_check_pm_user(request:Request):
    try:
        discord_id = int(request.session["discord_id"])
    except:
        raise HTTPException(401)
    
    u = await check_user(discord_id, True)
    db_user, member = u
    if db_user is None or member is None:
        raise HTTPException(403)
    
    return db_user, member