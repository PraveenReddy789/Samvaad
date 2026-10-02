from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base
from backend.config import DATABASE_URL

# For SQLite, check_same_thread=False is needed for multi-threaded FastAPI handlers
connect_args = {"check_same_thread": False} if DATABASE_URL.startswith("sqlite") else {}

engine = create_engine(
    DATABASE_URL,
    connect_args=connect_args,
    echo=False
)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()


def get_db():
    """Dependency for obtaining database session in FastAPI routes."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
