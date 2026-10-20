"""audit append then seal

Revision ID: e30b8d69938f
Revises: cf66b06047d9
Create Date: 2026-10-20 12:26:17.896437

The ledger is now written in two steps (see app/services/audit.py): the DB assigns `seq`,
and a serialised sealer fills `chain_index`, `prev_hash` and `hash` after commit.
Existing entries were chained by `seq`, so `chain_index = seq` keeps their hashes valid.
"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = 'e30b8d69938f'
down_revision: str | None = 'cf66b06047d9'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    with op.batch_alter_table('audit_ledger', schema=None) as batch_op:
        batch_op.add_column(sa.Column('chain_index', sa.Integer(), nullable=True))
        batch_op.alter_column('seq', existing_type=sa.Integer(), autoincrement=True)
        batch_op.alter_column('prev_hash', existing_type=sa.String(length=64), nullable=True)
        batch_op.alter_column('hash', existing_type=sa.String(length=64), nullable=True)
    op.execute("UPDATE audit_ledger SET chain_index = seq")
    with op.batch_alter_table('audit_ledger', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_audit_ledger_chain_index'), ['chain_index'], unique=True)


def downgrade() -> None:
    op.execute("DELETE FROM audit_ledger WHERE chain_index IS NULL")
    with op.batch_alter_table('audit_ledger', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_audit_ledger_chain_index'))
        batch_op.alter_column('hash', existing_type=sa.String(length=64), nullable=False)
        batch_op.alter_column('prev_hash', existing_type=sa.String(length=64), nullable=False)
        batch_op.drop_column('chain_index')
