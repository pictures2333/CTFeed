import logging

from fastapi import APIRouter, HTTPException, Request, Depends
from fastapi.responses import RedirectResponse
from authlib.integrations.starlette_client import OAuth
from sqlalchemy.ext.asyncio import AsyncSession
import discord

from src.config import settings
from src.backend import security
from src.backend import get_user
from src.database.database import fastapi_get_db
from src import crud
from src import schema
from src.database import model
from src.backend.security import fastapi_check_user

# logging
logger = logging.getLogger("uvicorn")

# oauth
oauth = OAuth()
oauth.register(
    name="discord",
    client_id=settings.DISCORD_OAUTH2_CLIENT_ID,
    client_secret=settings.DISCORD_OAUTH2_CLIENT_SECRET,
    access_token_url='https://discord.com/api/oauth2/token',
    access_token_params=None,
    authorize_url='https://discord.com/api/oauth2/authorize',
    authorize_params=None,
    api_base_url='https://discord.com/api/users/@me',
    client_kwargs={'scope': 'identify email guilds connections'},
)

# router
router = APIRouter(prefix="/auth")

# auth
@router.get("/discord")
async def login_discord(request:Request):
    return await oauth.discord.authorize_redirect(
        request,
        settings.DISCORD_OAUTH2_REDIRECT_URI
    )


@router.get("/login")
async def login(
    request:Request,
    db:AsyncSession=Depends(fastapi_get_db),
):
    # get token
    try:
        token = await oauth.discord.authorize_access_token(request)
    except:
        raise HTTPException(400)

    # get user info
    try:
        user_resp = await oauth.discord.get("https://discord.com/api/users/@me", token=token)
        user_info = user_resp.json()
        user_id:int = int(user_info["id"])
    except Exception as e:
        logger.error(f"login(): failed to get user info: {e}")
        raise HTTPException(500)
    
    # check permission and login (or register)
    db_user, member = await security.auto_register_and_check_user(user_id, False, True)
    
    # login
    request.session["discord_id"] = user_id
    return RedirectResponse(settings.HTTP_FRONTEND_URL)


@router.get("/logout")
async def logout(request:Request):
    request.session["discord_id"] = 0
    return RedirectResponse(settings.HTTP_FRONTEND_URL)


# read
@router.get("/me")
async def read_me(
    db:AsyncSession=Depends(fastapi_get_db),
    u:model.User=Depends(fastapi_check_user)
) -> schema.User:
    db_user:model.User = u[0]
    return (await get_user.get_user(db_user.discord_id))


# update
@router.patch("/me")
async def update_me(
    data:schema.UpdateUser,
    db:AsyncSession=Depends(fastapi_get_db),
    u:model.User=Depends(fastapi_check_user),
) -> schema.User:
    db_user:model.User = u[0]
    discord_id = db_user.discord_id
    
    try:
        # update user
        await crud.update_user(
            db,
            discord_id=discord_id,
            status=data.status,
            skills=data.skills,
            rhythm_games=data.rhythm_games
        )
        
        # get again
        return (await get_user.get_user(discord_id))
    except Exception as e:
        logger.error(f"failed to update user (discord_id={discord_id}) on database: {str(e)}")
        raise HTTPException(status_code=500, detail=f"failed to update user (discord_id={discord_id}) on database")
