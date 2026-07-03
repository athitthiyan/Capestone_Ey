"""add ground truth field, llm_call_logs.investigation_id, and ragas_evaluation_results

Revision ID: 20260704_0004
Revises: 20260701_0003
Create Date: 2026-07-04

Note on idempotent column adds: the ``investigations`` table is created by
the base migration (20260625_0000) directly from the live ``Base.metadata``
(see that file's docstring), so on a brand-new database it already picks up
whatever columns exist on the ``Investigation`` model at migration-run time -
including the two added here. On an existing (already-bootstrapped) database
those columns genuinely don't exist yet and need the ALTER TABLE. The
``_column_exists`` guard makes this migration correct in both cases.
``ragas_evaluation_results`` is guarded too so this revision remains safe after
partial local create_all() bootstraps or startup schema repair.
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "20260704_0004"
down_revision: Union[str, None] = "20260701_0003"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _column_exists(table: str, column: str) -> bool:
    inspector = sa.inspect(op.get_bind())
    if not inspector.has_table(table):
        return False
    return column in {col["name"] for col in inspector.get_columns(table)}


def _table_exists(table: str) -> bool:
    inspector = sa.inspect(op.get_bind())
    return inspector.has_table(table)


def _index_exists(table: str, index: str) -> bool:
    inspector = sa.inspect(op.get_bind())
    if not inspector.has_table(table):
        return False
    return index in {idx["name"] for idx in inspector.get_indexes(table)}


def _create_index_if_missing(index: str, table: str, columns: list[str]) -> None:
    if not _index_exists(table, index):
        op.create_index(index, table, columns)


def upgrade() -> None:
    # Human-confirmed final verdict on a case, set by a reviewer on
    # approve/reject. Unlocks the 3 reference-dependent RAGAS metrics.
    if not _column_exists("investigations", "ground_truth_verdict"):
        op.add_column(
            "investigations", sa.Column("ground_truth_verdict", sa.Text(), nullable=True)
        )
    if not _column_exists("investigations", "ground_truth_set_at"):
        op.add_column(
            "investigations", sa.Column("ground_truth_set_at", sa.DateTime(), nullable=True)
        )

    # Lets telemetry rows be joined back to the case they were produced for,
    # so the RAGAS judge can identify which provider/model to attribute a
    # score to (app/evaluation/ragas_judge.py::_scored_llm).
    if not _column_exists("llm_call_logs", "investigation_id"):
        op.add_column(
            "llm_call_logs", sa.Column("investigation_id", sa.String(length=36), nullable=True)
        )
    _create_index_if_missing(
        op.f("ix_llm_call_logs_investigation_id"), "llm_call_logs", ["investigation_id"]
    )

    if not _table_exists("ragas_evaluation_results"):
        op.create_table(
            "ragas_evaluation_results",
            sa.Column("id", sa.String(length=36), nullable=False),
            sa.Column("investigation_id", sa.String(length=36), nullable=False),
            sa.Column("metric", sa.String(length=100), nullable=False),
            sa.Column("score", sa.Float(), nullable=True),
            sa.Column("is_reference_metric", sa.Boolean(), nullable=True),
            sa.Column("scored_provider", sa.String(length=50), nullable=True),
            sa.Column("scored_model", sa.String(length=120), nullable=True),
            sa.Column("judge_model", sa.String(length=120), nullable=True),
            sa.Column("error_message", sa.Text(), nullable=True),
            sa.Column("created_at", sa.DateTime(), nullable=True),
            sa.Column("updated_at", sa.DateTime(), nullable=True),
            sa.ForeignKeyConstraint(
                ["investigation_id"], ["investigations.id"], ondelete="CASCADE"
            ),
            sa.PrimaryKeyConstraint("id"),
            sa.UniqueConstraint(
                "investigation_id", "metric", name="uq_ragas_investigation_metric"
            ),
        )
    _create_index_if_missing(
        op.f("ix_ragas_evaluation_results_investigation_id"),
        "ragas_evaluation_results",
        ["investigation_id"],
    )
    _create_index_if_missing(
        op.f("ix_ragas_evaluation_results_metric"), "ragas_evaluation_results", ["metric"]
    )
    _create_index_if_missing(
        op.f("ix_ragas_evaluation_results_scored_provider"),
        "ragas_evaluation_results",
        ["scored_provider"],
    )
    _create_index_if_missing(
        op.f("ix_ragas_evaluation_results_scored_model"),
        "ragas_evaluation_results",
        ["scored_model"],
    )
    _create_index_if_missing(
        op.f("ix_ragas_evaluation_results_created_at"),
        "ragas_evaluation_results",
        ["created_at"],
    )
    _create_index_if_missing(
        "idx_ragas_provider_model",
        "ragas_evaluation_results",
        ["scored_provider", "scored_model"],
    )


def downgrade() -> None:
    op.drop_index("idx_ragas_provider_model", table_name="ragas_evaluation_results")
    op.drop_index(
        op.f("ix_ragas_evaluation_results_created_at"), table_name="ragas_evaluation_results"
    )
    op.drop_index(
        op.f("ix_ragas_evaluation_results_scored_model"), table_name="ragas_evaluation_results"
    )
    op.drop_index(
        op.f("ix_ragas_evaluation_results_scored_provider"),
        table_name="ragas_evaluation_results",
    )
    op.drop_index(
        op.f("ix_ragas_evaluation_results_metric"), table_name="ragas_evaluation_results"
    )
    op.drop_index(
        op.f("ix_ragas_evaluation_results_investigation_id"),
        table_name="ragas_evaluation_results",
    )
    op.drop_table("ragas_evaluation_results")

    op.drop_index(op.f("ix_llm_call_logs_investigation_id"), table_name="llm_call_logs")
    op.drop_column("llm_call_logs", "investigation_id")

    op.drop_column("investigations", "ground_truth_set_at")
    op.drop_column("investigations", "ground_truth_verdict")
