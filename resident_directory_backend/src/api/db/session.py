from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from src.api.core.config import get_settings

settings = get_settings()

# Using synchronous SQLAlchemy for simplicity and reliability in template CI.
engine = create_engine(settings.postgres_url, pool_pre_ping=True)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


# PUBLIC_INTERFACE
def get_db():
    """FastAPI dependency that provides a SQLAlchemy session."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
