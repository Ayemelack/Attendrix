"""Phase 7: Add revoked, revoked_at, expires_at to vouchers

Revision ID: phase_7_voucher_columns
Revises: phase_6_telemetry_migration
Create Date: 2026-07-06 19:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'phase_7_voucher_columns'
down_revision = 'phase_6_telemetry_migration'
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table('vouchers', schema=None) as batch_op:
        batch_op.add_column(sa.Column('expires_at', sa.DateTime(), nullable=True))
        batch_op.add_column(sa.Column('revoked', sa.Boolean(), default=False))
        batch_op.add_column(sa.Column('revoked_at', sa.DateTime(), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table('vouchers', schema=None) as batch_op:
        batch_op.drop_column('revoked_at')
        batch_op.drop_column('revoked')
        batch_op.drop_column('expires_at')
