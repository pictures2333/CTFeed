from typing import List, Optional, Tuple

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload
import sqlalchemy

from src.database.model import User, Status, Skills, RhythmGames

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
    return result.scalars().all()


# update
async def update_user(
    db:AsyncSession,
    discord_id:int,
    status:Optional[Status]=None,
    skills:Optional[List[Skills]]=None,
    rhythm_games:Optional[List[RhythmGames]]=None
) -> User:
    try:
        stmt = sqlalchemy.select(User).where(User.discord_id == discord_id)
        user = (await db.execute(stmt)).scalar_one_or_none()
        if user is None:
            raise Exception(f"user (discord_id={discord_id}) not found")
        
        if not(status is None):
            user.status = status
            
        if not(skills is None):
            user.skills = skills
            
        if not(rhythm_games is None):
            user.rhythm_games = rhythm_games

        # commit
        await db.commit()
        await db.refresh(user)
        return user
    except:
        await db.rollback()
        raise


# delete