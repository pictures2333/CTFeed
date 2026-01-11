from sqlalchemy.ext.asyncio import AsyncSession
from fastapi import HTTPException

from src.backend import security
from src.schema import User, DiscordUser

async def get_user(discord_id:int) -> User:
    try:
        u = await security.auto_register_and_check_user(discord_id, False, False)
    except:
        raise HTTPException(status_code=404, detail=f"invalid user (discord_id={discord_id})")
    db_user, member = u
    
    return User(
        discord_id=db_user.discord_id,
        status=db_user.status,
        skills=db_user.skills,
        rhythm_games=db_user.rhythm_games,
        events=db_user.events,
        discord=DiscordUser(
            display_name=member.display_name,
            id=member.id,
            name=member.name
        )
    )
