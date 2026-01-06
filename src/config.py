from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    # Discord bot configuration
    DISCORD_BOT_TOKEN:str
    GUILD_ID:int                    # the guild which the bot works for
    ANNOUNCEMENT_CHANNEL_ID:int     # the channel which the bot sends notifications to
    CTF_CHANNEL_CATETORY_ID:int     # the category stores active CTF channels
    ARCHIVE_CATEGORY_ID:int         # the category stores old CTF channels
    PM_ROLE_ID:int
    MEMBER_ROLE_ID:int
    
    # HTTP API configuration
    HTTP_SECRET_KEY:str
    HTTP_COOKIE_MAX_AGE:int=60*60*24*30    # in seconds
    HTTP_FRONTEND_URL:str
    HTTP_COOKIE_DOMAIN:str
    
    # Discord OAuth2 configuration
    DISCORD_OAUTH2_CLIENT_ID:str
    DISCORD_OAUTH2_CLIENT_SECRET:str
    DISCORD_OAUTH2_REDIRECT_URI:str
    
    # CTFTime tracking configuration
    CTFTIME_API_URL:str="https://ctftime.org/api/v1/events/"
    TEAM_API_URL:str="https://ctftime.org/api/v1/teams/"
    DATABASE_SEARCH_DAYS:int=-90    # known events: finish > now_day+(-90)
    CHECK_INTERVAL_MINUTES:int
    
    # Database configuration
    DATABASE_URL:str
    
    # Misc
    TIMEZONE:str
    EMOJI:str="🚩"

    model_config = SettingsConfigDict(env_file=".env")

settings = Settings()
