"""add phase 5.3 external calendar events table

Revision ID: i9j0k1l2m3n4
Revises: h8i9j0k1l2m3
Create Date: 2026-11-24 16:30:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = 'i9j0k1l2m3n4'
down_revision: Union[str, None] = 'h8i9j0k1l2m3'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'external_calendar_events',
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('integration_id', sa.UUID(), nullable=False),
        sa.Column('user_id', sa.UUID(), nullable=False),
        sa.Column('calendar_id', sa.String(length=255), nullable=False, server_default='primary'),
        sa.Column('external_event_id', sa.String(length=255), nullable=False),
        sa.Column('title', sa.String(length=512), nullable=False),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('location_name', sa.String(length=255), nullable=True),
        sa.Column('start_time', sa.DateTime(timezone=True), nullable=False),
        sa.Column('end_time', sa.DateTime(timezone=True), nullable=False),
        sa.Column('timezone', sa.String(length=64), nullable=False, server_default='UTC'),
        sa.Column('is_all_day', sa.Boolean(), nullable=False, server_default=sa.text('false')),
        sa.Column('status', sa.String(length=32), nullable=False, server_default='CONFIRMED'),
        sa.Column('transparency', sa.String(length=32), nullable=False, server_default='OPAQUE'),
        sa.Column('visibility', sa.String(length=32), nullable=False, server_default='default'),
        sa.Column('is_private', sa.Boolean(), nullable=False, server_default=sa.text('false')),
        sa.Column('is_recurring', sa.Boolean(), nullable=False, server_default=sa.text('false')),
        sa.Column('recurring_event_id', sa.String(length=255), nullable=True),
        sa.Column('recurrence_rule', sa.Text(), nullable=True),
        sa.Column('original_start_time', sa.DateTime(timezone=True), nullable=True),
        sa.Column('is_organizer', sa.Boolean(), nullable=False, server_default=sa.text('true')),
        sa.Column('organizer_email', sa.String(length=320), nullable=True),
        sa.Column('attendees_count', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('etag', sa.String(length=255), nullable=True),
        sa.Column('html_link', sa.Text(), nullable=True),
        sa.Column('external_updated_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('is_contextiq_managed', sa.Boolean(), nullable=False, server_default=sa.text('false')),
        sa.Column('linked_task_id', sa.UUID(), nullable=True),
        sa.Column('last_synced_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.text('now()')),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.text('now()')),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.text('now()')),
        sa.ForeignKeyConstraint(['integration_id'], ['calendar_integrations.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['linked_task_id'], ['tasks.id'], ondelete='SET NULL'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('integration_id', 'external_event_id', name='uq_integration_external_event_id'),
    )
    op.create_index(op.f('ix_external_calendar_events_user_time'), 'external_calendar_events', ['user_id', 'start_time', 'end_time'], unique=False)
    op.create_index(op.f('ix_external_calendar_events_integration'), 'external_calendar_events', ['integration_id'], unique=False)
    op.create_index(op.f('ix_external_calendar_events_calendar'), 'external_calendar_events', ['calendar_id'], unique=False)
    op.create_index(op.f('ix_external_calendar_events_transparency'), 'external_calendar_events', ['user_id', 'transparency'], unique=False)
    op.create_index(op.f('ix_external_calendar_events_recurring'), 'external_calendar_events', ['recurring_event_id'], unique=False)


def downgrade() -> None:
    op.drop_table('external_calendar_events')
