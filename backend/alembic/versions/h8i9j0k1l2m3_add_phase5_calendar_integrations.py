"""add phase 5 calendar integration tables

Revision ID: h8i9j0k1l2m3
Revises: g7h8i9j0k1l2
Create Date: 2026-11-24 16:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = 'h8i9j0k1l2m3'
down_revision: Union[str, None] = 'g7h8i9j0k1l2'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. calendar_integrations
    op.create_table(
        'calendar_integrations',
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('user_id', sa.UUID(), nullable=False),
        sa.Column('provider', sa.String(length=64), nullable=False),
        sa.Column('provider_account_id', sa.String(length=255), nullable=True),
        sa.Column('provider_email', sa.String(length=320), nullable=True),
        sa.Column('connection_status', sa.String(length=32), nullable=False, server_default='CONNECTED'),
        sa.Column('granted_scopes', postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default='[]'),
        sa.Column('is_active', sa.Boolean(), nullable=False, server_default=sa.text('true')),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.text('now()')),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.text('now()')),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('user_id', 'provider', name='uq_user_calendar_provider'),
    )
    op.create_index(op.f('ix_calendar_integrations_user_id'), 'calendar_integrations', ['user_id'], unique=False)
    op.create_index(op.f('ix_calendar_integrations_provider'), 'calendar_integrations', ['provider'], unique=False)
    op.create_index(op.f('ix_calendar_integrations_status'), 'calendar_integrations', ['connection_status'], unique=False)

    # 2. calendar_credentials
    op.create_table(
        'calendar_credentials',
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('integration_id', sa.UUID(), nullable=False),
        sa.Column('encrypted_access_token', sa.LargeBinary(), nullable=False),
        sa.Column('encrypted_refresh_token', sa.LargeBinary(), nullable=True),
        sa.Column('expiration_timestamp', sa.DateTime(timezone=True), nullable=False),
        sa.Column('credential_version', sa.Integer(), nullable=False, server_default='1'),
        sa.Column('token_type', sa.String(length=32), nullable=False, server_default='Bearer'),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.text('now()')),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.text('now()')),
        sa.ForeignKeyConstraint(['integration_id'], ['calendar_integrations.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('integration_id', name='uq_credential_integration'),
    )
    op.create_index(op.f('ix_calendar_credentials_integration_id'), 'calendar_credentials', ['integration_id'], unique=True)

    # 3. calendar_sync_states
    op.create_table(
        'calendar_sync_states',
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('integration_id', sa.UUID(), nullable=False),
        sa.Column('calendar_id', sa.String(length=255), nullable=False, server_default='primary'),
        sa.Column('sync_token', sa.Text(), nullable=True),
        sa.Column('last_sync_timestamp', sa.DateTime(timezone=True), nullable=True),
        sa.Column('sync_status', sa.String(length=32), nullable=False, server_default='INITIALIZING'),
        sa.Column('error_message', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.text('now()')),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.text('now()')),
        sa.ForeignKeyConstraint(['integration_id'], ['calendar_integrations.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('integration_id', 'calendar_id', name='uq_integration_calendar_sync'),
    )
    op.create_index(op.f('ix_calendar_sync_states_integration'), 'calendar_sync_states', ['integration_id'], unique=False)
    op.create_index(op.f('ix_calendar_sync_states_status'), 'calendar_sync_states', ['sync_status'], unique=False)


def downgrade() -> None:
    op.drop_table('calendar_sync_states')
    op.drop_table('calendar_credentials')
    op.drop_table('calendar_integrations')
