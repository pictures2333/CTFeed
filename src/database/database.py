from contextlib import asynccontextmanager

from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession

from src.config import settings

engine = create_async_engine(
    settings.DATABASE_URL,
    echo=False,
)

AsyncSessionLocal = async_sessionmaker(
    engine,
    expire_on_commit=False,
    class_=AsyncSession
)

# get database session
@asynccontextmanager
async def with_get_db():
    session = AsyncSessionLocal()
    try:
        yield session
    finally:
        await session.close()


async def fastapi_get_db():
    session = AsyncSessionLocal()
    try:
        yield session
    finally:
        await session.close()
