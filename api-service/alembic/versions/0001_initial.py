from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "0001_initial"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "wallets",
        sa.Column("telegram_id", sa.String(length=64), primary_key=True),
        sa.Column("username", sa.String(length=64), nullable=True),
        sa.Column("first_name", sa.String(length=64), nullable=True),
        sa.Column("last_name", sa.String(length=64), nullable=True),
        sa.Column("bnb_address", sa.String(length=64), nullable=True),
        sa.Column("slh_address", sa.String(length=64), nullable=True),
        sa.Column("slh_ton_address", sa.String(length=128), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_wallets_telegram_id", "wallets", ["telegram_id"], unique=False)
    op.create_index("ix_wallets_username", "wallets", ["username"], unique=False)
    op.create_index("ix_wallets_bnb_address", "wallets", ["bnb_address"], unique=False)
    op.create_index("ix_wallets_slh_address", "wallets", ["slh_address"], unique=False)
    op.create_index("ix_wallets_slh_ton_address", "wallets", ["slh_ton_address"], unique=False)

    op.create_table(
        "internal_transfers",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("from_telegram_id", sa.String(length=64), nullable=False),
        sa.Column("to_telegram_id", sa.String(length=64), nullable=False),
        sa.Column("amount_slh", sa.Numeric(precision=24, scale=8), nullable=False),
        sa.Column("memo", sa.String(length=255), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["from_telegram_id"], ["wallets.telegram_id"]),
        sa.ForeignKeyConstraint(["to_telegram_id"], ["wallets.telegram_id"]),
    )
    op.create_index(
        "ix_internal_transfers_from",
        "internal_transfers",
        ["from_telegram_id"],
        unique=False,
    )
    op.create_index(
        "ix_internal_transfers_to",
        "internal_transfers",
        ["to_telegram_id"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_internal_transfers_to", table_name="internal_transfers")
    op.drop_index("ix_internal_transfers_from", table_name="internal_transfers")
    op.drop_table("internal_transfers")

    op.drop_index("ix_wallets_slh_ton_address", table_name="wallets")
    op.drop_index("ix_wallets_slh_address", table_name="wallets")
    op.drop_index("ix_wallets_bnb_address", table_name="wallets")
    op.drop_index("ix_wallets_username", table_name="wallets")
    op.drop_index("ix_wallets_telegram_id", table_name="wallets")
    op.drop_table("wallets")
