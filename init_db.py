from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase

DATABASE_URL = 'sqlite+aiosqlite:///mobil.db'

engine = create_async_engine(DATABASE_URL, echo=True)

AsyncSessionLocal = async_sessionmaker(bind=engine, expire_on_commit=True)

class Base(DeclarativeBase):
    pass

async def get_session():
    async with AsyncSessionLocal() as session:
        yield session