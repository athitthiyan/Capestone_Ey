"""initial base schema

Baseline migration so a completely fresh database can be built with a single
`alembic upgrade head` — no manual create_all() step required. It creates every
model table EXCEPT the ones added by later migrations (those migrations create
their own tables and would collide).

`checkfirst=True` makes this migration safe to run against a database that
already has some or all base tables (e.g. one previously bootstrapped via
init_db()/create_all): existing tables are skipped.

Revision ID: 20260625_0000
Revises:
Create Date: 2026-07-03
"""

from typing import Sequence, Union

from alembic import op

revision: str = "20260625_0000"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

# Tables owned by later migrations — excluded here so those migrations'
# op.create_table() calls don't fail with "already exists" on a fresh DB.
_LATER_MIGRATION_TABLES = {
    "third_party_evidence_verifications",  # 20260630_0001
    "request_logs",                        # 20260701_0002
    "runtime_settings",                    # 20260701_0003
    "llm_call_logs",                       # 20260701_0003
    "ragas_evaluation_results",            # 20260704_0004
}


def _base_tables():
    from app.db.models import Base

    return Base.metadata, [
        table
        for name, table in Base.metadata.tables.items()
        if name not in _LATER_MIGRATION_TABLES
    ]


def upgrade() -> None:
    metadata, tables = _base_tables()
    metadata.create_all(bind=op.get_bind(), tables=tables, checkfirst=True)


def downgrade() -> None:
    metadata, tables = _base_tables()
    metadata.drop_all(bind=op.get_bind(), tables=tables, checkfirst=True)
