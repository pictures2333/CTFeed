from typing import List, Optional, Tuple
import logging

from sqlalchemy.ext.asyncio import AsyncSession
import sqlalchemy

from src.database.model import User

# logger
logger = logging.getLogger("uvicorn")

# create
async def create_user(
    db:AsyncSession,
    discord_id:int
) -> Optional[User]:
    """
    user:Optional[User] = await create_user(db, discord_id)
    """
    user = User(discord_id=discord_id)
    
    try:
        db.add(user)
        await db.commit()
        await db.refresh(user)
    except Exception as e:
        await db.rollback()
        logger.error(f"failed to create user: {str(e)}")
        return None

    return user

# read
async def read_user(
    db:AsyncSession,
    discord_id:Optional[int],
) -> Tuple[List[User], Exception]:
    """
    users, err = await read_user(db, discord_id)
    """
    try:
        query = sqlalchemy.select(User)
        
        if not(discord_id is None):
            query = query.where(User.discord_id == discord_id)
        
        result = await db.execute(query)
        return result.scalars().all(), None
    except Exception as e:
        logger.error(f"failed to read users: {str(e)}")
        return [], e
    
# update

# delete