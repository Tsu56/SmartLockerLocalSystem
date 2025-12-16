from typing import Annotated
from contextlib import asynccontextmanager
from fastapi import FastAPI, Query, HTTPException
from sqlmodel import SQLModel, select
from database import engine

def create_db_and_tables():
    SQLModel.metadata.create_all(engine)

@asynccontextmanager
async def lifespan(app: FastAPI):
    create_db_and_tables()
    yield

app = FastAPI(lifespan=lifespan)

@app.post("/api/")