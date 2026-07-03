"""
Database session management.
Handles connection pooling, session lifecycle, and transaction management.
"""

import logging
from typing import Iterable, Iterator

from sqlalchemy import create_engine, event, inspect, text
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import NullPool, QueuePool

from app.core.config import settings
from app.db.models import Base

logger = logging.getLogger(__name__)

_is_sqlite = settings.DATABASE_URL.startswith("sqlite")
_is_postgres = "postgresql" in settings.DATABASE_URL


def _build_engine_kwargs() -> dict:
    """Build engine kwargs. NullPool does not accept pool_size/max_overflow."""
    kwargs: dict = {"echo": settings.DATABASE_ECHO, "pool_pre_ping": True}
    if _is_sqlite:
        kwargs["poolclass"] = NullPool
        kwargs["connect_args"] = {"check_same_thread": False}
    else:
        kwargs["poolclass"] = QueuePool
        kwargs["pool_size"] = settings.DATABASE_POOL_SIZE
        kwargs["max_overflow"] = settings.DATABASE_MAX_OVERFLOW
        kwargs["pool_timeout"] = settings.DATABASE_POOL_TIMEOUT
        kwargs["pool_recycle"] = settings.DATABASE_POOL_RECYCLE
        if _is_postgres:
            kwargs["connect_args"] = {
                "connect_timeout": 10,
                "application_name": settings.APP_NAME,
            }
    return kwargs


engine = create_engine(settings.DATABASE_URL, **_build_engine_kwargs())
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def get_db_session() -> Iterator[Session]:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def init_db() -> None:
    logger.info("Initializing database...")
    Base.metadata.create_all(bind=engine)
    ensure_schema_compatibility()
    logger.info("Database initialized")


def _compile_column_type(table_name: str, column_name: str) -> str:
    column = Base.metadata.tables[table_name].c[column_name]
    return column.type.compile(dialect=engine.dialect)


def _add_missing_columns(table_name: str, column_names: Iterable[str]) -> None:
    inspector = inspect(engine)
    if not inspector.has_table(table_name):
        return

    existing_columns = {column["name"] for column in inspector.get_columns(table_name)}
    missing_columns = [
        column_name for column_name in column_names if column_name not in existing_columns
    ]
    if not missing_columns:
        return

    with engine.begin() as connection:
        for column_name in missing_columns:
            column_type = _compile_column_type(table_name, column_name)
            logger.warning(
                "Adding missing schema column %s.%s at startup",
                table_name,
                column_name,
            )
            connection.execute(
                text(f"ALTER TABLE {table_name} ADD COLUMN {column_name} {column_type}")
            )


def _ensure_indexes(table_name: str) -> None:
    table = Base.metadata.tables.get(table_name)
    inspector = inspect(engine)
    if table is None or not inspector.has_table(table_name):
        return
    existing_columns = {column["name"] for column in inspector.get_columns(table_name)}
    for index in table.indexes:
        if any(column.name not in existing_columns for column in index.columns):
            continue
        index.create(bind=engine, checkfirst=True)


def ensure_schema_compatibility() -> None:
    """Patch additive columns/tables missed by older create_all bootstraps.

    Alembic is still the source of truth. This exists for local/test databases
    that were originally created with SQLAlchemy create_all(), because create_all
    will create new tables but will not ALTER existing tables when models gain
    nullable columns.
    """

    _add_missing_columns(
        "investigations",
        ("ground_truth_verdict", "ground_truth_set_at"),
    )
    _add_missing_columns("llm_call_logs", ("investigation_id",))

    ragas_table = Base.metadata.tables["ragas_evaluation_results"]
    ragas_table.create(bind=engine, checkfirst=True)
    _ensure_indexes("llm_call_logs")
    _ensure_indexes("ragas_evaluation_results")


def drop_db() -> None:
    logger.warning("Dropping all database tables...")
    Base.metadata.drop_all(bind=engine)


@event.listens_for(engine, "connect")
def _on_connect(dbapi_conn, connection_record):
    if _is_sqlite:
        cursor = dbapi_conn.cursor()
        cursor.execute("PRAGMA journal_mode=WAL")
        cursor.execute("PRAGMA synchronous=NORMAL")
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()
    elif _is_postgres:
        cursor = dbapi_conn.cursor()
        cursor.execute("SET search_path TO public")
        cursor.close()


def check_db_connection() -> bool:
    try:
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        return True
    except Exception as e:  # noqa: BLE001
        logger.error(f"Database connection check failed: {e}")
        return False
