from typing import Optional

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.dialects.postgresql import insert as postgresql_insert
import sqlalchemy

from src.database.model import CTFMenuMessage

# create and update
async def create_or_update_ctfmenu_message(
    session: AsyncSession,
    message_id: Optional[int]=None,
    extra_message: Optional[str]=None,
) -> CTFMenuMessage:
    """
    *This function "flushes" changes. Caller has to commit changes manually.*

    Create or update a CTFMenuMessage in database.

    :param session:
    :param message_id:
    :param extra_message:

    :return: The CTFMenuMessage that was created or updated.

    :raise (Exception from sqlalchemy):
    """
    # args
    _args = {
        "message_id": message_id,
        "extra_message": extra_message
    }

    args = {"id": 1}
    for k in _args:
        if _args[k] is not None:
            args[k] = _args[k]

    # stmt
    stmt = (
        postgresql_insert(CTFMenuMessage)
        .values(args)
        .returning(CTFMenuMessage)
        .on_conflict_do_update(
            index_elements=["id"],
            set_=args
        )
    )
    
    # execute
    try:
        result = (await session.execute(stmt)).scalar_one()
        await session.flush()
        await session.refresh(result)
        return result
    except Exception:
        raise


# read
async def read_ctfmenu_message(session: AsyncSession) -> CTFMenuMessage:
    """
    Read CTFMenuMessage.

    :param session:

    :return CTFMenuMessage:

    :raise (Exception from sqlalchemy):
    """
    stmt = sqlalchemy.select(CTFMenuMessage).where(CTFMenuMessage.id == 1)
    try:
        return (await session.execute(stmt)).scalar_one()
    except Exception:
        raise
