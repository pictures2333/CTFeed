from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    # Discord bot configuration
    DISCORD_BOT_TOKEN:str
    
    # CTFTime tracking configuration
    CTFTIME_API_URL:str="https://ctftime.org/api/v1/events/"
    TEAM_API_URL:str="https://ctftime.org/api/v1/teams/"
    DATABASE_SEARCH_DAYS:int=-90 # known events: finish > now_day+(-90)
    CHECK_INTERVAL_MINUTES:int
    
    GUILD_ID:int                    # the guild which the bot works for
    ANNOUNCEMENT_CHANNEL_ID:int     # the channel which the bot sends notifications to
    CTF_CHANNEL_CATETORY_ID:int     # the category stores active CTF channels
    ARCHIVE_CATEGORY_ID:int         # the category stores old CTF channels
    PM_ROLE_ID:int
    MEMBER_ROLE_ID:int
    
    # Database configuration
    DATABASE_URL:str
    
    # Misc
    TIMEZONE:str
    EMOJI:str="🚩"

    model_config = SettingsConfigDict(env_file=".env")

settings = Settings()
