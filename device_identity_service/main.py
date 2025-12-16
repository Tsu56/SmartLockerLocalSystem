from typing import Annotated
from contextlib import asynccontextmanager
from fastapi import FastAPI, Query, HTTPException
from sqlmodel import SQLModel, select
from database import engine, SessionDep, Item, ItemCreate, ItemPublic, ItemUpdate

def create_db_and_tables():
    SQLModel.metadata.create_all(engine)

@asynccontextmanager
async def lifespan(app: FastAPI):
    create_db_and_tables()
    yield

app = FastAPI(lifespan=lifespan)

@app.post("/items/", response_model=ItemPublic)
def create_item(item: ItemCreate, session: SessionDep):
    db_item = Item.model_validate(item)
    session.add(db_item)
    session.commit()
    session.refresh(db_item)
    return db_item

@app.get("/items/", response_model=list[ItemPublic])
def read_items(
    session: SessionDep,
    offset: int = 0,
    limit: Annotated[int, Query(le=100)] = 100,
) -> list[Item]:
    items = session.exec(select(Item).offset(offset).limit(limit)).all()
    return items

@app.get("/items/{item_id}", response_model=ItemPublic)
def read_item(item_id: int, session: SessionDep):
    item = session.get(Item, item_id)
    if not item:
        raise HTTPException(status_code=404, detail="Item not found")
    return item

@app.patch("/items/{item_id}", response_model=ItemPublic)
def update_item(item_id: int, item: ItemUpdate, session: SessionDep):
    item_db = session.get(Item, item_id)
    if not item_db:
        raise HTTPException(status_code=404, detail="Item not found")
    item_data = item.model_dump(exclude_unset=True)
    item_db.sqlmodel_update(item_data)
    session.add(item_db)
    session.commit()
    session.refresh(item_db)
    return item_db

@app.delete("/items/{item_id}")
def delete_item(item_id: int, session: SessionDep):
    item = session.get(Item, item_id)
    if not item:
        raise HTTPException(status_code=404, detail="Item not found")
    session.delete(item)
    session.commit()
    return {"ok": True}