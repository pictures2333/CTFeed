from typing import Optional, Dict, Any, Tuple

import discord

from src.utils.get_category import get_category


async def check_config_valid_obj(guild: discord.Guild, key: str, value: Any) -> Tuple[str, Any]:
    """
    Check whether the value of the config points to a valid object in Discord.
    
    :param guild:
    :param key:
    :param value:
    
    :return message:
    :return object: The object which the value of the config points to.
    """
    from src.database import model

    config_info = model.config_info[key]
        
    msg = ""
    _ = None
    if config_info.config_type == model.ConfigType.CHANNEL and \
            (_ := guild.get_channel(value)) is not None and \
            isinstance(_, discord.TextChannel):
        msg = f"Channel: {_.name}\nID: (value={value})"
    elif config_info.config_type == model.ConfigType.CATEGORY and \
            (_ := get_category(guild, value)) is not None:
        msg = f"Category: {_.name}\nID: (value={value})"
    elif config_info.config_type == model.ConfigType.ROLE and \
            (_ := guild.get_role(value)) is not None:
        msg = f"Role: {_.name}\nID: (value={value})"
    else:
        msg = f"(Invalid)\nvalue={value}"
        _ = None
        
    return msg, _


async def test_send_message(
    guild: discord.Guild,
    config_cache: Dict[str, Any],
    key: str
) -> Optional[str]:
    # get channel
    try:
        channel_id = config_cache.get(key, None)
        if channel_id is None:
            raise ValueError(f"{key} not in config cache")
        
        channel = guild.get_channel(channel_id)
        if (channel is None) or (not isinstance(channel, discord.TextChannel)):
            raise RuntimeError(f"channel (id={channel_id}) not found")
    except Exception as e:
        return f"Get channel failed : {e.__class__.__name__} : {str(e)}"

    # send message
    embed = discord.Embed(
        title="Test message",
        description="This is a test message.",
        color=discord.Color.green()
    )
    try:
        message = await channel.send(embed=embed)
    except Exception as e:
        return f"Send message failed : {e.__class__.__name__} : {(str(e))}"
    
    # delete message
    try:
        await message.delete()
    except Exception as e:
        return f"Delete message failed : {e.__class__.__name__} : {str(e)}"
    
    return None


async def test_ctf_channel_category(
    guild: discord.Guild,
    config_cache: Dict[str, Any],
    key: str
) -> Optional[str]:
    # get category
    try:
        category_id = config_cache.get("CTF_CHANNEL_CATEGORY_ID", None)
        if category_id is None:
            raise ValueError(f"CTF_CHANNEL_CATEGORY_ID not in config cache")
        
        category = get_category(guild, category_id)
        if category is None:
            raise RuntimeError(f"category (id={category_id}) not found")
    except Exception as e:
        return f"Get CTF channel category failed : {e.__class__.__name__} : {str(e)}"

    # create channel
    overwrites = {
        guild.default_role: discord.PermissionOverwrite(view_channel=False)
    }
    try:
        channel = await category.create_text_channel("test", overwrites=overwrites)
    except Exception as e:
        return f"Create text channel failed : {e.__class__.__name__} : {str(e)}"

    result: Optional[str] = None
    try:
        # modify permissions
        try:
            await channel.set_permissions(guild.me, view_channel=True)
        except Exception as e:
            result = f"Modify permissions failed : {e.__class__.__name__} : {str(e)}"
        
        # send message
        if result is None:
            embed = discord.Embed(
                title="Test message",
                description="This is a test message.",
                color=discord.Color.green()
            )
            try:
                await channel.send(embed=embed)
            except Exception as e:
                result = f"Send message to channel failed : {e.__class__.__name__} : {str(e)}"
    finally:
        # delete channel
        try:
            await channel.delete()
        except Exception as e:
            if result is None:
                result = f"Delete channel failed : {e.__class__.__name__} : {str(e)}"
    
    return result


async def test_archive_category(
    guild: discord.Guild,
    config_cache: Dict[str, Any],
    key: str,
) -> Optional[str]:
    # get ctf category
    try:
        ctf_category_id = config_cache.get("CTF_CHANNEL_CATEGORY_ID", None)
        if ctf_category_id is None:
            raise ValueError(f"CTF_CHANNEL_CATEGORY_ID not in config cache")
        
        ctf_category = get_category(guild, ctf_category_id)
        if ctf_category is None:
            raise RuntimeError(f"category (id={ctf_category_id}) not found")
    except Exception as e:
        return f"Get CTF channel category failed : {e.__class__.__name__} : {str(e)}"

    # get archive category
    try:
        archive_category_id = config_cache.get("ARCHIVE_CATEGORY_ID", None)
        if archive_category_id is None:
            raise ValueError(f"ARCHIVE_CATEGORY_ID not in config cache")
        
        archive_category = get_category(guild, archive_category_id)
        if archive_category is None:
            raise RuntimeError(f"category (id={archive_category_id}) not found")
    except Exception as e:
        return f"Get archive category failed : {e.__class__.__name__} : {str(e)}"
    
    # create channel in ctf category
    overwrites = {
        guild.default_role: discord.PermissionOverwrite(view_channel=False),
        guild.me: discord.PermissionOverwrite(view_channel=True)
    }
    try:
        channel = await ctf_category.create_text_channel("test", overwrites=overwrites)
    except Exception as e:
        return f"Create text channel failed : {e.__class__.__name__} : {str(e)}"

    result: Optional[str] = None
    try:
        # move channel to archive category
        try:
            await channel.move(
                category=archive_category,
                beginning=True,
                sync_permissions=True,
                reason=f"test"
            )
        except Exception as e:
            result = f"Move text channel to archive category failed : {e.__class__.__name__} : {str(e)}"
        
        # send message
        if result is None:
            embed = discord.Embed(
                title="Test message",
                description="This is a test message.",
                color=discord.Color.green()
            )
            try:
                await channel.send(embed=embed)
            except Exception as e:
                result = f"Send message to channel failed : {e.__class__.__name__} : {str(e)}"
    finally:
        # delete channel
        try:
            await channel.delete()
        except Exception as e:
            if result is None:
                result = f"Delete channel failed : {e.__class__.__name__} : {str(e)}"
    
    return result
