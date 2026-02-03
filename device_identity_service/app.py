from fastapi import FastAPI
from api import router as auth_router
from contextlib import asynccontextmanager
from sqlmodel import SQLModel
from database import create_db_and_tables

@asynccontextmanager
async def lifespan(app: FastAPI):
    create_db_and_tables()
    yield

app = FastAPI(lifespan=lifespan)

app.include_router(auth_router)