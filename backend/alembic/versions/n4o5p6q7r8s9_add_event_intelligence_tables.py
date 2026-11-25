"""add phase 7.3 event intelligence and proactive feed tables

Revision ID: n4o5p6q7r8s9
Revises: m3n4o5p6q7r8
Create Date: 2026-11-25 17:48:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = 'n4o5p6q7r8s9'
down_revision: Union[str, None] = 'm3n4o5p6q7r8'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. standard_event_records
    op.create_table(
        'standard_event_records',
        sa.Column('event_id', sa.String(length=64), nullable=False),
        sa.Column('user_id', sa.UUID(), nullable=False),
        sa.Column('device_id', sa.String(length=128), nullable=True),
        sa.Column('event_type', sa.String(length=64), nullable=False),
        sa.Column('event_timestamp', sa.DateTime(timezone=True), nullable=False),
        sa.Column('ingestion_timestamp', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('schema_version', sa.String(length=32), server_default='1.0.0', nullable=False),
        sa.Column('source', sa.String(length=64), server_default='desktop_telemetry', nullable=False),
        sa.Column('payload', postgresql.JSONB(astext_type=sa.Text()).with_variant(sa.Text(), 'sqlite'), nullable=False),
        sa.Column('correlation_id', sa.String(length=64), nullable=True),
        sa.Column('idempotency_key', sa.String(length=128), nullable=True),
        sa.Column('processed', sa.Boolean(), server_default='false', nullable=False),
        sa.Column('rules_matched', sa.Integer(), server_default='0', nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('event_id')
    )
    op.create_index('ix_standard_events_user_time', 'standard_event_records', ['user_id', 'event_timestamp'], unique=False)
    op.create_index('ix_standard_events_type_time', 'standard_event_records', ['event_type', 'event_timestamp'], unique=False)
    op.create_index('ix_standard_events_user_idempotency', 'standard_event_records', ['user_id', 'idempotency_key'], unique=True)
    op.create_index(op.f('ix_standard_event_records_user_id'), 'standard_event_records', ['user_id'], unique=False)
    op.create_index(op.f('ix_standard_event_records_event_type'), 'standard_event_records', ['event_type'], unique=False)

    # 2. dead_letter_events
    op.create_table(
        'dead_letter_events',
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('event_id', sa.String(length=64), nullable=True),
        sa.Column('user_id', sa.UUID(), nullable=True),
        sa.Column('raw_payload', postgresql.JSONB(astext_type=sa.Text()).with_variant(sa.Text(), 'sqlite'), nullable=False),
        sa.Column('error_code', sa.String(length=64), nullable=False),
        sa.Column('error_reason', sa.Text(), nullable=False),
        sa.Column('retry_count', sa.Integer(), server_default='0', nullable=False),
        sa.Column('max_retries', sa.Integer(), server_default='3', nullable=False),
        sa.Column('status', sa.String(length=32), server_default='PENDING', nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('ix_dead_letter_user_created', 'dead_letter_events', ['user_id', 'created_at'], unique=False)
    op.create_index('ix_dead_letter_status', 'dead_letter_events', ['status'], unique=False)

    # 3. proactive_feed_items
    op.create_table(
        'proactive_feed_items',
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('user_id', sa.UUID(), nullable=False),
        sa.Column('event_id', sa.String(length=64), nullable=True),
        sa.Column('detection_type', sa.String(length=64), nullable=False),
        sa.Column('title', sa.String(length=255), nullable=False),
        sa.Column('why_it_matters', sa.Text(), nullable=False),
        sa.Column('related_task_id', sa.UUID(), nullable=True),
        sa.Column('related_context', postgresql.JSONB(astext_type=sa.Text()).with_variant(sa.Text(), 'sqlite'), nullable=False),
        sa.Column('recommended_response', sa.Text(), nullable=False),
        sa.Column('evidence', postgresql.JSONB(astext_type=sa.Text()).with_variant(sa.Text(), 'sqlite'), nullable=False),
        sa.Column('confidence_score', sa.Float(), server_default='0.85', nullable=False),
        sa.Column('uncertainty_lower_bound', sa.Float(), server_default='0.75', nullable=False),
        sa.Column('uncertainty_upper_bound', sa.Float(), server_default='0.95', nullable=False),
        sa.Column('conformal_interval_text', sa.String(length=128), server_default='90% coverage', nullable=False),
        sa.Column('status', sa.String(length=32), server_default='ACTIVE', nullable=False),
        sa.Column('requires_approval', sa.Boolean(), server_default='true', nullable=False),
        sa.Column('suggested_action', postgresql.JSONB(astext_type=sa.Text()).with_variant(sa.Text(), 'sqlite'), nullable=True),
        sa.Column('snoozed_until', sa.DateTime(timezone=True), nullable=True),
        sa.Column('expires_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['related_task_id'], ['tasks.id'], ondelete='SET NULL'),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('ix_proactive_feed_user_status', 'proactive_feed_items', ['user_id', 'status'], unique=False)
    op.create_index('ix_proactive_feed_user_created', 'proactive_feed_items', ['user_id', 'created_at'], unique=False)


def downgrade() -> None:
    op.drop_table('proactive_feed_items')
    op.drop_table('dead_letter_events')
    op.drop_table('standard_event_records')
