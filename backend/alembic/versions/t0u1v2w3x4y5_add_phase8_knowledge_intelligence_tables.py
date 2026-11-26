"""add_phase8_knowledge_intelligence_tables

Revision ID: t0u1v2w3x4y5
Revises: s9t0u1v2w3x4
Create Date: 2026-11-26 17:55:00.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB, UUID

# revision identifiers, used by Alembic.
revision = 't0u1v2w3x4y5'
down_revision = 's9t0u1v2w3x4'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # 1. Projects, Goals, Milestones
    op.create_table(
        'projects',
        sa.Column('id', UUID(as_uuid=True), primary_key=True),
        sa.Column('user_id', UUID(as_uuid=True), sa.ForeignKey('users.id', ondelete='CASCADE'), nullable=False, index=True),
        sa.Column('title', sa.String(255), nullable=False),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('status', sa.String(32), nullable=False, server_default='ACTIVE'),
        sa.Column('priority', sa.String(32), nullable=False, server_default='MEDIUM'),
        sa.Column('target_completion_date', sa.DateTime(timezone=True), nullable=True),
        sa.Column('completion_criteria', sa.Text(), nullable=True),
        sa.Column('health_status', sa.String(32), nullable=False, server_default='ON_TRACK', index=True),
        sa.Column('metadata_payload', JSONB, nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )

    op.create_table(
        'goals',
        sa.Column('id', UUID(as_uuid=True), primary_key=True),
        sa.Column('user_id', UUID(as_uuid=True), sa.ForeignKey('users.id', ondelete='CASCADE'), nullable=False, index=True),
        sa.Column('parent_goal_id', UUID(as_uuid=True), sa.ForeignKey('goals.id', ondelete='SET NULL'), nullable=True, index=True),
        sa.Column('title', sa.String(255), nullable=False),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('category', sa.String(64), nullable=False, server_default='PRODUCTIVITY'),
        sa.Column('hierarchy_level', sa.String(32), nullable=False, server_default='LONG_TERM', index=True),
        sa.Column('priority', sa.String(32), nullable=False, server_default='MEDIUM', index=True),
        sa.Column('status', sa.String(32), nullable=False, server_default='ACTIVE'),
        sa.Column('target_date', sa.DateTime(timezone=True), nullable=True),
        sa.Column('progress_pct', sa.Float(), nullable=False, server_default='0.0'),
        sa.Column('completion_criteria', sa.Text(), nullable=True),
        sa.Column('metadata_payload', JSONB, nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )

    op.create_table(
        'milestones',
        sa.Column('id', UUID(as_uuid=True), primary_key=True),
        sa.Column('user_id', UUID(as_uuid=True), sa.ForeignKey('users.id', ondelete='CASCADE'), nullable=False, index=True),
        sa.Column('project_id', UUID(as_uuid=True), sa.ForeignKey('projects.id', ondelete='CASCADE'), nullable=True, index=True),
        sa.Column('goal_id', UUID(as_uuid=True), sa.ForeignKey('goals.id', ondelete='CASCADE'), nullable=True, index=True),
        sa.Column('title', sa.String(255), nullable=False),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('status', sa.String(32), nullable=False, server_default='PENDING'),
        sa.Column('target_date', sa.DateTime(timezone=True), nullable=True),
        sa.Column('completed_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('order_index', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('is_critical', sa.Boolean(), nullable=False, server_default=sa.text('false')),
        sa.Column('metadata_payload', JSONB, nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )

    # 2. Knowledge Graph Universal Registry
    op.create_table(
        'knowledge_graph_nodes',
        sa.Column('id', UUID(as_uuid=True), primary_key=True),
        sa.Column('user_id', UUID(as_uuid=True), sa.ForeignKey('users.id', ondelete='CASCADE'), nullable=False, index=True),
        sa.Column('node_type', sa.String(64), nullable=False, index=True),
        sa.Column('entity_id', UUID(as_uuid=True), nullable=False, index=True),
        sa.Column('entity_table', sa.String(64), nullable=False),
        sa.Column('name', sa.String(255), nullable=False),
        sa.Column('is_archived', sa.Boolean(), nullable=False, server_default=sa.text('false'), index=True),
        sa.Column('archived_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('properties', JSONB, nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )

    op.create_table(
        'knowledge_graph_edges',
        sa.Column('id', UUID(as_uuid=True), primary_key=True),
        sa.Column('user_id', UUID(as_uuid=True), sa.ForeignKey('users.id', ondelete='CASCADE'), nullable=False, index=True),
        sa.Column('source_node_id', UUID(as_uuid=True), sa.ForeignKey('knowledge_graph_nodes.id', ondelete='CASCADE'), nullable=False, index=True),
        sa.Column('target_node_id', UUID(as_uuid=True), sa.ForeignKey('knowledge_graph_nodes.id', ondelete='CASCADE'), nullable=False, index=True),
        sa.Column('relationship_type', sa.String(64), nullable=False, index=True),
        sa.Column('confidence', sa.Float(), nullable=False, server_default='1.0'),
        sa.Column('is_inferred', sa.Boolean(), nullable=False, server_default=sa.text('false')),
        sa.Column('is_valid', sa.Boolean(), nullable=False, server_default=sa.text('true'), index=True),
        sa.Column('valid_until', sa.DateTime(timezone=True), nullable=True),
        sa.Column('weight', sa.Float(), nullable=False, server_default='1.0'),
        sa.Column('properties', JSONB, nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )

    op.create_table(
        'knowledge_evidence',
        sa.Column('id', UUID(as_uuid=True), primary_key=True),
        sa.Column('user_id', UUID(as_uuid=True), sa.ForeignKey('users.id', ondelete='CASCADE'), nullable=False, index=True),
        sa.Column('relationship_id', UUID(as_uuid=True), sa.ForeignKey('knowledge_graph_edges.id', ondelete='CASCADE'), nullable=False, index=True),
        sa.Column('evidence_type', sa.String(64), nullable=False),
        sa.Column('source_entity_id', UUID(as_uuid=True), nullable=True),
        sa.Column('source_entity_table', sa.String(64), nullable=True),
        sa.Column('confidence_score', sa.Float(), nullable=False, server_default='1.0'),
        sa.Column('payload', JSONB, nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column('recorded_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column('is_valid', sa.Boolean(), nullable=False, server_default=sa.text('true'), index=True),
    )

    op.create_table(
        'knowledge_graph_versions',
        sa.Column('id', UUID(as_uuid=True), primary_key=True),
        sa.Column('user_id', UUID(as_uuid=True), sa.ForeignKey('users.id', ondelete='CASCADE'), nullable=False, index=True),
        sa.Column('version_number', sa.Integer(), nullable=False, server_default='1'),
        sa.Column('change_type', sa.String(64), nullable=False),
        sa.Column('affected_node_ids', JSONB, nullable=False, server_default=sa.text("'[]'::jsonb")),
        sa.Column('affected_relationship_ids', JSONB, nullable=False, server_default=sa.text("'[]'::jsonb")),
        sa.Column('change_summary', sa.String(512), nullable=False),
        sa.Column('version_metadata', JSONB, nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )

    # 3. Behavioral Memory
    op.create_table(
        'behavioral_memories',
        sa.Column('id', UUID(as_uuid=True), primary_key=True),
        sa.Column('user_id', UUID(as_uuid=True), sa.ForeignKey('users.id', ondelete='CASCADE'), nullable=False, index=True),
        sa.Column('category', sa.String(64), nullable=False, index=True),
        sa.Column('title', sa.String(255), nullable=False),
        sa.Column('description', sa.Text(), nullable=False),
        sa.Column('confidence', sa.Float(), nullable=False, server_default='0.5'),
        sa.Column('observation_count', sa.Integer(), nullable=False, server_default='1'),
        sa.Column('validity_status', sa.String(32), nullable=False, server_default='VALID', index=True),
        sa.Column('source_type', sa.String(32), nullable=False, server_default='INFERRED'),
        sa.Column('decay_weight', sa.Float(), nullable=False, server_default='1.0'),
        sa.Column('half_life_days', sa.Integer(), nullable=False, server_default='30'),
        sa.Column('is_pinned', sa.Boolean(), nullable=False, server_default=sa.text('false')),
        sa.Column('is_user_edited', sa.Boolean(), nullable=False, server_default=sa.text('false')),
        sa.Column('first_observed_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column('last_observed_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column('last_reinforced_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column('supporting_evidence', JSONB, nullable=False, server_default=sa.text("'[]'::jsonb")),
        sa.Column('metadata_payload', JSONB, nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )

    op.create_table(
        'behavioral_memory_snapshots',
        sa.Column('id', UUID(as_uuid=True), primary_key=True),
        sa.Column('user_id', UUID(as_uuid=True), sa.ForeignKey('users.id', ondelete='CASCADE'), nullable=False, index=True),
        sa.Column('snapshot_date', sa.Date(), nullable=False, index=True),
        sa.Column('active_memories_count', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('category_distribution', JSONB, nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column('avg_confidence', sa.Float(), nullable=False, server_default='0.0'),
        sa.Column('emerging_patterns_count', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('decayed_patterns_count', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('payload', JSONB, nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )

    op.create_table(
        'behavioral_memory_corrections',
        sa.Column('id', UUID(as_uuid=True), primary_key=True),
        sa.Column('user_id', UUID(as_uuid=True), sa.ForeignKey('users.id', ondelete='CASCADE'), nullable=False, index=True),
        sa.Column('memory_id', UUID(as_uuid=True), sa.ForeignKey('behavioral_memories.id', ondelete='CASCADE'), nullable=False, index=True),
        sa.Column('action', sa.String(32), nullable=False),
        sa.Column('previous_state', JSONB, nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column('corrected_state', JSONB, nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column('user_rationale', sa.Text(), nullable=True),
        sa.Column('corrected_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )

    # 4. Goal-Project Associations & Snapshots
    op.create_table(
        'goal_task_associations',
        sa.Column('id', UUID(as_uuid=True), primary_key=True),
        sa.Column('user_id', UUID(as_uuid=True), sa.ForeignKey('users.id', ondelete='CASCADE'), nullable=False, index=True),
        sa.Column('goal_id', UUID(as_uuid=True), sa.ForeignKey('goals.id', ondelete='CASCADE'), nullable=True, index=True),
        sa.Column('project_id', UUID(as_uuid=True), sa.ForeignKey('projects.id', ondelete='CASCADE'), nullable=True, index=True),
        sa.Column('milestone_id', UUID(as_uuid=True), sa.ForeignKey('milestones.id', ondelete='SET NULL'), nullable=True, index=True),
        sa.Column('task_id', UUID(as_uuid=True), sa.ForeignKey('tasks.id', ondelete='CASCADE'), nullable=False, index=True),
        sa.Column('association_type', sa.String(32), nullable=False, server_default='CONTRIBUTES_TO'),
        sa.Column('importance_weight', sa.Float(), nullable=False, server_default='1.0'),
        sa.Column('effort_weight', sa.Float(), nullable=False, server_default='1.0'),
        sa.Column('is_critical_path', sa.Boolean(), nullable=False, server_default=sa.text('false'), index=True),
        sa.Column('metadata_payload', JSONB, nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )

    op.create_table(
        'project_goal_associations',
        sa.Column('id', UUID(as_uuid=True), primary_key=True),
        sa.Column('user_id', UUID(as_uuid=True), sa.ForeignKey('users.id', ondelete='CASCADE'), nullable=False, index=True),
        sa.Column('project_id', UUID(as_uuid=True), sa.ForeignKey('projects.id', ondelete='CASCADE'), nullable=False, index=True),
        sa.Column('goal_id', UUID(as_uuid=True), sa.ForeignKey('goals.id', ondelete='CASCADE'), nullable=False, index=True),
        sa.Column('contribution_weight', sa.Float(), nullable=False, server_default='1.0'),
        sa.Column('metadata_payload', JSONB, nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )

    op.create_table(
        'goal_progress_snapshots',
        sa.Column('id', UUID(as_uuid=True), primary_key=True),
        sa.Column('user_id', UUID(as_uuid=True), sa.ForeignKey('users.id', ondelete='CASCADE'), nullable=False, index=True),
        sa.Column('goal_id', UUID(as_uuid=True), sa.ForeignKey('goals.id', ondelete='CASCADE'), nullable=False, index=True),
        sa.Column('snapshot_date', sa.Date(), nullable=False, index=True),
        sa.Column('progress_pct', sa.Float(), nullable=False, server_default='0.0'),
        sa.Column('completed_milestones_count', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('total_milestones_count', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('completed_tasks_count', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('total_tasks_count', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('behavioral_alignment_score', sa.Float(), nullable=False, server_default='1.0'),
        sa.Column('delay_risk_score', sa.Float(), nullable=False, server_default='0.0'),
        sa.Column('velocity_tasks_per_week', sa.Float(), nullable=False, server_default='0.0'),
        sa.Column('estimated_completion_date', sa.DateTime(timezone=True), nullable=True),
        sa.Column('risk_factors', JSONB, nullable=False, server_default=sa.text("'[]'::jsonb")),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )

    op.create_table(
        'project_progress_snapshots',
        sa.Column('id', UUID(as_uuid=True), primary_key=True),
        sa.Column('user_id', UUID(as_uuid=True), sa.ForeignKey('users.id', ondelete='CASCADE'), nullable=False, index=True),
        sa.Column('project_id', UUID(as_uuid=True), sa.ForeignKey('projects.id', ondelete='CASCADE'), nullable=False, index=True),
        sa.Column('snapshot_date', sa.Date(), nullable=False, index=True),
        sa.Column('progress_pct', sa.Float(), nullable=False, server_default='0.0'),
        sa.Column('health_status', sa.String(32), nullable=False, server_default='ON_TRACK'),
        sa.Column('completed_tasks_count', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('total_tasks_count', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('completed_milestones_count', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('total_milestones_count', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('blocker_count', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('burnup_rate', sa.Float(), nullable=False, server_default='0.0'),
        sa.Column('estimated_finish_date', sa.DateTime(timezone=True), nullable=True),
        sa.Column('payload', JSONB, nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )

    # 5. Task Dependencies
    op.create_table(
        'task_dependencies',
        sa.Column('id', UUID(as_uuid=True), primary_key=True),
        sa.Column('user_id', UUID(as_uuid=True), sa.ForeignKey('users.id', ondelete='CASCADE'), nullable=False, index=True),
        sa.Column('source_task_id', UUID(as_uuid=True), sa.ForeignKey('tasks.id', ondelete='CASCADE'), nullable=False, index=True),
        sa.Column('target_task_id', UUID(as_uuid=True), sa.ForeignKey('tasks.id', ondelete='CASCADE'), nullable=False, index=True),
        sa.Column('dependency_type', sa.String(64), nullable=False, server_default='INFERRED_DEPENDENCY', index=True),
        sa.Column('is_inferred', sa.Boolean(), nullable=False, server_default=sa.text('true'), index=True),
        sa.Column('confidence', sa.Float(), nullable=False, server_default='0.5'),
        sa.Column('detection_method', sa.String(64), nullable=False, server_default='RULE_BASED'),
        sa.Column('validation_status', sa.String(64), nullable=False, server_default='PROPOSED', index=True),
        sa.Column('supporting_observations', JSONB, nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column('first_observed_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column('last_observed_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )

    op.create_table(
        'task_dependency_audit_logs',
        sa.Column('id', UUID(as_uuid=True), primary_key=True),
        sa.Column('user_id', UUID(as_uuid=True), sa.ForeignKey('users.id', ondelete='CASCADE'), nullable=False, index=True),
        sa.Column('dependency_id', UUID(as_uuid=True), sa.ForeignKey('task_dependencies.id', ondelete='CASCADE'), nullable=False, index=True),
        sa.Column('action', sa.String(64), nullable=False),
        sa.Column('previous_status', sa.String(64), nullable=True),
        sa.Column('new_status', sa.String(64), nullable=True),
        sa.Column('actor', sa.String(32), nullable=False, server_default='USER'),
        sa.Column('notes', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )

    # 6. Project Forecasts
    op.create_table(
        'project_forecasts',
        sa.Column('id', UUID(as_uuid=True), primary_key=True),
        sa.Column('user_id', UUID(as_uuid=True), sa.ForeignKey('users.id', ondelete='CASCADE'), nullable=False, index=True),
        sa.Column('project_id', UUID(as_uuid=True), sa.ForeignKey('projects.id', ondelete='CASCADE'), nullable=False, index=True),
        sa.Column('forecast_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now(), index=True),
        sa.Column('on_time_probability', sa.Float(), nullable=False),
        sa.Column('estimated_completion_date', sa.DateTime(timezone=True), nullable=True),
        sa.Column('p50_completion_date', sa.DateTime(timezone=True), nullable=True),
        sa.Column('p80_completion_date', sa.DateTime(timezone=True), nullable=True),
        sa.Column('p95_completion_date', sa.DateTime(timezone=True), nullable=True),
        sa.Column('delay_risk_score', sa.Float(), nullable=False),
        sa.Column('delay_risk_tier', sa.String(32), nullable=False),
        sa.Column('expected_delay_days', sa.Float(), nullable=False, server_default='0.0'),
        sa.Column('remaining_workload_hours', sa.Float(), nullable=False, server_default='0.0'),
        sa.Column('unresolved_blocker_probability', sa.Float(), nullable=False, server_default='0.0'),
        sa.Column('data_sufficiency', sa.String(32), nullable=False),
        sa.Column('uncertainty_level', sa.String(32), nullable=False, server_default='MEDIUM'),
        sa.Column('confidence_interval_lower_days', sa.Float(), nullable=True),
        sa.Column('confidence_interval_upper_days', sa.Float(), nullable=True),
        sa.Column('model_name', sa.String(64), nullable=False),
        sa.Column('model_version', sa.String(32), nullable=False, server_default='1.0.0'),
        sa.Column('feature_snapshot', JSONB, nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column('shap_importance_snapshot', JSONB, nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )

    op.create_table(
        'milestone_forecasts',
        sa.Column('id', UUID(as_uuid=True), primary_key=True),
        sa.Column('user_id', UUID(as_uuid=True), sa.ForeignKey('users.id', ondelete='CASCADE'), nullable=False, index=True),
        sa.Column('project_forecast_id', UUID(as_uuid=True), sa.ForeignKey('project_forecasts.id', ondelete='CASCADE'), nullable=False, index=True),
        sa.Column('milestone_id', UUID(as_uuid=True), sa.ForeignKey('milestones.id', ondelete='CASCADE'), nullable=False, index=True),
        sa.Column('milestone_title', sa.String(255), nullable=False),
        sa.Column('target_date', sa.DateTime(timezone=True), nullable=True),
        sa.Column('on_time_probability', sa.Float(), nullable=False),
        sa.Column('estimated_completion_date', sa.DateTime(timezone=True), nullable=True),
        sa.Column('delay_risk_score', sa.Float(), nullable=False),
        sa.Column('delay_risk_tier', sa.String(32), nullable=False),
        sa.Column('blocked_dependency_count', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('is_critical_path', sa.Boolean(), nullable=False, server_default=sa.text('false')),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )

    op.create_table(
        'forecast_scenario_comparisons',
        sa.Column('id', UUID(as_uuid=True), primary_key=True),
        sa.Column('user_id', UUID(as_uuid=True), sa.ForeignKey('users.id', ondelete='CASCADE'), nullable=False, index=True),
        sa.Column('project_id', UUID(as_uuid=True), sa.ForeignKey('projects.id', ondelete='CASCADE'), nullable=False, index=True),
        sa.Column('scenario_name', sa.String(128), nullable=False),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('adjusted_weekly_velocity_tasks', sa.Float(), nullable=True),
        sa.Column('unblocked_tasks_count', sa.Integer(), nullable=True),
        sa.Column('simulated_on_time_prob', sa.Float(), nullable=False),
        sa.Column('delta_on_time_prob', sa.Float(), nullable=False),
        sa.Column('simulated_completion_date', sa.DateTime(timezone=True), nullable=True),
        sa.Column('delta_completion_days', sa.Float(), nullable=False, server_default='0.0'),
        sa.Column('scenario_parameters', JSONB, nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )

    # 7. Behavioral Trends
    op.create_table(
        'behavioral_daily_metrics',
        sa.Column('id', UUID(as_uuid=True), primary_key=True),
        sa.Column('user_id', UUID(as_uuid=True), sa.ForeignKey('users.id', ondelete='CASCADE'), nullable=False, index=True),
        sa.Column('metric_date', sa.Date(), nullable=False, index=True),
        sa.Column('total_focus_minutes', sa.Float(), nullable=False, server_default='0.0'),
        sa.Column('focus_sessions_count', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('avg_session_duration_minutes', sa.Float(), nullable=False, server_default='0.0'),
        sa.Column('focus_consistency_score', sa.Float(), nullable=False, server_default='0.0'),
        sa.Column('interruption_count', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('interruptions_per_focus_hour', sa.Float(), nullable=False, server_default='0.0'),
        sa.Column('avg_recovery_lag_seconds', sa.Float(), nullable=False, server_default='0.0'),
        sa.Column('recovery_efficiency_score', sa.Float(), nullable=False, server_default='0.0'),
        sa.Column('context_switch_frequency', sa.Float(), nullable=False, server_default='0.0'),
        sa.Column('behavioral_friction_index', sa.Float(), nullable=False, server_default='0.0'),
        sa.Column('tasks_completed_count', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('tasks_due_count', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('tasks_completed_on_time', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('deadline_adherence_rate', sa.Float(), nullable=False, server_default='1.0'),
        sa.Column('data_coverage_ratio', sa.Float(), nullable=False, server_default='1.0'),
        sa.Column('raw_telemetry_snapshot', JSONB, nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )

    op.create_table(
        'behavioral_trend_aggregates',
        sa.Column('id', UUID(as_uuid=True), primary_key=True),
        sa.Column('user_id', UUID(as_uuid=True), sa.ForeignKey('users.id', ondelete='CASCADE'), nullable=False, index=True),
        sa.Column('category', sa.String(64), nullable=False, index=True),
        sa.Column('granularity', sa.String(32), nullable=False, index=True),
        sa.Column('start_date', sa.Date(), nullable=False),
        sa.Column('end_date', sa.Date(), nullable=False),
        sa.Column('rolling_mean', sa.Float(), nullable=False),
        sa.Column('exponential_moving_avg', sa.Float(), nullable=False),
        sa.Column('slope', sa.Float(), nullable=False, server_default='0.0'),
        sa.Column('trend_direction', sa.String(32), nullable=False),
        sa.Column('pct_change_vs_baseline', sa.Float(), nullable=False, server_default='0.0'),
        sa.Column('change_point_detected', sa.Boolean(), nullable=False, server_default=sa.text('false')),
        sa.Column('volatility_std_dev', sa.Float(), nullable=False, server_default='0.0'),
        sa.Column('data_coverage_ratio', sa.Float(), nullable=False, server_default='1.0'),
        sa.Column('metadata_payload', JSONB, nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )

    op.create_table(
        'behavioral_milestone_records',
        sa.Column('id', UUID(as_uuid=True), primary_key=True),
        sa.Column('user_id', UUID(as_uuid=True), sa.ForeignKey('users.id', ondelete='CASCADE'), nullable=False, index=True),
        sa.Column('milestone_type', sa.String(64), nullable=False, index=True),
        sa.Column('title', sa.String(255), nullable=False),
        sa.Column('description', sa.Text(), nullable=False),
        sa.Column('detected_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now(), index=True),
        sa.Column('metric_category', sa.String(64), nullable=False),
        sa.Column('baseline_value', sa.Float(), nullable=False),
        sa.Column('sustained_value', sa.Float(), nullable=False),
        sa.Column('percentage_improvement', sa.Float(), nullable=False),
        sa.Column('significance_level', sa.Float(), nullable=False, server_default='0.05'),
        sa.Column('observation_window_days', sa.Integer(), nullable=False, server_default='14'),
        sa.Column('is_active', sa.Boolean(), nullable=False, server_default=sa.text('true')),
        sa.Column('evidence_payload', JSONB, nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )

    # 8. Assistant Conversations & Messages
    op.create_table(
        'assistant_conversations',
        sa.Column('id', UUID(as_uuid=True), primary_key=True),
        sa.Column('user_id', UUID(as_uuid=True), sa.ForeignKey('users.id', ondelete='CASCADE'), nullable=False, index=True),
        sa.Column('title', sa.String(255), nullable=False),
        sa.Column('summary', sa.Text(), nullable=True),
        sa.Column('is_archived', sa.Boolean(), nullable=False, server_default=sa.text('false'), index=True),
        sa.Column('message_count', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('last_message_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('metadata_payload', JSONB, nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )

    op.create_table(
        'assistant_messages',
        sa.Column('id', UUID(as_uuid=True), primary_key=True),
        sa.Column('conversation_id', UUID(as_uuid=True), sa.ForeignKey('assistant_conversations.id', ondelete='CASCADE'), nullable=False, index=True),
        sa.Column('user_id', UUID(as_uuid=True), sa.ForeignKey('users.id', ondelete='CASCADE'), nullable=False, index=True),
        sa.Column('role', sa.String(32), nullable=False),
        sa.Column('content', sa.Text(), nullable=False),
        sa.Column('grounded_evidence_payload', JSONB, nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column('structured_response_payload', JSONB, nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column('anti_hallucination_verified', sa.Boolean(), nullable=False, server_default=sa.text('true')),
        sa.Column('model_provider', sa.String(64), nullable=True),
        sa.Column('model_name', sa.String(64), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )

    # 9. Natural-Language Analytics Workspace
    op.create_table(
        'saved_analytics_queries',
        sa.Column('id', UUID(as_uuid=True), primary_key=True),
        sa.Column('user_id', UUID(as_uuid=True), sa.ForeignKey('users.id', ondelete='CASCADE'), nullable=False, index=True),
        sa.Column('title', sa.String(255), nullable=False),
        sa.Column('query_text', sa.String(1000), nullable=False),
        sa.Column('target_domain', sa.String(64), nullable=False, server_default='GENERAL', index=True),
        sa.Column('is_favorite', sa.Boolean(), nullable=False, server_default=sa.text('false'), index=True),
        sa.Column('plan_snapshot', JSONB, nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column('last_run_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )


def downgrade() -> None:
    op.drop_table('saved_analytics_queries')
    op.drop_table('assistant_messages')
    op.drop_table('assistant_conversations')
    op.drop_table('behavioral_milestone_records')
    op.drop_table('behavioral_trend_aggregates')
    op.drop_table('behavioral_daily_metrics')
    op.drop_table('forecast_scenario_comparisons')
    op.drop_table('milestone_forecasts')
    op.drop_table('project_forecasts')
    op.drop_table('task_dependency_audit_logs')
    op.drop_table('task_dependencies')
    op.drop_table('project_progress_snapshots')
    op.drop_table('goal_progress_snapshots')
    op.drop_table('project_goal_associations')
    op.drop_table('goal_task_associations')
    op.drop_table('behavioral_memory_corrections')
    op.drop_table('behavioral_memory_snapshots')
    op.drop_table('behavioral_memories')
    op.drop_table('knowledge_graph_versions')
    op.drop_table('knowledge_evidence')
    op.drop_table('knowledge_graph_edges')
    op.drop_table('knowledge_graph_nodes')
    op.drop_table('milestones')
    op.drop_table('goals')
    op.drop_table('projects')
