"""add detected interruptions and feedback tables

Revision ID: f6a7b8c9d0e1
Revises: e5f6a7b8c9d0
Create Date: 2026-11-22 01:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision: str = 'f6a7b8c9d0e1'
down_revision: Union[str, None] = 'e5f6a7b8c9d0'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'detected_interruptions',
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('user_id', sa.UUID(), nullable=False),
        sa.Column('source_event_ids', postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column('interruption_type', sa.String(length=64), nullable=False),
        sa.Column('severity', sa.String(length=32), nullable=False),
        sa.Column('start_timestamp', sa.DateTime(timezone=True), nullable=False),
        sa.Column('end_timestamp', sa.DateTime(timezone=True), nullable=True),
        sa.Column('duration_seconds', sa.Float(), nullable=True),
        sa.Column('confidence', sa.Float(), nullable=False, server_default='1.0'),
        sa.Column('detection_method', sa.String(length=64), nullable=False, server_default='RULE_BASED_HEURISTIC'),
        sa.Column('detection_version', sa.String(length=32), nullable=False, server_default='1.0.0'),
        sa.Column('explanation', sa.Text(), nullable=False),
        sa.Column('primary_app', sa.String(length=255), nullable=True),
        sa.Column('interrupting_app', sa.String(length=255), nullable=True),
        sa.Column('resumption_lag_seconds', sa.Float(), nullable=True),
        sa.Column('metadata_payload', postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('ix_detected_interruptions_user_id', 'detected_interruptions', ['user_id'])
    op.create_index('ix_detected_interruptions_start_timestamp', 'detected_interruptions', ['start_timestamp'])
    op.create_index('ix_detected_interruptions_interruption_type', 'detected_interruptions', ['interruption_type'])
    op.create_index('ix_detected_interruptions_severity', 'detected_interruptions', ['severity'])
    op.create_index('ix_detected_interruptions_user_time', 'detected_interruptions', ['user_id', 'start_timestamp'])
    op.create_index('ix_detected_interruptions_type_time', 'detected_interruptions', ['interruption_type', 'start_timestamp'])

    op.create_table(
        'detected_interruption_feedback',
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('interruption_id', sa.UUID(), nullable=False),
        sa.Column('user_id', sa.UUID(), nullable=False),
        sa.Column('feedback_classification', sa.String(length=64), nullable=False),
        sa.Column('notes', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(['interruption_id'], ['detected_interruptions.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('ix_interruption_feedback_user', 'detected_interruption_feedback', ['user_id'])
    op.create_index('ix_interruption_feedback_interruption', 'detected_interruption_feedback', ['interruption_id'])
    op.create_index('ix_interruption_feedback_classification', 'detected_interruption_feedback', ['feedback_classification'])


def downgrade() -> None:
    op.drop_index('ix_interruption_feedback_classification', table_name='detected_interruption_feedback')
    op.drop_index('ix_interruption_feedback_interruption', table_name='detected_interruption_feedback')
    op.drop_index('ix_interruption_feedback_user', table_name='detected_interruption_feedback')
    op.drop_table('detected_interruption_feedback')

    op.drop_index('ix_detected_interruptions_type_time', table_name='detected_interruptions')
    op.drop_index('ix_detected_interruptions_user_time', table_name='detected_interruptions')
    op.drop_index('ix_detected_interruptions_severity', table_name='detected_interruptions')
    op.drop_index('ix_detected_interruptions_interruption_type', table_name='detected_interruptions')
    op.drop_index('ix_detected_interruptions_start_timestamp', table_name='detected_interruptions')
    op.drop_index('ix_detected_interruptions_user_id', table_name='detected_interruptions')
    op.drop_table('detected_interruptions')
