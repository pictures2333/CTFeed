from typing import List, Optional, Tuple

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload
import sqlalchemy

from src.database.model import User

# create
async def create_user(db:AsyncSession, discord_id:int) -> User:
    user = User(discord_id=discord_id)
    
    try:
        db.add(user)
        await db.commit()
        await db.refresh(user)
        return user
    except:
        await db.rollback()
        raise


# read
async def read_user(db:AsyncSession, discord_id:Optional[int]=None) -> List[User]:
    query = sqlalchemy.select(User) \
        .options(selectinload(User.events))
        
    if not(discord_id is None):
        query = query.where(User.discord_id == discord_id)
        
    result = await db.execute(query)
    return result.scalars().all(), None


# update

# delete