"""add phase 7.4 workflow planning and orchestration tables

Revision ID: o5p6q7r8s9t0
Revises: n4o5p6q7r8s9
Create Date: 2026-11-25 18:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = 'o5p6q7r8s9t0'
down_revision: Union[str, None] = 'n4o5p6q7r8s9'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. workflow_definitions
    op.create_table(
        'workflow_definitions',
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('user_id', sa.UUID(), nullable=False),
        sa.Column('name', sa.String(length=128), nullable=False),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('workflow_category', sa.String(length=64), server_default='TASK_MANAGEMENT', nullable=False),
        sa.Column('trigger_type', sa.String(length=64), nullable=True),
        sa.Column('is_active', sa.Boolean(), server_default='true', nullable=False),
        sa.Column('version', sa.Integer(), server_default='1', nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('ix_workflow_defs_user_active', 'workflow_definitions', ['user_id', 'is_active'], unique=False)
    op.create_index('ix_workflow_defs_category', 'workflow_definitions', ['workflow_category'], unique=False)
    op.create_index(op.f('ix_workflow_definitions_user_id'), 'workflow_definitions', ['user_id'], unique=False)

    # 2. workflow_steps
    op.create_table(
        'workflow_steps',
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('workflow_definition_id', sa.UUID(), nullable=False),
        sa.Column('step_key', sa.String(length=64), nullable=False),
        sa.Column('name', sa.String(length=128), nullable=False),
        sa.Column('action_identifier', sa.String(length=128), nullable=False),
        sa.Column('parameters', postgresql.JSONB(astext_type=sa.Text()).with_variant(sa.Text(), 'sqlite'), nullable=False),
        sa.Column('order_index', sa.Integer(), server_default='0', nullable=False),
        sa.Column('is_optional', sa.Boolean(), server_default='false', nullable=False),
        sa.Column('requires_approval', sa.Boolean(), server_default='true', nullable=False),
        sa.Column('timeout_seconds', sa.Integer(), server_default='300', nullable=False),
        sa.Column('estimated_duration_minutes', sa.Integer(), server_default='10', nullable=False),
        sa.Column('condition_expression', postgresql.JSONB(astext_type=sa.Text()).with_variant(sa.Text(), 'sqlite'), nullable=True),
        sa.Column('compensation_action_identifier', sa.String(length=128), nullable=True),
        sa.Column('compensation_parameters', postgresql.JSONB(astext_type=sa.Text()).with_variant(sa.Text(), 'sqlite'), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['workflow_definition_id'], ['workflow_definitions.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('ix_workflow_steps_def_key', 'workflow_steps', ['workflow_definition_id', 'step_key'], unique=True)
    op.create_index('ix_workflow_steps_action', 'workflow_steps', ['action_identifier'], unique=False)
    op.create_index(op.f('ix_workflow_steps_workflow_definition_id'), 'workflow_steps', ['workflow_definition_id'], unique=False)

    # 3. workflow_dependencies
    op.create_table(
        'workflow_dependencies',
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('workflow_definition_id', sa.UUID(), nullable=False),
        sa.Column('source_step_key', sa.String(length=64), nullable=False),
        sa.Column('target_step_key', sa.String(length=64), nullable=False),
        sa.Column('dependency_type', sa.String(length=32), server_default='SUCCESS', nullable=False),
        sa.Column('condition_payload', postgresql.JSONB(astext_type=sa.Text()).with_variant(sa.Text(), 'sqlite'), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['workflow_definition_id'], ['workflow_definitions.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('ix_workflow_dep_def', 'workflow_dependencies', ['workflow_definition_id'], unique=False)
    op.create_index('ix_workflow_dep_source_target', 'workflow_dependencies', ['workflow_definition_id', 'source_step_key', 'target_step_key'], unique=True)

    # 4. workflow_execution_plans
    op.create_table(
        'workflow_execution_plans',
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('workflow_definition_id', sa.UUID(), nullable=True),
        sa.Column('user_id', sa.UUID(), nullable=False),
        sa.Column('title', sa.String(length=255), nullable=False),
        sa.Column('status', sa.String(length=32), server_default='CREATED', nullable=False),
        sa.Column('version', sa.Integer(), server_default='1', nullable=False),
        sa.Column('idempotency_key', sa.String(length=128), nullable=False),
        sa.Column('trigger_context', postgresql.JSONB(astext_type=sa.Text()).with_variant(sa.Text(), 'sqlite'), nullable=False),
        sa.Column('plan_steps', postgresql.JSONB(astext_type=sa.Text()).with_variant(sa.Text(), 'sqlite'), nullable=False),
        sa.Column('plan_dependencies', postgresql.JSONB(astext_type=sa.Text()).with_variant(sa.Text(), 'sqlite'), nullable=False),
        sa.Column('rationale', sa.Text(), nullable=False),
        sa.Column('expected_benefits', postgresql.JSONB(astext_type=sa.Text()).with_variant(sa.Text(), 'sqlite'), nullable=False),
        sa.Column('potential_side_effects', postgresql.JSONB(astext_type=sa.Text()).with_variant(sa.Text(), 'sqlite'), nullable=False),
        sa.Column('utility_score', sa.Float(), server_default='0.85', nullable=False),
        sa.Column('plan_comparison_metadata', postgresql.JSONB(astext_type=sa.Text()).with_variant(sa.Text(), 'sqlite'), nullable=True),
        sa.Column('reversibility_summary', postgresql.JSONB(astext_type=sa.Text()).with_variant(sa.Text(), 'sqlite'), nullable=False),
        sa.Column('approved_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('executed_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('expires_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['workflow_definition_id'], ['workflow_definitions.id'], ondelete='SET NULL'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('ix_workflow_plans_user_status', 'workflow_execution_plans', ['user_id', 'status'], unique=False)
    op.create_index('ix_workflow_plans_idempotency', 'workflow_execution_plans', ['user_id', 'idempotency_key'], unique=True)
    op.create_index('ix_workflow_plans_created', 'workflow_execution_plans', ['created_at'], unique=False)

    # 5. workflow_plan_versions
    op.create_table(
        'workflow_plan_versions',
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('plan_id', sa.UUID(), nullable=False),
        sa.Column('version', sa.Integer(), nullable=False),
        sa.Column('plan_snapshot', postgresql.JSONB(astext_type=sa.Text()).with_variant(sa.Text(), 'sqlite'), nullable=False),
        sa.Column('change_summary', sa.String(length=255), server_default='Plan modified', nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['plan_id'], ['workflow_execution_plans.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('ix_workflow_plan_versions_plan_v', 'workflow_plan_versions', ['plan_id', 'version'], unique=True)


def downgrade() -> None:
    op.drop_table('workflow_plan_versions')
    op.drop_table('workflow_execution_plans')
    op.drop_table('workflow_dependencies')
    op.drop_table('workflow_steps')
    op.drop_table('workflow_definitions')
