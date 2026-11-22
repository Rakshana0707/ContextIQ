"""add raw telemetry events table

Establishes the raw_telemetry_events table for high-throughput, idempotent
ingestion of desktop behavioral activity events in ContextIQ Phase 3.4.

Revision ID: e5f6a7b8c9d0
Revises: d4e5f6a7b8c9
Create Date: 2026-11-22 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision: str = 'e5f6a7b8c9d0'
down_revision: Union[str, None] = 'd4e5f6a7b8c9'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'raw_telemetry_events',
        sa.Column('event_id', sa.String(length=64), nullable=False),
        sa.Column('user_id', sa.UUID(), nullable=False),
        sa.Column('device_id', sa.String(length=128), nullable=True),
        sa.Column('event_type', sa.String(length=64), nullable=False),
        sa.Column('event_timestamp', sa.DateTime(timezone=True), nullable=False),
        sa.Column('ingestion_timestamp', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column('source', sa.String(length=64), server_default='desktop_agent_windows', nullable=False),
        sa.Column('schema_version', sa.String(length=32), server_default='1.0.0', nullable=False),
        sa.Column('session_id', sa.UUID(), nullable=True),
        sa.Column('correlation_id', sa.UUID(), nullable=True),
        sa.Column('application_identifier', sa.String(length=255), nullable=True),
        sa.Column('previous_application_identifier', sa.String(length=255), nullable=True),
        sa.Column('current_application_identifier', sa.String(length=255), nullable=True),
        sa.Column('payload', postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('event_id')
    )
    op.create_index('ix_raw_telemetry_events_user_id', 'raw_telemetry_events', ['user_id'])
    op.create_index('ix_raw_telemetry_events_device_id', 'raw_telemetry_events', ['device_id'])
    op.create_index('ix_raw_telemetry_events_event_type', 'raw_telemetry_events', ['event_type'])
    op.create_index('ix_raw_telemetry_events_event_timestamp', 'raw_telemetry_events', ['event_timestamp'])
    op.create_index('ix_raw_telemetry_events_ingestion_timestamp', 'raw_telemetry_events', ['ingestion_timestamp'])
    op.create_index('ix_raw_telemetry_events_app_id', 'raw_telemetry_events', ['application_identifier'])
    op.create_index('ix_raw_telemetry_user_time', 'raw_telemetry_events', ['user_id', 'event_timestamp'])
    op.create_index('ix_raw_telemetry_user_device', 'raw_telemetry_events', ['user_id', 'device_id'])
    op.create_index('ix_raw_telemetry_type_time', 'raw_telemetry_events', ['event_type', 'event_timestamp'])


def downgrade() -> None:
    op.drop_index('ix_raw_telemetry_type_time', table_name='raw_telemetry_events')
    op.drop_index('ix_raw_telemetry_user_device', table_name='raw_telemetry_events')
    op.drop_index('ix_raw_telemetry_user_time', table_name='raw_telemetry_events')
    op.drop_index('ix_raw_telemetry_events_app_id', table_name='raw_telemetry_events')
    op.drop_index('ix_raw_telemetry_events_ingestion_timestamp', table_name='raw_telemetry_events')
    op.drop_index('ix_raw_telemetry_events_event_timestamp', table_name='raw_telemetry_events')
    op.drop_index('ix_raw_telemetry_events_event_type', table_name='raw_telemetry_events')
    op.drop_index('ix_raw_telemetry_events_device_id', table_name='raw_telemetry_events')
    op.drop_index('ix_raw_telemetry_events_user_id', table_name='raw_telemetry_events')
    op.drop_table('raw_telemetry_events')
