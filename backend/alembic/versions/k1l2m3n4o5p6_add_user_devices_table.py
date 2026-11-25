"""add phase 5.7 user devices table

Revision ID: k1l2m3n4o5p6
Revises: j0k1l2m3n4o5
Create Date: 2026-11-24 17:30:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = 'k1l2m3n4o5p6'
down_revision: Union[str, None] = 'j0k1l2m3n4o5'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'user_devices',
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('user_id', sa.UUID(), nullable=False),
        sa.Column('device_id', sa.String(length=128), nullable=False),
        sa.Column('device_type', sa.String(length=32), nullable=False, server_default='DESKTOP'),
        sa.Column('platform', sa.String(length=32), nullable=False, server_default='WINDOWS'),
        sa.Column('device_name', sa.String(length=255), nullable=False, server_default='Primary Device'),
        sa.Column('application_version', sa.String(length=64), nullable=False, server_default='1.0.0'),
        sa.Column('registration_timestamp', sa.DateTime(timezone=True), nullable=False, server_default=sa.text('now()')),
        sa.Column('last_seen_timestamp', sa.DateTime(timezone=True), nullable=False, server_default=sa.text('now()')),
        sa.Column('connection_status', sa.String(length=32), nullable=False, server_default='ONLINE'),
        sa.Column('synchronization_status', sa.String(length=32), nullable=False, server_default='SYNCED'),
        sa.Column('device_metadata', postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column('is_active', sa.Boolean(), nullable=False, server_default='true'),
        sa.Column('revoked_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.text('now()')),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.text('now()')),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('user_id', 'device_id', name='uq_user_device_id'),
    )
    op.create_index('ix_user_devices_user_status', 'user_devices', ['user_id', 'connection_status'])
    op.create_index('ix_user_devices_device_id', 'user_devices', ['device_id'])
    op.create_index('ix_user_devices_last_seen', 'user_devices', ['last_seen_timestamp'])


def downgrade() -> None:
    op.drop_index('ix_user_devices_last_seen', table_name='user_devices')
    op.drop_index('ix_user_devices_device_id', table_name='user_devices')
    op.drop_index('ix_user_devices_user_status', table_name='user_devices')
    op.drop_table('user_devices')
