from typing import Tuple, Optional, Any, Dict
import logging

from fastapi import HTTPException

from src import schema
from src import crud
from src.bot import get_guild
from src.database import model
from src.database import database
from src.config import settings, settings_lock
from src.backend import config_test

# logging
logger = logging.getLogger("uvicorn")

# config cache
async def update_config_cache(config:model.Config) -> None:
    async with settings_lock:
        for _k in model.config_info:
            try:
                _v = getattr(config, _k.lower())
                setattr(settings, _k, _v)
            except Exception as e:
                logger.critical(f"fail to update cache of config (key={_k}) (maybe src.database.model.Config, src.database.model.config_info and src.config are out of sync): {str(e)}")


async def read_config_cache(key: Optional[str]=None) -> Dict[str, Any]:
    cache_config = {}
    async with settings_lock:
        if key is not None:
            cinfo = model.config_info.get(key)
            if cinfo is None:
                raise HTTPException(404)
            
            try:
                cache_config[key] = cinfo.data_type(getattr(settings, key))
            except Exception as e:
                errmsg = f"fail to get config (key={key}) from settings (cache) (maybe src.database.model.Config, src.database.model.config_info and src.config are out of sync): {str(e)}"
                logger.critical(errmsg)
                raise HTTPException(500, errmsg)
        else:
            for k in model.config_info:
                try:
                    cinfo = model.config_info[k]
                    cache_config[k] = cinfo.data_type(getattr(settings, k))
                except Exception as e:
                    errmsg = f"fail to get config (key={k}) from settings (cache) (maybe src.database.model.Config, src.database.model.config_info and src.config are out of sync): {str(e)}"
                    logger.critical(errmsg)
                    raise HTTPException(500, errmsg)

    return cache_config


# config
async def read_config(key:Optional[str]=None) -> schema.ConfigResponse:
    """
    Read config.
    
    :param bot:
    :param key:
    
    :return ConfigResponse: Guild name, Guild id and Config.
    
    :raise HTTPException:
    """
    # get guild
    guild = get_guild()
    
    # get config
    cache_config = await read_config_cache(key)
    
    # get details
    configs = []
    for k in cache_config:
        cinfo = model.config_info[k]
        v = cache_config[k]
        msg, _ = await config_test.check_config_valid_obj(guild, k, v)
        configs.append(schema.Config(
            key=k,
            description=cinfo.description,
            message=msg,
            value=v,
            ok=(True if _ is not None else False)
        ))
    
    # return
    if key is not None and len(configs) == 0:
        raise HTTPException(404)
    
    return schema.ConfigResponse(
        guild_id=settings.GUILD_ID,
        guild_name=guild.name,
        config=configs
    )


async def update_config(kv:Optional[Tuple]) -> None:
    """
    Update Config in database and cache.
    
    :param bot:
    :param kv: Tuple (key, value)
    
    :raise HTTPException:
    """
    # get guild
    guild = get_guild()
    
    # check arguments
    arg = {}
    post_func = None
    if kv is not None:
        if len(kv) != 2:
            raise HTTPException(400)
        k, v = kv
        
        # check whether k is a valid config
        cinfo = model.config_info.get(k, None)
        if cinfo is None:
            raise HTTPException(400)
        
        # check whether v is valid and points to a valid object in Discord
        try:
            v = cinfo.data_type(v)
        except Exception:
            raise HTTPException(400)
        _, obj = await config_test.check_config_valid_obj(guild, k, v)
        if obj is None:
            raise HTTPException(400)
        
        # success
        arg[k.lower()] = v

        # get post func
        post_func = cinfo.post_func
    
    # update database
    try:
        async with database.with_get_db() as session:
            async with session.begin():
                config = await crud.create_or_update_config(
                    session,
                    **arg
                )
    except Exception as e:
        logger.error(f"fail to update Config in database: {str(e)}")
        raise HTTPException(500, detail=f"fail to update Config in database")
    
    # update cache
    await update_config_cache(config)

    # execute post function
    if post_func is not None:
        try:
            await post_func(guild, k, v)
        except Exception as e:
            logger.error(f"fail to execute post function of {k}: {str(e)}")
            raise HTTPException(500, f"config saved, but fail to execute post function of {k}: {str(e)}")
    
    return


async def test_config(key:str) -> None:
    # get guild
    guild = get_guild()

    # get config
    cache_config = await read_config_cache()
    config_info = model.config_info[key]
    value = cache_config[key]

    # test
    msg, _ = await config_test.check_config_valid_obj(guild, key, value)
    if _ is None:
        raise HTTPException(500, f"Type check for {key} failed")
    
    if (config_info.test_func is not None):
        errmsg = await config_info.test_func(guild, cache_config, key)
        if errmsg:
            raise HTTPException(500, errmsg)
    
    return
