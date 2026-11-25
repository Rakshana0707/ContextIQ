"""add phase 7.2 automation rules, triggers, conditions, actions, executions, and versions

Revision ID: m3n4o5p6q7r8
Revises: l2m3n4o5p6q7
Create Date: 2026-11-25 17:30:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = 'm3n4o5p6q7r8'
down_revision: Union[str, None] = 'l2m3n4o5p6q7'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. automation_rules
    op.create_table(
        'automation_rules',
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('user_id', sa.UUID(), nullable=False),
        sa.Column('name', sa.String(length=128), nullable=False),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('is_enabled', sa.Boolean(), server_default='true', nullable=False),
        sa.Column('version', sa.Integer(), server_default='1', nullable=False),
        sa.Column('priority', sa.Integer(), server_default='10', nullable=False),
        sa.Column('cooldown_minutes', sa.Integer(), server_default='30', nullable=False),
        sa.Column('max_executions_per_day', sa.Integer(), server_default='5', nullable=False),
        sa.Column('requires_approval', sa.Boolean(), server_default='true', nullable=False),
        sa.Column('risk_tier', sa.String(length=32), server_default='Tier 2', nullable=False),
        sa.Column('active_schedule', postgresql.JSONB(astext_type=sa.Text()).with_variant(sa.Text(), 'sqlite'), nullable=False),
        sa.Column('quiet_hours', postgresql.JSONB(astext_type=sa.Text()).with_variant(sa.Text(), 'sqlite'), nullable=False),
        sa.Column('expires_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('last_triggered_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('execution_count_today', sa.Integer(), server_default='0', nullable=False),
        sa.Column('last_execution_date', sa.DateTime(timezone=True), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_automation_rules_user_id'), 'automation_rules', ['user_id'], unique=False)
    op.create_index(op.f('ix_automation_rules_is_enabled'), 'automation_rules', ['is_enabled'], unique=False)
    op.create_index('ix_automation_rules_user_enabled', 'automation_rules', ['user_id', 'is_enabled'], unique=False)
    op.create_index('ix_automation_rules_user_priority', 'automation_rules', ['user_id', 'priority'], unique=False)

    # 2. automation_triggers
    op.create_table(
        'automation_triggers',
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('rule_id', sa.UUID(), nullable=False),
        sa.Column('trigger_type', sa.String(length=64), nullable=False),
        sa.Column('parameters', postgresql.JSONB(astext_type=sa.Text()).with_variant(sa.Text(), 'sqlite'), nullable=False),
        sa.Column('is_authorized', sa.Boolean(), server_default='true', nullable=False),
        sa.Column('authorization_source', sa.String(length=64), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['rule_id'], ['automation_rules.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_automation_triggers_rule_id'), 'automation_triggers', ['rule_id'], unique=False)
    op.create_index(op.f('ix_automation_triggers_type'), 'automation_triggers', ['trigger_type'], unique=False)
    op.create_index('ix_automation_triggers_rule_type', 'automation_triggers', ['rule_id', 'trigger_type'], unique=False)

    # 3. automation_conditions
    op.create_table(
        'automation_conditions',
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('rule_id', sa.UUID(), nullable=False),
        sa.Column('condition_group', sa.Integer(), server_default='0', nullable=False),
        sa.Column('logical_operator', sa.String(length=8), server_default='AND', nullable=False),
        sa.Column('field_path', sa.String(length=128), nullable=False),
        sa.Column('operator', sa.String(length=32), nullable=False),
        sa.Column('expected_value', postgresql.JSONB(astext_type=sa.Text()).with_variant(sa.Text(), 'sqlite'), nullable=False),
        sa.Column('min_evidence_observations', sa.Integer(), server_default='1', nullable=False),
        sa.Column('confidence_threshold', sa.Float(), server_default='0.0', nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['rule_id'], ['automation_rules.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_automation_conditions_rule_id'), 'automation_conditions', ['rule_id'], unique=False)
    op.create_index('ix_automation_conditions_rule_group', 'automation_conditions', ['rule_id', 'condition_group'], unique=False)

    # 4. automation_action_definitions
    op.create_table(
        'automation_action_definitions',
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('rule_id', sa.UUID(), nullable=False),
        sa.Column('action_order', sa.Integer(), server_default='1', nullable=False),
        sa.Column('action_identifier', sa.String(length=128), nullable=False),
        sa.Column('parameters_template', postgresql.JSONB(astext_type=sa.Text()).with_variant(sa.Text(), 'sqlite'), nullable=False),
        sa.Column('is_critical', sa.Boolean(), server_default='true', nullable=False),
        sa.Column('is_reversible', sa.Boolean(), server_default='true', nullable=False),
        sa.Column('action_preview_template', postgresql.JSONB(astext_type=sa.Text()).with_variant(sa.Text(), 'sqlite'), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['rule_id'], ['automation_rules.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_automation_action_definitions_rule_id'), 'automation_action_definitions', ['rule_id'], unique=False)
    op.create_index('ix_automation_actions_rule_order', 'automation_action_definitions', ['rule_id', 'action_order'], unique=False)

    # 5. automation_executions
    op.create_table(
        'automation_executions',
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('rule_id', sa.UUID(), nullable=False),
        sa.Column('user_id', sa.UUID(), nullable=False),
        sa.Column('trigger_event_id', sa.String(length=128), nullable=False),
        sa.Column('trigger_type', sa.String(length=64), nullable=False),
        sa.Column('status', sa.String(length=32), nullable=False),
        sa.Column('matched_conditions', postgresql.JSONB(astext_type=sa.Text()).with_variant(sa.Text(), 'sqlite'), nullable=False),
        sa.Column('suppression_reason', sa.Text(), nullable=True),
        sa.Column('workflow_instance_id', sa.UUID(), nullable=True),
        sa.Column('idempotency_key', sa.String(length=128), nullable=False),
        sa.Column('execution_duration_ms', sa.Float(), server_default='0.0', nullable=False),
        sa.Column('executed_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['rule_id'], ['automation_rules.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_automation_executions_rule_id'), 'automation_executions', ['rule_id'], unique=False)
    op.create_index(op.f('ix_automation_executions_user_id'), 'automation_executions', ['user_id'], unique=False)
    op.create_index(op.f('ix_automation_executions_status'), 'automation_executions', ['status'], unique=False)
    op.create_index('ix_automation_executions_user_time', 'automation_executions', ['user_id', 'executed_at'], unique=False)
    op.create_index('ix_automation_executions_rule_status', 'automation_executions', ['rule_id', 'status'], unique=False)
    op.create_index('ix_automation_executions_idempotency', 'automation_executions', ['idempotency_key'], unique=True)

    # 6. automation_rule_versions
    op.create_table(
        'automation_rule_versions',
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('rule_id', sa.UUID(), nullable=False),
        sa.Column('version_number', sa.Integer(), nullable=False),
        sa.Column('rule_snapshot', postgresql.JSONB(astext_type=sa.Text()).with_variant(sa.Text(), 'sqlite'), nullable=False),
        sa.Column('change_summary', sa.String(length=256), nullable=True),
        sa.Column('changed_by', sa.UUID(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['rule_id'], ['automation_rules.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_automation_rule_versions_rule_id'), 'automation_rule_versions', ['rule_id'], unique=False)
    op.create_index('ix_automation_rule_versions_rule_ver', 'automation_rule_versions', ['rule_id', 'version_number'], unique=True)


def downgrade() -> None:
    op.drop_table('automation_rule_versions')
    op.drop_table('automation_executions')
    op.drop_table('automation_action_definitions')
    op.drop_table('automation_conditions')
    op.drop_table('automation_triggers')
    op.drop_table('automation_rules')
