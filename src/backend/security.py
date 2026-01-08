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

# utils
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


# functions
async def auto_register_and_check_user(
    discord_id:int,
    force_pm:bool=False,
    auto_register:bool=True
) -> Optional[Tuple[User, discord.Member]]:
    """
    for both Discord and fastapi (/auth/login)
    
    check a user
    - discord_check_user(discord_id)
    - check in database
    - if not in database -> register
    - if in database -> login
    """
    # check discord
    member = await discord_check_user(discord_id=discord_id, force_pm=force_pm)
    if member is None:
        return None
    
    async with get_db() as session:
        # check db
        db_users, err = await crud.read_user(session, discord_id=discord_id)
        if not(err is None): # error
            return None
    
        if len(db_users) == 0:
            # not exists -> register
            if auto_register:
                db_user = await crud.create_user(session, discord_id=discord_id)
                if db_user is None:
                    return None
            else:
                return None
        else:
            # exists -> login
            db_user = db_users[0]
        
        return (db_user, member)


# for fastapi
async def fastapi_check_user(request:Request) -> Tuple[User, discord.Member]:
    try:
        discord_id = int(request.session["discord_id"])
    except:
        raise HTTPException(401)
    
    u = await auto_register_and_check_user(discord_id, False, False)
    if u is None:
        raise HTTPException(403)
    
    return u


async def fastapi_check_pm_user(request:Request) -> Tuple[User, discord.Member]:
    try:
        discord_id = int(request.session["discord_id"])
    except:
        raise HTTPException(401)
    
    u = await auto_register_and_check_user(discord_id, True, False)
    if u is None:
        raise HTTPException(403)
    
    return u

