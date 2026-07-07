"""Deployment schema bootstrap.

Standard, idempotent "make the database match the models" step. Creates any
missing tables, columns, and indexes (additive only), then stamps Alembic to
head so the version table reflects reality.

Usage (from the Backend/ directory):

    python -m scripts.ensure_schema
    # or
    python scripts/ensure_schema.py

Run it once during deploy, before starting the API. Safe to run repeatedly.
"""

from __future__ import annotations

import logging
import os
import sys

logging.basicConfig(level=os.getenv("LOG_LEVEL", "INFO"))
logger = logging.getLogger("ensure_schema")


def main() -> int:
    # Import inside main so a bad DATABASE_URL fails with a clear message.
    from app.db.session import ensure_schema

    ensure_schema()

    # Keep Alembic's version table honest so future migrations run cleanly.
    try:
        from alembic import command
        from alembic.config import Config

        here = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        cfg = Config(os.path.join(here, "alembic.ini"))
        command.stamp(cfg, "head")
        logger.info("ensure_schema: alembic stamped to head")
    except Exception as exc:  # noqa: BLE001
        logger.warning("ensure_schema: could not stamp alembic head (%s)", exc)

    logger.info("ensure_schema: complete")
    return 0


if __name__ == "__main__":
    sys.exit(main())
