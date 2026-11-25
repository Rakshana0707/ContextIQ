"""add phase 5.5 schedule proposals table

Revision ID: j0k1l2m3n4o5
Revises: i9j0k1l2m3n4
Create Date: 2026-11-24 17:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = 'j0k1l2m3n4o5'
down_revision: Union[str, None] = 'i9j0k1l2m3n4'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'schedule_proposals',
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('user_id', sa.UUID(), nullable=False),
        sa.Column('status', sa.String(length=32), nullable=False, server_default='DRAFT'),
        sa.Column('horizon_start', sa.DateTime(timezone=True), nullable=False),
        sa.Column('horizon_end', sa.DateTime(timezone=True), nullable=False),
        sa.Column('scheduled_items', postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default=sa.text("'[]'::jsonb")),
        sa.Column('unscheduled_items', postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default=sa.text("'[]'::jsonb")),
        sa.Column('metadata_json', postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.text('now()')),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.text('now()')),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_schedule_proposals_user_status', 'schedule_proposals', ['user_id', 'status'])
    op.create_index('ix_schedule_proposals_horizon', 'schedule_proposals', ['user_id', 'horizon_start', 'horizon_end'])


def downgrade() -> None:
    op.drop_index('ix_schedule_proposals_horizon', table_name='schedule_proposals')
    op.drop_index('ix_schedule_proposals_user_status', table_name='schedule_proposals')
    op.drop_table('schedule_proposals')
