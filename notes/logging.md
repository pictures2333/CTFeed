# About logging
- Critical
    - fail to initialize config in database
    - fail to initialize ctfmenu message in database
    - fail to initialize or stop ``aiohttp.ClientSession``
    - fail to get or update config from settings (cache) -> src.database.model.Config, src.database.model.config_info and src.config.Settings are out of sync 
    - Guild not found
    - configured CTF channel category or archive category not found
    - (discord bot) fail to load extension
    - locally caught failure in rollback or non-test cleanup of ``try...except...finally...``

- Rollback 出錯誤一律使用 critical
- Rollback logging 一律在前面加上 ``[rollback]``
