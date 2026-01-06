#!/usr/bin/env python3

from contextlib import asynccontextmanager
import logging

from fastapi import FastAPI

from src.database import database
from src import schema
from src import bot

# startup and shutdown
@asynccontextmanager
async def lifespan(app:FastAPI):
    # startup
    ## initialize database
    await database.init_db()
    
    ## start discord bot
    await bot.start_bot()
    
    # app run
    yield
    
    # shutdown
    ## stop discord bot
    await bot.stop_bot()


# app
app = FastAPI(debug=False, lifespan=lifespan)

@app.get("/")
async def index() -> schema.General:
    return schema.General(
        success=True,
        message="Shirakami Fubuki is the cutest fox in the world!"
    )
