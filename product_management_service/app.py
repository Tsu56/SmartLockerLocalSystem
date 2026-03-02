from fastapi import FastAPI
from api import router as product_management_router
from contextlib import asynccontextmanager
from sqlmodel import SQLModel
from database import create_db_and_tables
from product_sync_agent import start_product_sync_agent

@asynccontextmanager
async def lifespan(app: FastAPI):
    create_db_and_tables()
    start_product_sync_agent()
    yield

app = FastAPI(lifespan=lifespan)

app.include_router(product_management_router)