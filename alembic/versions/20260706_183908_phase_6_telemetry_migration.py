"""Phase 6: Telemetry Migration

Revision ID: phase_6_telemetry_migration
Revises: acbb55eaa237
Create Date: 2026-07-06 18:39:08.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'phase_6_telemetry_migration'
down_revision = 'acbb55eaa237'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # offline_queue
    op.create_table('offline_queue',
        sa.Column('id', sa.String(length=36), nullable=False),
        sa.Column('institution_id', sa.String(length=36), nullable=False),
        sa.Column('operation_type', sa.String(length=50), nullable=False),
        sa.Column('payload', sa.JSON(), nullable=False),
        sa.Column('status', sa.String(length=20), nullable=False),
        sa.Column('node_name', sa.String(length=100), nullable=True),
        sa.Column('priority', sa.Integer(), nullable=True),
        sa.Column('retry_count', sa.Integer(), nullable=True),
        sa.Column('max_retries', sa.Integer(), nullable=True),
        sa.Column('next_retry_at', sa.DateTime(), nullable=True),
        sa.Column('error_message', sa.Text(), nullable=True),
        sa.Column('conflict_info', sa.JSON(), nullable=True),
        sa.Column('checksum', sa.String(length=255), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.Column('updated_at', sa.DateTime(), nullable=True),
        sa.Column('synced_at', sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(['institution_id'], ['institutions.id'], ),
        sa.PrimaryKeyConstraint('id')
    )
    with op.batch_alter_table('offline_queue', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_offline_queue_institution_id'), ['institution_id'], unique=False)

    # network_presence
    op.create_table('network_presence',
        sa.Column('id', sa.String(length=36), nullable=False),
        sa.Column('user_id', sa.String(length=36), nullable=False),
        sa.Column('institution_id', sa.String(length=36), nullable=False),
        sa.Column('ip_address', sa.String(length=255), nullable=True),
        sa.Column('user_agent', sa.Text(), nullable=True),
        sa.Column('browser', sa.String(length=100), nullable=True),
        sa.Column('os', sa.String(length=100), nullable=True),
        sa.Column('device_type', sa.String(length=100), nullable=True),
        sa.Column('login_time', sa.DateTime(), nullable=True),
        sa.Column('last_activity_time', sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(['institution_id'], ['institutions.id'], ),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ),
        sa.PrimaryKeyConstraint('id')
    )
    with op.batch_alter_table('network_presence', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_network_presence_institution_id'), ['institution_id'], unique=False)
        batch_op.create_index(batch_op.f('ix_network_presence_user_id'), ['user_id'], unique=False)

    # activity_logs
    op.create_table('activity_logs',
        sa.Column('id', sa.String(length=36), nullable=False),
        sa.Column('institution_id', sa.String(length=36), nullable=False),
        sa.Column('user_id', sa.String(length=36), nullable=True),
        sa.Column('type', sa.String(length=50), nullable=False),
        sa.Column('message', sa.Text(), nullable=False),
        sa.Column('faculty', sa.String(length=255), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(['institution_id'], ['institutions.id'], ),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ),
        sa.PrimaryKeyConstraint('id')
    )
    with op.batch_alter_table('activity_logs', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_activity_logs_institution_id'), ['institution_id'], unique=False)
        batch_op.create_index(batch_op.f('ix_activity_logs_user_id'), ['user_id'], unique=False)

    # security_logs
    op.create_table('security_logs',
        sa.Column('id', sa.String(length=36), nullable=False),
        sa.Column('institution_id', sa.String(length=36), nullable=False),
        sa.Column('user_id', sa.String(length=36), nullable=True),
        sa.Column('event_type', sa.String(length=50), nullable=False),
        sa.Column('severity', sa.String(length=50), nullable=False),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('ip_address', sa.String(length=255), nullable=True),
        sa.Column('is_resolved', sa.Boolean(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(['institution_id'], ['institutions.id'], ),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ),
        sa.PrimaryKeyConstraint('id')
    )
    with op.batch_alter_table('security_logs', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_security_logs_institution_id'), ['institution_id'], unique=False)
        batch_op.create_index(batch_op.f('ix_security_logs_user_id'), ['user_id'], unique=False)


def downgrade() -> None:
    with op.batch_alter_table('security_logs', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_security_logs_user_id'))
        batch_op.drop_index(batch_op.f('ix_security_logs_institution_id'))
    op.drop_table('security_logs')

    with op.batch_alter_table('activity_logs', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_activity_logs_user_id'))
        batch_op.drop_index(batch_op.f('ix_activity_logs_institution_id'))
    op.drop_table('activity_logs')

    with op.batch_alter_table('network_presence', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_network_presence_user_id'))
        batch_op.drop_index(batch_op.f('ix_network_presence_institution_id'))
    op.drop_table('network_presence')

    with op.batch_alter_table('offline_queue', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_offline_queue_institution_id'))
    op.drop_table('offline_queue')
