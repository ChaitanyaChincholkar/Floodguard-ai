import os
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy.orm import declarative_base

# The database URL for asyncpg, defaulting to localhost for local non-docker runs
DATABASE_URL = os.getenv(
    "DATABASE_URL", 
    "postgresql+asyncpg://floodguard_user:floodguard_password@localhost:5432/floodguard"
)

# Async engine
engine = create_async_engine(DATABASE_URL, echo=True)

# Async session factory
AsyncSessionLocal = async_sessionmaker(
    bind=engine,
    class_=AsyncSession,
    expire_on_commit=False,
)

Base = declarative_base()

async def get_db():
    async with AsyncSessionLocal() as session:
        yield session
