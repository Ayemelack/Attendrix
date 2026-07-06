"""phase_5_attendance_migration

Revision ID: acbb55eaa237
Revises: 476218e33db8
Create Date: 2026-07-06 16:07:43.075308

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'acbb55eaa237'
down_revision: Union[str, Sequence[str], None] = '476218e33db8'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Drop existing attendance tables as they were previously unused (data in Firebase)
    op.drop_table('attendance_records')
    op.drop_table('attendance_sessions')

    # Recreate attendance_sessions
    op.create_table(
        'attendance_sessions',
        sa.Column('id', sa.String(length=36), primary_key=True),
        sa.Column('session_code', sa.String(length=255), nullable=False),
        sa.Column('qr_payload', sa.Text(), nullable=True),
        sa.Column('qr_hash', sa.String(length=255), nullable=True),
        sa.Column('course_id', sa.String(length=36), sa.ForeignKey('courses.id')),
        sa.Column('institution_id', sa.String(length=36), sa.ForeignKey('institutions.id')),
        sa.Column('lecturer_id', sa.String(length=36), sa.ForeignKey('users.id')),
        sa.Column('start_time', sa.DateTime(), nullable=True),
        sa.Column('end_time', sa.DateTime(), nullable=True),
        sa.Column('status', sa.Enum('ACTIVE', 'CLOSED', 'CANCELLED', name='sessionstatus'), nullable=True),
        sa.Column('is_active', sa.Boolean(), nullable=True),
        sa.Column('location_data', sa.JSON(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=True)
    )
    op.create_index('ix_session_course', 'attendance_sessions', ['course_id'])
    op.create_index('ix_session_institution', 'attendance_sessions', ['institution_id'])
    op.create_index('ix_session_code', 'attendance_sessions', ['session_code'], unique=True)

    # Recreate attendance_records
    op.create_table(
        'attendance_records',
        sa.Column('id', sa.String(length=36), primary_key=True),
        sa.Column('session_id', sa.String(length=36), sa.ForeignKey('attendance_sessions.id')),
        sa.Column('student_id', sa.String(length=36), sa.ForeignKey('users.id')),
        sa.Column('institution_id', sa.String(length=36), sa.ForeignKey('institutions.id')),
        sa.Column('status', sa.Enum('PRESENT', 'LATE', 'ABSENT', name='attendancestatus'), nullable=True),
        sa.Column('marked_at', sa.DateTime(), nullable=True),
        sa.Column('device_id', sa.String(length=255), nullable=True),
        sa.Column('ip_address', sa.String(length=255), nullable=True),
        sa.Column('face_verified', sa.Boolean(), nullable=True),
        sa.Column('biometric_verified', sa.Boolean(), nullable=True),
        sa.Column('device_fingerprint', sa.String(length=255), nullable=True),
        sa.Column('network_ssid', sa.String(length=255), nullable=True),
        sa.Column('geo_hash', sa.String(length=255), nullable=True),
        sa.UniqueConstraint('session_id', 'student_id', name='uq_session_student')
    )
    op.create_index('ix_record_session', 'attendance_records', ['session_id'])
    op.create_index('ix_record_student', 'attendance_records', ['student_id'])
    op.create_index('ix_record_institution', 'attendance_records', ['institution_id'])

    # Create attendance_verification_logs
    op.create_table(
        'attendance_verification_logs',
        sa.Column('id', sa.String(length=36), primary_key=True),
        sa.Column('attendance_record_id', sa.String(length=36), sa.ForeignKey('attendance_records.id')),
        sa.Column('method', sa.String(length=50), nullable=True),
        sa.Column('score', sa.Float(), nullable=True),
        sa.Column('device_id', sa.String(length=255), nullable=True),
        sa.Column('ip_address', sa.String(length=255), nullable=True),
        sa.Column('raw_payload', sa.JSON(), nullable=True),
        sa.Column('timestamp', sa.DateTime(), nullable=True)
    )

def downgrade() -> None:
    pass
