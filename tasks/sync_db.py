from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from config import settings

SYNC_DATABASE_URL = settings.DATABASE_URL.replace("+asyncpg", "")
sync_engine = create_engine(SYNC_DATABASE_URL)
SyncSessionLocal = sessionmaker(bind=sync_engine)