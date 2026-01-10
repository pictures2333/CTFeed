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
) -> discord.Member:
    """
    check a user
    - in the guild
    - hahs member role or pm role
    
    Raises:
        HTTPException
    """
    bot:commands.Bot = await get_bot()
    
    # get guild
    guild = bot.get_guild(settings.GUILD_ID)
    if guild is None:
        errmsg = f"invalid guild id={settings.GUILD_ID}"
        logger.error(errmsg)
        raise HTTPException(status_code=500, detail=errmsg)
        
    # get member
    member = guild.get_member(discord_id)
    if member is None:
        raise HTTPException(status_code=403)
        
    # check role
    member_role = member.get_role(settings.MEMBER_ROLE_ID)
    pm_role = member.get_role(settings.PM_ROLE_ID)
    if force_pm and pm_role is None:
        raise HTTPException(403)
    if not force_pm and member_role is None and pm_role is None:
        raise HTTPException(403)
        
    return member


# functions
async def auto_register_and_check_user(
    discord_id:int,
    force_pm:bool=False,
    auto_register:bool=True
) -> Tuple[User, discord.Member]:
    """
    for both Discord and fastapi (/auth/login)
    
    check a user
    - discord_check_user(discord_id)
    - check in database
    - if not in database -> register
    - if in database -> login
    
    Raises:
        HTTPException
    """
    # check discord
    member = await discord_check_user(discord_id=discord_id, force_pm=force_pm)
    
    async with get_db() as session:
        # check db
        try:
            db_users = await crud.read_user(session, discord_id=discord_id)
        except Exception as e:
            logger.error(f"failed to get user (discord_id={discord_id}) from database: {str(e)}")
            raise HTTPException(status_code=500, detail=f"failed to get user (discord_id={discord_id}) from database")
    
        if len(db_users) == 0:
            # not exists -> register
            if auto_register:
                try:
                    db_user = await crud.create_user(session, discord_id=discord_id)
                except Exception as e:
                    logger.error(f"failed to create user (discord_id={discord_id}) on database: {str(e)}")
                    raise HTTPException(status_code=500, detail=f"failed to create user (discord_id={discord_id}) on database")
            else:
                raise HTTPException(status_code=403)
        else:
            # exists -> login
            db_user = db_users[0]
        
        return db_user, member


# for fastapi
async def fastapi_check_user(request:Request) -> Tuple[User, discord.Member]:
    try:
        discord_id = int(request.session["discord_id"])
    except:
        raise HTTPException(401)
    
    return await auto_register_and_check_user(discord_id, False, False)


async def fastapi_check_pm_user(request:Request) -> Tuple[User, discord.Member]:
    try:
        discord_id = int(request.session["discord_id"])
    except:
        raise HTTPException(401)
    
    return await auto_register_and_check_user(discord_id, True, False)

