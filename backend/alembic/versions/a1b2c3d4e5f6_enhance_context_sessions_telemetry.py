"""enhance context sessions table with automated telemetry fields

Revision ID: a1b2c3d4e5f6
Revises: f6a7b8c9d0e1
Create Date: 2026-11-22 02:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision: str = 'a1b2c3d4e5f6'
down_revision: Union[str, None] = 'f6a7b8c9d0e1'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Add new telemetry-driven columns to context_sessions
    op.add_column('context_sessions', sa.Column('task_id', sa.UUID(), nullable=True))
    op.add_column('context_sessions', sa.Column('status', sa.String(length=32), server_default='COMPLETED', nullable=False))
    op.add_column('context_sessions', sa.Column('primary_application', sa.String(length=255), nullable=True))
    op.add_column('context_sessions', sa.Column('secondary_applications', postgresql.JSONB(astext_type=sa.Text()), server_default='[]', nullable=False))
    op.add_column('context_sessions', sa.Column('application_breakdown', postgresql.JSONB(astext_type=sa.Text()), server_default='{}', nullable=False))
    op.add_column('context_sessions', sa.Column('transition_count', sa.Integer(), server_default='0', nullable=False))
    op.add_column('context_sessions', sa.Column('context_switch_frequency', sa.Float(), server_default='0.0', nullable=False))
    op.add_column('context_sessions', sa.Column('focused_time_seconds', sa.Float(), server_default='0.0', nullable=False))
    op.add_column('context_sessions', sa.Column('interruption_time_seconds', sa.Float(), server_default='0.0', nullable=False))
    op.add_column('context_sessions', sa.Column('idle_time_seconds', sa.Float(), server_default='0.0', nullable=False))
    op.add_column('context_sessions', sa.Column('resume_delay_seconds', sa.Float(), nullable=True))
    op.add_column('context_sessions', sa.Column('task_association_status', sa.String(length=32), server_default='UNKNOWN', nullable=False))
    op.add_column('context_sessions', sa.Column('task_association_confidence', sa.Float(), nullable=True))
    op.add_column('context_sessions', sa.Column('suggested_task_id', sa.UUID(), nullable=True))
    op.add_column('context_sessions', sa.Column('reconstruction_confidence', sa.Float(), server_default='1.0', nullable=False))
    op.add_column('context_sessions', sa.Column('quality_tier', sa.String(length=16), server_default='HIGH', nullable=False))
    op.add_column('context_sessions', sa.Column('quality_details', postgresql.JSONB(astext_type=sa.Text()), server_default='{}', nullable=False))
    op.add_column('context_sessions', sa.Column('timeline', postgresql.JSONB(astext_type=sa.Text()), server_default='[]', nullable=False))
    op.add_column('context_sessions', sa.Column('user_corrected', sa.Boolean(), server_default='false', nullable=False))
    op.add_column('context_sessions', sa.Column('user_correction_notes', sa.Text(), nullable=True))
    op.add_column('context_sessions', sa.Column('last_reconstructed_at', sa.DateTime(timezone=True), nullable=True))

    # Foreign keys
    op.create_foreign_key('fk_context_sessions_task_id', 'context_sessions', 'tasks', ['task_id'], ['id'], ondelete='SET NULL')
    op.create_foreign_key('fk_context_sessions_suggested_task_id', 'context_sessions', 'tasks', ['suggested_task_id'], ['id'], ondelete='SET NULL')

    # Indexes
    op.create_index('ix_context_sessions_task_id', 'context_sessions', ['task_id'])
    op.create_index('ix_context_sessions_primary_app', 'context_sessions', ['primary_application'])
    op.create_index('ix_context_sessions_task_association_status', 'context_sessions', ['task_association_status'])
    op.create_index('ix_context_sessions_status', 'context_sessions', ['status'])
    op.create_index('ix_context_sessions_quality', 'context_sessions', ['quality_tier'])
    op.create_index('ix_context_sessions_user_start', 'context_sessions', ['user_id', 'started_at'])


def downgrade() -> None:
    op.drop_index('ix_context_sessions_user_start', table_name='context_sessions')
    op.drop_index('ix_context_sessions_quality', table_name='context_sessions')
    op.drop_index('ix_context_sessions_status', table_name='context_sessions')
    op.drop_index('ix_context_sessions_task_association_status', table_name='context_sessions')
    op.drop_index('ix_context_sessions_primary_app', table_name='context_sessions')
    op.drop_index('ix_context_sessions_task_id', table_name='context_sessions')

    op.drop_constraint('fk_context_sessions_suggested_task_id', 'context_sessions', type_='foreignkey')
    op.drop_constraint('fk_context_sessions_task_id', 'context_sessions', type_='foreignkey')

    op.drop_column('context_sessions', 'last_reconstructed_at')
    op.drop_column('context_sessions', 'user_correction_notes')
    op.drop_column('context_sessions', 'user_corrected')
    op.drop_column('context_sessions', 'timeline')
    op.drop_column('context_sessions', 'quality_details')
    op.drop_column('context_sessions', 'quality_tier')
    op.drop_column('context_sessions', 'reconstruction_confidence')
    op.drop_column('context_sessions', 'suggested_task_id')
    op.drop_column('context_sessions', 'task_association_confidence')
    op.drop_column('context_sessions', 'task_association_status')
    op.drop_column('context_sessions', 'resume_delay_seconds')
    op.drop_column('context_sessions', 'idle_time_seconds')
    op.drop_column('context_sessions', 'interruption_time_seconds')
    op.drop_column('context_sessions', 'focused_time_seconds')
    op.drop_column('context_sessions', 'context_switch_frequency')
    op.drop_column('context_sessions', 'transition_count')
    op.drop_column('context_sessions', 'application_breakdown')
    op.drop_column('context_sessions', 'secondary_applications')
    op.drop_column('context_sessions', 'primary_application')
    op.drop_column('context_sessions', 'status')
    op.drop_column('context_sessions', 'task_id')
