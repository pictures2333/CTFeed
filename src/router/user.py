from typing import List
import logging

from discord.ext import commands
from sqlalchemy.ext.asyncio import AsyncSession
from fastapi import APIRouter, Depends, HTTPException

from src.bot import get_bot
from src.database.database import fastapi_get_db
from src.backend.security import fastapi_check_user
from src.backend import get_user
from src import schema
from src import crud

# logger
logger = logging.getLogger("uvicorn")

# router
router = APIRouter(prefix="/user")

@router.get("/")
async def read_all_users(
    u=Depends(fastapi_check_user),
    db:AsyncSession=Depends(fastapi_get_db),
    bot:commands.Bot=Depends(get_bot)
) -> List[schema.User]:
    try:
        db_users = await crud.read_user(db)
        
        r = []
        for u in db_users:
            try:
                _ = await get_user.get_user(u.discord_id)
            except:
                pass
            r.append(_)
        
        return r
    except Exception as e:
        if isinstance(e, HTTPException):
            raise
        logger.error(f"failed to get users: {str(e)}")
        raise HTTPException(status_code=500, detail=f"failed to get users")


@router.get("/{discord_id}")
async def read_user(
    discord_id:int,
    u=Depends(fastapi_check_user),
    db:AsyncSession=Depends(fastapi_get_db),
    bot:commands.Bot=Depends(get_bot),
) -> schema.User:
    try:
        db_users = await crud.read_user(db, discord_id=discord_id)
        if len(db_users) == 0:
            raise HTTPException(status_code=404)
        
        return (await get_user.get_user(db_users[0].discord_id))
    except Exception as e:
        if isinstance(e, HTTPException):
            raise
        logger.error(f"failed to get user (discord_id={discord_id}) from database: {str(e)}")
        raise HTTPException(status_code=500, detail=f"failed to get user (discord_id={discord_id}) from database")
