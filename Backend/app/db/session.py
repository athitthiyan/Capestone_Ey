"""
Database session management.
Handles connection pooling, session lifecycle, and transaction management.
"""

import logging
from typing import Iterator

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


def _server_default_ddl(column) -> str | None:
    """Best-effort SQL literal for a column's server_default (for ADD COLUMN)."""
    server_default = getattr(column, "server_default", None)
    arg = getattr(server_default, "arg", None)
    if arg is None:
        return None
    try:
        return str(arg.compile(dialect=engine.dialect, compile_kwargs={"literal_binds": True}))
    except Exception:  # noqa: BLE001
        text_value = getattr(arg, "text", None)
        return str(text_value) if text_value is not None else None


def _add_missing_columns(connection, inspector, table) -> None:
    """ALTER TABLE ADD COLUMN for every model column absent from the live table.

    Additive and safe: a NOT NULL column with no default is added as NULLABLE
    (with a warning) so the statement cannot fail on an already-populated table.
    """
    existing = {col["name"] for col in inspector.get_columns(table.name)}
    for column in table.columns:
        if column.name in existing:
            continue
        col_type = column.type.compile(dialect=engine.dialect)
        pieces = [f"ALTER TABLE {table.name} ADD COLUMN {column.name} {col_type}"]
        default_ddl = _server_default_ddl(column)
        nullable = column.nullable
        if not nullable and default_ddl is None:
            logger.warning(
                "ensure_schema: adding %s.%s as NULLABLE (model is NOT NULL but has "
                "no server_default); backfill + a migration are needed to enforce it",
                table.name,
                column.name,
            )
            nullable = True
        if default_ddl is not None:
            pieces.append(f"DEFAULT {default_ddl}")
        if not nullable:
            pieces.append("NOT NULL")
        connection.execute(text(" ".join(pieces)))
        logger.warning("ensure_schema: added missing column %s.%s", table.name, column.name)


def ensure_schema() -> None:
    """Idempotent, global schema bootstrap for deployment.

    Additive only: creates any missing TABLES, COLUMNS, and INDEXES declared on
    the SQLAlchemy models (``Base.metadata``). Safe to run repeatedly and against
    any database state (empty, partially built, or fully migrated). It never
    drops, renames, or retypes existing objects - those still require an explicit
    Alembic migration.
    """
    logger.info("ensure_schema: syncing database to models (additive)")

    # 1) Missing tables. checkfirst leaves existing tables untouched.
    Base.metadata.create_all(bind=engine, checkfirst=True)

    # 2) Missing columns on already-existing tables (create_all won't ALTER them).
    inspector = inspect(engine)
    with engine.begin() as connection:
        for table in Base.metadata.sorted_tables:
            if inspector.has_table(table.name):
                _add_missing_columns(connection, inspector, table)

    # 3) Missing indexes (checkfirst avoids duplicates).
    inspector = inspect(engine)
    for table in Base.metadata.sorted_tables:
        if not inspector.has_table(table.name):
            continue
        for index in table.indexes:
            try:
                index.create(bind=engine, checkfirst=True)
            except Exception as exc:  # noqa: BLE001
                logger.warning("ensure_schema: index %s not created: %s", index.name, exc)

    logger.info("ensure_schema: database is in sync with the models")


def ensure_schema_compatibility() -> None:
    """Backwards-compatible name; now runs the generic, global sync."""
    ensure_schema()


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
