"""add employee_transactions table

Revision ID: 20260707_0005
Revises: 20260704_0004
Create Date: 2026-07-07

Creates the ``employee_transactions`` table linking financial transactions to a
specific employee (``employee_id`` references ``users.id``). Guards keep the
revision safe on databases that were partially bootstrapped via create_all() or
the startup schema repair.
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "20260707_0005"
down_revision: Union[str, None] = "20260704_0004"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

TABLE = "employee_transactions"

_INDEXES = [
    ("ix_employee_transactions_employee_id", ["employee_id"]),
    ("ix_employee_transactions_status", ["status"]),
    ("ix_employee_transactions_transaction_type", ["transaction_type"]),
    ("ix_employee_transactions_transaction_date", ["transaction_date"]),
    ("ix_employee_transactions_reference_id", ["reference_id"]),
    ("ix_employee_transactions_is_archived", ["is_archived"]),
    ("ix_employee_transactions_created_at", ["created_at"]),
    ("idx_emptx_employee_date", ["employee_id", "transaction_date"]),
    ("idx_emptx_status_type", ["status", "transaction_type"]),
]


def _table_exists(table: str) -> bool:
    return sa.inspect(op.get_bind()).has_table(table)


def _index_exists(table: str, index: str) -> bool:
    inspector = sa.inspect(op.get_bind())
    if not inspector.has_table(table):
        return False
    return index in {idx["name"] for idx in inspector.get_indexes(table)}


def upgrade() -> None:
    if not _table_exists(TABLE):
        op.create_table(
            TABLE,
            sa.Column("id", sa.String(length=36), nullable=False),
            sa.Column("employee_id", sa.String(length=36), nullable=False),
            sa.Column("transaction_type", sa.String(length=50), nullable=False),
            sa.Column("amount", sa.Float(), nullable=False),
            sa.Column("currency", sa.String(length=3), nullable=False, server_default=sa.text("'USD'")),
            sa.Column("status", sa.String(length=50), nullable=False, server_default=sa.text("'pending'")),
            sa.Column("description", sa.Text(), nullable=True),
            sa.Column("reference_id", sa.String(length=100), nullable=True),
            sa.Column("transaction_date", sa.DateTime(), nullable=False),
            sa.Column("is_archived", sa.Boolean(), nullable=False, server_default=sa.false()),
            sa.Column("created_at", sa.DateTime(), nullable=True),
            sa.Column("updated_at", sa.DateTime(), nullable=True),
            sa.ForeignKeyConstraint(["employee_id"], ["users.id"], ondelete="CASCADE"),
            sa.PrimaryKeyConstraint("id"),
        )

    for index_name, columns in _INDEXES:
        if not _index_exists(TABLE, index_name):
            op.create_index(index_name, TABLE, columns)


def downgrade() -> None:
    for index_name, _ in _INDEXES:
        if _index_exists(TABLE, index_name):
            op.drop_index(index_name, table_name=TABLE)
    if _table_exists(TABLE):
        op.drop_table(TABLE)
