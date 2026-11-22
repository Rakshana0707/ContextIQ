"""add telemetry consent and privacy tables

Establishes the auditable telemetry_consents, user_privacy_settings,
and user_app_exclusions tables for ContextIQ Phase 3.2.

Revision ID: d4e5f6a7b8c9
Revises: 9f82d6a11b3c
Create Date: 2026-11-21 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision: str = 'd4e5f6a7b8c9'
down_revision: Union[str, None] = '9f82d6a11b3c'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # --- native Postgres enum type ---
    op.execute("CREATE TYPE consent_status AS ENUM ('GRANTED', 'REVOKED', 'PAUSED', 'EXPIRED')")

    # --- telemetry_consents table ---
    op.create_table(
        'telemetry_consents',
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('user_id', sa.UUID(), nullable=False),
        sa.Column('consent_version', sa.String(length=32), nullable=False, server_default='1.0.0'),
        sa.Column('enabled_categories', postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column('granted_timestamp', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column('updated_timestamp', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column('revoked_timestamp', sa.DateTime(timezone=True), nullable=True),
        sa.Column('device_id', sa.String(length=128), nullable=True),
        sa.Column('consent_status', sa.Enum('GRANTED', 'REVOKED', 'PAUSED', 'EXPIRED', name='consent_status'), nullable=False),
        sa.Column('ip_hash', sa.String(length=64), nullable=True),
        sa.Column('user_agent', sa.String(length=256), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_telemetry_consents_user_status', 'telemetry_consents', ['user_id', 'consent_status'], unique=False)
    op.create_index('ix_telemetry_consents_user_granted', 'telemetry_consents', ['user_id', 'granted_timestamp'], unique=False)
    op.create_index(op.f('ix_telemetry_consents_user_id'), 'telemetry_consents', ['user_id'], unique=False)
    op.create_index(op.f('ix_telemetry_consents_device_id'), 'telemetry_consents', ['device_id'], unique=False)

    # --- user_privacy_settings table ---
    op.create_table(
        'user_privacy_settings',
        sa.Column('user_id', sa.UUID(), nullable=False),
        sa.Column('is_paused', sa.Boolean(), nullable=False, server_default=sa.text('false')),
        sa.Column('paused_until', sa.DateTime(timezone=True), nullable=True),
        sa.Column('raw_event_retention_days', sa.Integer(), nullable=False, server_default=sa.text('30')),
        sa.Column('aggregated_metric_retention_days', sa.Integer(), nullable=False, server_default=sa.text('365')),
        sa.Column('allow_anonymized_research', sa.Boolean(), nullable=False, server_default=sa.text('false')),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('user_id'),
    )

    # --- user_app_exclusions table ---
    op.create_table(
        'user_app_exclusions',
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('user_id', sa.UUID(), nullable=False),
        sa.Column('application_identifier', sa.String(length=128), nullable=False),
        sa.Column('description', sa.String(length=256), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('user_id', 'application_identifier', name='uq_user_app_exclusion'),
    )
    op.create_index('ix_user_app_exclusions_user_app', 'user_app_exclusions', ['user_id', 'application_identifier'], unique=False)
    op.create_index(op.f('ix_user_app_exclusions_user_id'), 'user_app_exclusions', ['user_id'], unique=False)


def downgrade() -> None:
    # --- drop user_app_exclusions ---
    op.drop_index(op.f('ix_user_app_exclusions_user_id'), table_name='user_app_exclusions')
    op.drop_index('ix_user_app_exclusions_user_app', table_name='user_app_exclusions')
    op.drop_table('user_app_exclusions')

    # --- drop user_privacy_settings ---
    op.drop_table('user_privacy_settings')

    # --- drop telemetry_consents ---
    op.drop_index(op.f('ix_telemetry_consents_device_id'), table_name='telemetry_consents')
    op.drop_index(op.f('ix_telemetry_consents_user_id'), table_name='telemetry_consents')
    op.drop_index('ix_telemetry_consents_user_granted', table_name='telemetry_consents')
    op.drop_index('ix_telemetry_consents_user_status', table_name='telemetry_consents')
    op.drop_table('telemetry_consents')

    # --- drop enum type ---
    op.execute("DROP TYPE consent_status")
