from sqlmodel import SQLModel, create_engine, Session
from app.config.settings import get_settings

_engine = None


def get_engine():
    global _engine
    if _engine is None:
        settings = get_settings()
        _engine = create_engine(settings.database_url, connect_args={"check_same_thread": False})
    return _engine


def create_db_and_tables() -> None:
    # Import models so SQLModel metadata picks them up
    import app.db.models  # noqa: F401
    SQLModel.metadata.create_all(get_engine())


def get_session():
    with Session(get_engine()) as session:
        yield session
