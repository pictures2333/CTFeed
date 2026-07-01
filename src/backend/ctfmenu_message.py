from typing import Optional, Literal
import logging

from fastapi import HTTPException
import discord
import sqlalchemy

from src.database import database

# logging
logger = logging.getLogger("uvicorn")

# function
async def operate_message(guild: discord.Guild, mode: Literal["send", "recover", "edit"]) -> None:
    """
    :param guild:
    :param channel_id:
    :param mode:

    :raise HTTPException:
    :raise Exception:
    """
    from src.crud import (
        create_or_update_ctfmenu_message,
        read_ctfmenu_message
    )
    from src.backend import config

    # get channel id
    channel_id = (await config.read_config_cache("CTFMENU_CHANNEL_ID"))["CTFMENU_CHANNEL_ID"]
    if channel_id == -1:
        raise HTTPException(500, "CTFMENU_CHANNEL_ID is not set")

    async with database.with_get_db() as session:
        async with session.begin():
            # table lock
            await session.execute(
                sqlalchemy.text(
                    "LOCK TABLE ctfmenu_message IN EXCLUSIVE MODE"
                )
            )

            # get message id
            message_id = None
            ctfmenu_message = await read_ctfmenu_message(session)
            if ctfmenu_message.message_id != -1:
                message_id = ctfmenu_message.message_id

            # fetch channel
            try:
                channel = await guild.fetch_channel(channel_id)
            except discord.NotFound as exc:
                raise HTTPException(500, f"Channel not found (id={channel_id})") from exc
            except discord.Forbidden as exc:
                raise HTTPException(500, f"Forbidden (id={channel_id})") from exc
            except Exception as exc:
                raise HTTPException(500, f"Failed to fetch channel: {str(exc)}") from exc
            
            if not isinstance(channel, discord.TextChannel):
                raise HTTPException(500, f"Wrong channel type (id={channel_id})")

            # fetch message
            message: Optional[discord.Message] = None
            
            if (mode == "recover" or mode == "edit") and (message_id is not None):
                try:
                    message = await channel.fetch_message(ctfmenu_message.message_id)
                except (discord.NotFound, discord.Forbidden) as exc:
                    message = None
                except Exception as exc:
                    raise HTTPException(500, f"Failed to fetch message (channel_id={channel_id}, message_id={ctfmenu_message}): {str(exc)}") from exc

            # send or edit message
            if (mode == "send") or (mode == "recover" and message is None):
                # send message
                view = discord.ui.View(timeout=None)
                view.add_item(
                    discord.ui.Button(
                        label="/ctfmenu",
                        style=discord.ButtonStyle.green,
                        custom_id="ctfmenu_message:ctfmenu"
                    )
                )
                view.add_item(
                    discord.ui.Button(
                        label="Set description",
                        style=discord.ButtonStyle.grey,
                        custom_id="ctfmenu_message:extra_message"
                    )
                )

                embed = discord.Embed(
                    title="🚩 Press button to execute ``/ctfmenu``",
                    description=ctfmenu_message.extra_message,
                    color=discord.Color.green()
                )

                message = await channel.send(embed=embed, view=view)

                # update db
                await create_or_update_ctfmenu_message(
                    session,
                    message_id=message.id,
                )
            
            if (mode == "edit") and (message is not None):
                embed = discord.Embed(
                    title="🚩 Press button to execute ``/ctfmenu``",
                    description=ctfmenu_message.extra_message,
                    color=discord.Color.green()
                )
                await message.edit(embed=embed)
    
    return


async def post_ctfmenu_channel_id(guild: discord.Guild, key: str, value: int) -> None:
    await operate_message(
        guild=guild,
        mode="send"
    )
    return


class SetDescriptionModal(discord.ui.Modal):
    def __init__(self) -> None:
        super().__init__(title="Set description")
        self.add_item(
            discord.ui.InputText(
                label="Enter description...",
                style=discord.InputTextStyle.long,
                required=True
            )
        )
    
    async def callback(self, interaction: discord.Interaction) -> None:
        from src.crud import (
            create_or_update_ctfmenu_message
        )
        from src.backend import security

        # check permission
        if (member := await security.discord_check_user_and_auto_register(interaction, False)) is None:
            return

        await interaction.response.defer()

        try:
            extra_message = str(self.children[0].value)

            # update db
            async with database.with_get_db() as session:
                async with session.begin():
                    await session.execute(
                        sqlalchemy.text(
                            "LOCK TABLE ctfmenu_message IN EXCLUSIVE MODE"
                        )
                    )

                    ctfmenu_message = await create_or_update_ctfmenu_message(session, extra_message=extra_message)

            # edit message
            await operate_message(interaction.guild, "edit")
        except Exception as e:
            errmsg = f"failed to set description for ctfmenu message: {str(e)}"
            logger.error(errmsg)
            await interaction.followup.send(errmsg, ephemeral=True)
            return
        
        await interaction.followup.send("Done", ephemeral=True)
        return


async def bgtask_interaction(interaction: discord.Interaction, bot: discord.Bot, custom_id: str) -> None:
    from src.crud import read_ctfmenu_message
    from src.backend import security
    from src.cog import ctfmenu

    # check prefix
    if not custom_id.startswith("ctfmenu_message:"):
        return
    
    # check permission
    if (member := await security.discord_check_user_and_auto_register(interaction, False)) is None:
        return
    
    # get message id
    message_id: Optional[int] = None
    async with database.with_get_db() as session:
        async with session.begin():
            # table lock
            await session.execute(
                sqlalchemy.text(
                    "LOCK TABLE ctfmenu_message IN EXCLUSIVE MODE"
                )
            )

            # get ctfmenu message
            ctfmenu_message = await read_ctfmenu_message(session)
            message_id = ctfmenu_message.message_id

    if (message_id == -1) or (interaction.message.id != message_id):
        await interaction.response.send_message("Invalid CTFMenu message", ephemeral=True)
        return
    
    # execute
    if custom_id == "ctfmenu_message:ctfmenu":
        view = ctfmenu.EventMenu(bot, member.id, "ctftime")
        embed = await view.build_embed_and_view()
        await interaction.response.send_message(embed=embed, view=view, ephemeral=True)
    elif custom_id == "ctfmenu_message:extra_message":
        await interaction.response.send_modal(SetDescriptionModal())

    return
