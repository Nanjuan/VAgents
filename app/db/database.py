from sqlalchemy import text
from sqlmodel import SQLModel, create_engine, Session
from app.config.settings import get_settings

_engine = None


def get_engine():
    global _engine
    if _engine is None:
        settings = get_settings()
        _engine = create_engine(settings.database_url, connect_args={"check_same_thread": False})
    return _engine


def _sqlite_add_column_if_missing(engine, table: str, column: str, coltype: str) -> None:
    """Best-effort SQLite ALTER for existing deployments."""
    try:
        with engine.connect() as conn:
            conn.execute(text(f"ALTER TABLE {table} ADD COLUMN {column} {coltype}"))
            conn.commit()
    except Exception:
        pass


def _migrate_sqlite_schema(engine) -> None:
    settings = get_settings()
    if not str(settings.database_url).startswith("sqlite"):
        return
    # ChatMessage
    for column, ctype in (
        ("tool_calls_json", "TEXT"),
        ("tool_call_id", "TEXT"),
    ):
        _sqlite_add_column_if_missing(engine, "chatmessage", column, ctype)
    # ApprovalRequest
    for column, ctype in (
        ("profile_name", "TEXT"),
        ("tool_id", "TEXT"),
        ("tool_call_id", "TEXT"),
    ):
        _sqlite_add_column_if_missing(engine, "approvalrequest", column, ctype)


def create_db_and_tables() -> None:
    # Import models so SQLModel metadata picks them up
    import app.db.models  # noqa: F401
    engine = get_engine()
    SQLModel.metadata.create_all(engine)
    _migrate_sqlite_schema(engine)


def get_session():
    with Session(get_engine()) as session:
        yield session
