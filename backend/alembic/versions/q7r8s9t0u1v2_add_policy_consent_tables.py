"""add phase 7.6 policy consent and audit tables

Revision ID: q7r8s9t0u1v2
Revises: p6q7r8s9t0u1
Create Date: 2026-11-25 21:15:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = 'q7r8s9t0u1v2'
down_revision: Union[str, None] = 'p6q7r8s9t0u1'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'user_policy_consents',
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('user_id', sa.UUID(), nullable=False),
        sa.Column('scope', sa.String(length=64), nullable=False),
        sa.Column('consent_status', sa.String(length=32), server_default='GRANTED', nullable=False),
        sa.Column('consent_version', sa.String(length=32), server_default='1.0.0', nullable=False),
        sa.Column('granted_timestamp', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('revoked_timestamp', sa.DateTime(timezone=True), nullable=True),
        sa.Column('source', sa.String(length=32), server_default='USER_EXPLICIT', nullable=False),
        sa.Column('device_id', sa.String(length=128), nullable=True),
        sa.Column('integration_id', sa.String(length=128), nullable=True),
        sa.Column('revocation_reason', sa.Text(), nullable=True),
        sa.Column('policy_metadata', postgresql.JSONB(astext_type=sa.Text()).with_variant(sa.Text(), 'sqlite'), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('ix_policy_consents_user_scope', 'user_policy_consents', ['user_id', 'scope'], unique=False)
    op.create_index('ix_policy_consents_user_status', 'user_policy_consents', ['user_id', 'consent_status'], unique=False)
    op.create_index(op.f('ix_user_policy_consents_user_id'), 'user_policy_consents', ['user_id'], unique=False)

    op.create_table(
        'policy_audit_trails',
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('user_id', sa.UUID(), nullable=False),
        sa.Column('action_identifier', sa.String(length=128), nullable=False),
        sa.Column('scope_checked', sa.String(length=64), nullable=True),
        sa.Column('decision', sa.String(length=32), nullable=False),
        sa.Column('risk_tier', sa.String(length=64), nullable=False),
        sa.Column('reason', sa.Text(), nullable=True),
        sa.Column('context_snapshot', postgresql.JSONB(astext_type=sa.Text()).with_variant(sa.Text(), 'sqlite'), nullable=True),
        sa.Column('evaluated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('ix_policy_audit_user_time', 'policy_audit_trails', ['user_id', 'evaluated_at'], unique=False)
    op.create_index('ix_policy_audit_decision', 'policy_audit_trails', ['decision'], unique=False)
    op.create_index(op.f('ix_policy_audit_trails_user_id'), 'policy_audit_trails', ['user_id'], unique=False)


def downgrade() -> None:
    op.drop_table('policy_audit_trails')
    op.drop_table('user_policy_consents')
