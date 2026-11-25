"""add phase 7.7 safety audit rollback and emergency tables

Revision ID: r8s9t0u1v2w3
Revises: q7r8s9t0u1v2
Create Date: 2026-11-25 21:32:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = 'r8s9t0u1v2w3'
down_revision: Union[str, None] = 'q7r8s9t0u1v2'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. workflow_audit_events
    op.create_table(
        'workflow_audit_events',
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('user_id', sa.UUID(), nullable=False),
        sa.Column('plan_id', sa.UUID(), nullable=True),
        sa.Column('workflow_version', sa.Integer(), server_default='1', nullable=False),
        sa.Column('event_type', sa.String(length=64), nullable=False),
        sa.Column('action_identifier', sa.String(length=128), nullable=True),
        sa.Column('step_key', sa.String(length=64), nullable=True),
        sa.Column('execution_timestamp', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('policy_decision', sa.String(length=32), nullable=True),
        sa.Column('approval_reference', sa.String(length=128), nullable=True),
        sa.Column('result_status', sa.String(length=32), nullable=True),
        sa.Column('error_details', postgresql.JSONB(astext_type=sa.Text()).with_variant(sa.Text(), 'sqlite'), nullable=True),
        sa.Column('correlation_id', sa.String(length=128), nullable=True),
        sa.Column('sanitized_payload', postgresql.JSONB(astext_type=sa.Text()).with_variant(sa.Text(), 'sqlite'), nullable=True),
        sa.ForeignKeyConstraint(['plan_id'], ['workflow_execution_plans.id'], ondelete='SET NULL'),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('ix_wf_audit_user_time', 'workflow_audit_events', ['user_id', 'execution_timestamp'], unique=False)
    op.create_index('ix_wf_audit_plan_time', 'workflow_audit_events', ['plan_id', 'execution_timestamp'], unique=False)
    op.create_index('ix_wf_audit_event_type', 'workflow_audit_events', ['event_type'], unique=False)
    op.create_index(op.f('ix_workflow_audit_events_plan_id'), 'workflow_audit_events', ['plan_id'], unique=False)
    op.create_index(op.f('ix_workflow_audit_events_user_id'), 'workflow_audit_events', ['user_id'], unique=False)

    # 2. workflow_approval_records
    op.create_table(
        'workflow_approval_records',
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('plan_id', sa.UUID(), nullable=False),
        sa.Column('user_id', sa.UUID(), nullable=False),
        sa.Column('decision', sa.String(length=32), nullable=False),
        sa.Column('approver_type', sa.String(length=32), server_default='USER_EXPLICIT', nullable=False),
        sa.Column('reason', sa.Text(), nullable=True),
        sa.Column('plan_version', sa.Integer(), server_default='1', nullable=False),
        sa.Column('snapshot_checksum', sa.String(length=64), nullable=True),
        sa.Column('timestamp', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['plan_id'], ['workflow_execution_plans.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('ix_wf_approval_plan', 'workflow_approval_records', ['plan_id'], unique=False)
    op.create_index('ix_wf_approval_user', 'workflow_approval_records', ['user_id'], unique=False)
    op.create_index(op.f('ix_workflow_approval_records_plan_id'), 'workflow_approval_records', ['plan_id'], unique=False)
    op.create_index(op.f('ix_workflow_approval_records_user_id'), 'workflow_approval_records', ['user_id'], unique=False)

    # 3. workflow_rollback_records
    op.create_table(
        'workflow_rollback_records',
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('plan_id', sa.UUID(), nullable=False),
        sa.Column('user_id', sa.UUID(), nullable=False),
        sa.Column('triggered_by', sa.String(length=64), server_default='USER_MANUAL', nullable=False),
        sa.Column('status', sa.String(length=32), server_default='IN_PROGRESS', nullable=False),
        sa.Column('total_steps_to_compensate', sa.Integer(), server_default='0', nullable=False),
        sa.Column('compensated_steps_count', sa.Integer(), server_default='0', nullable=False),
        sa.Column('failed_compensations', postgresql.JSONB(astext_type=sa.Text()).with_variant(sa.Text(), 'sqlite'), nullable=True),
        sa.Column('compensation_details', postgresql.JSONB(astext_type=sa.Text()).with_variant(sa.Text(), 'sqlite'), nullable=True),
        sa.Column('started_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('completed_at', sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(['plan_id'], ['workflow_execution_plans.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('ix_wf_rollback_plan', 'workflow_rollback_records', ['plan_id'], unique=False)
    op.create_index('ix_wf_rollback_user', 'workflow_rollback_records', ['user_id'], unique=False)
    op.create_index(op.f('ix_workflow_rollback_records_plan_id'), 'workflow_rollback_records', ['plan_id'], unique=False)
    op.create_index(op.f('ix_workflow_rollback_records_user_id'), 'workflow_rollback_records', ['user_id'], unique=False)

    # 4. emergency_stop_events
    op.create_table(
        'emergency_stop_events',
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('scope', sa.String(length=32), server_default='USER_LEVEL', nullable=False),
        sa.Column('user_id', sa.UUID(), nullable=True),
        sa.Column('triggered_by', sa.String(length=64), server_default='USER', nullable=False),
        sa.Column('reason', sa.Text(), nullable=False),
        sa.Column('is_active', sa.Boolean(), server_default='true', nullable=False),
        sa.Column('affected_plans_count', sa.Integer(), server_default='0', nullable=False),
        sa.Column('affected_rules_count', sa.Integer(), server_default='0', nullable=False),
        sa.Column('started_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('lifted_at', sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('ix_emergency_stop_user_active', 'emergency_stop_events', ['user_id', 'is_active'], unique=False)
    op.create_index('ix_emergency_stop_scope_active', 'emergency_stop_events', ['scope', 'is_active'], unique=False)
    op.create_index(op.f('ix_emergency_stop_events_user_id'), 'emergency_stop_events', ['user_id'], unique=False)


def downgrade() -> None:
    op.drop_table('emergency_stop_events')
    op.drop_table('workflow_rollback_records')
    op.drop_table('workflow_approval_records')
    op.drop_table('workflow_audit_events')
