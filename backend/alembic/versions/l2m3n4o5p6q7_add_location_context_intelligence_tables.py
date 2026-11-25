"""add phase 5.8 location checkins and context intelligence tables

Revision ID: l2m3n4o5p6q7
Revises: k1l2m3n4o5p6
Create Date: 2026-11-24 22:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = 'l2m3n4o5p6q7'
down_revision: Union[str, None] = 'k1l2m3n4o5p6'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. Add reminder columns to locations table
    op.add_column('locations', sa.Column('reminders_enabled', sa.Boolean(), server_default='true', nullable=False))
    op.add_column('locations', sa.Column('arrival_reminder_enabled', sa.Boolean(), server_default='true', nullable=False))
    op.add_column('locations', sa.Column('departure_reminder_enabled', sa.Boolean(), server_default='true', nullable=False))

    # 2. Create location_checkins table
    op.create_table(
        'location_checkins',
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('user_id', sa.UUID(), nullable=False),
        sa.Column('location_id', sa.UUID(), nullable=True),
        sa.Column('location_name', sa.String(length=120), nullable=False),
        sa.Column('location_type', sa.String(length=32), nullable=False, server_default='OTHER'),
        sa.Column('check_in_type', sa.String(length=32), nullable=False, server_default='MANUAL'),
        sa.Column('device_id', sa.String(length=128), nullable=True),
        sa.Column('occurred_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('notes', sa.Text(), nullable=True),
        sa.Column('payload', postgresql.JSONB(astext_type=sa.Text()).with_variant(sa.Text(), 'sqlite'), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['location_id'], ['locations.id'], ondelete='SET NULL'),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_location_checkins_user_id'), 'location_checkins', ['user_id'], unique=False)
    op.create_index(op.f('ix_location_checkins_location_id'), 'location_checkins', ['location_id'], unique=False)
    op.create_index(op.f('ix_location_checkins_occurred_at'), 'location_checkins', ['occurred_at'], unique=False)

    # 3. Create location_routine_associations table
    op.create_table(
        'location_routine_associations',
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('user_id', sa.UUID(), nullable=False),
        sa.Column('location_id', sa.UUID(), nullable=False),
        sa.Column('task_id', sa.UUID(), nullable=True),
        sa.Column('task_category', sa.String(length=64), nullable=True),
        sa.Column('trigger_type', sa.String(length=32), nullable=False, server_default='ARRIVAL'),
        sa.Column('association_source', sa.String(length=32), nullable=False, server_default='EXPLICIT'),
        sa.Column('confidence_score', sa.Float(), nullable=False, server_default='1.0'),
        sa.Column('support', sa.Float(), nullable=False, server_default='1.0'),
        sa.Column('observation_count', sa.Integer(), nullable=False, server_default='1'),
        sa.Column('is_active', sa.Boolean(), server_default='true', nullable=False),
        sa.Column('last_triggered_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['location_id'], ['locations.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['task_id'], ['tasks.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_location_routine_associations_user_id'), 'location_routine_associations', ['user_id'], unique=False)
    op.create_index(op.f('ix_location_routine_associations_location_id'), 'location_routine_associations', ['location_id'], unique=False)
    op.create_index(op.f('ix_location_routine_associations_task_id'), 'location_routine_associations', ['task_id'], unique=False)


def downgrade() -> None:
    op.drop_index(op.f('ix_location_routine_associations_task_id'), table_name='location_routine_associations')
    op.drop_index(op.f('ix_location_routine_associations_location_id'), table_name='location_routine_associations')
    op.drop_index(op.f('ix_location_routine_associations_user_id'), table_name='location_routine_associations')
    op.drop_table('location_routine_associations')

    op.drop_index(op.f('ix_location_checkins_occurred_at'), table_name='location_checkins')
    op.drop_index(op.f('ix_location_checkins_location_id'), table_name='location_checkins')
    op.drop_index(op.f('ix_location_checkins_user_id'), table_name='location_checkins')
    op.drop_table('location_checkins')

    op.drop_column('locations', 'departure_reminder_enabled')
    op.drop_column('locations', 'arrival_reminder_enabled')
    op.drop_column('locations', 'reminders_enabled')
