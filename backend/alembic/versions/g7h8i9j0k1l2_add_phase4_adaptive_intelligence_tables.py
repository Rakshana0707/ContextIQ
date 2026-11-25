"""add phase 4 adaptive intelligence tables

Revision ID: g7h8i9j0k1l2
Revises: f6a7b8c9d0e1
Create Date: 2026-11-22 18:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision: str = 'g7h8i9j0k1l2'
down_revision: Union[str, None] = 'f6a7b8c9d0e1'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. user_behavioral_profiles
    op.create_table(
        'user_behavioral_profiles',
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('user_id', sa.UUID(), nullable=False),
        sa.Column('profile_version', sa.String(length=32), nullable=False, server_default='1.0.0'),
        sa.Column('is_cold_start', sa.Boolean(), nullable=False, server_default=sa.text('true')),
        sa.Column('personalization_enabled', sa.Boolean(), nullable=False, server_default=sa.text('true')),
        sa.Column('telemetry_days_observed', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('total_sessions_observed', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('total_tasks_observed', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('total_interruptions_observed', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('focus_dimension', postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column('interruption_dimension', postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column('task_completion_dimension', postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column('context_dimension', postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column('temporal_dimension', postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column('baselines', postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column('global_confidence_score', sa.Float(), nullable=False, server_default='0.0'),
        sa.Column('global_pattern_status', sa.String(length=32), nullable=False, server_default='INSUFFICIENT_EVIDENCE'),
        sa.Column('last_rebuilt_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('user_id')
    )
    op.create_index('ix_behavioral_profiles_user', 'user_behavioral_profiles', ['user_id'], unique=True)
    op.create_index('ix_behavioral_profiles_updated', 'user_behavioral_profiles', ['updated_at'])

    # 2. profile_snapshots
    op.create_table(
        'profile_snapshots',
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('user_id', sa.UUID(), nullable=False),
        sa.Column('profile_version', sa.String(length=32), nullable=False, server_default='1.0.0'),
        sa.Column('snapshot_timestamp', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column('source_data_cutoff', sa.DateTime(timezone=True), nullable=False),
        sa.Column('feature_schema_version', sa.String(length=32), nullable=False, server_default='v4.2'),
        sa.Column('observation_window_days', sa.Integer(), nullable=False, server_default='30'),
        sa.Column('trigger_reason', sa.String(length=64), nullable=False, server_default='INCREMENTAL_BATCH'),
        sa.Column('snapshot_data', postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('ix_profile_snapshots_user_time', 'profile_snapshots', ['user_id', 'snapshot_timestamp'])
    op.create_index('ix_profile_snapshots_user_cutoff', 'profile_snapshots', ['user_id', 'source_data_cutoff'])

    # 3. profile_audit_logs
    op.create_table(
        'profile_audit_logs',
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('user_id', sa.UUID(), nullable=False),
        sa.Column('action', sa.String(length=64), nullable=False),
        sa.Column('actor', sa.String(length=64), nullable=False, server_default='USER'),
        sa.Column('details', postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('ix_profile_audit_logs_user_time', 'profile_audit_logs', ['user_id', 'created_at'])

    # 4. user_focus_windows
    op.create_table(
        'user_focus_windows',
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('user_id', sa.UUID(), nullable=False),
        sa.Column('task_category', sa.String(length=64), nullable=True),
        sa.Column('start_hour_utc', sa.Integer(), nullable=False),
        sa.Column('start_minute_utc', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('duration_minutes', sa.Integer(), nullable=False),
        sa.Column('day_of_week_mask', sa.Integer(), nullable=False, server_default='127'),
        sa.Column('quality_score', sa.Float(), nullable=False),
        sa.Column('completion_rate', sa.Float(), nullable=False),
        sa.Column('interruption_rate_per_hour', sa.Float(), nullable=False),
        sa.Column('resumption_latency_seconds', sa.Float(), nullable=False),
        sa.Column('session_stability_score', sa.Float(), nullable=False),
        sa.Column('sample_session_count', sa.Integer(), nullable=False),
        sa.Column('sample_task_count', sa.Integer(), nullable=False),
        sa.Column('confidence_tier', sa.String(length=32), nullable=False, server_default='EMERGING'),
        sa.Column('is_active', sa.Boolean(), nullable=False, server_default=sa.text('true')),
        sa.Column('is_curated', sa.Boolean(), nullable=False, server_default=sa.text('false')),
        sa.Column('discovery_run_id', sa.String(length=64), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('ix_focus_windows_user_cat', 'user_focus_windows', ['user_id', 'task_category'])
    op.create_index('ix_focus_windows_user_quality', 'user_focus_windows', ['user_id', 'quality_score'])
    op.create_index('ix_focus_windows_user_active', 'user_focus_windows', ['user_id', 'is_active'])

    # 5. task_ranking_feedback
    op.create_table(
        'task_ranking_feedback',
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('user_id', sa.UUID(), nullable=False),
        sa.Column('task_id', sa.UUID(), nullable=False),
        sa.Column('action', sa.String(length=32), nullable=False),
        sa.Column('rank_position', sa.Integer(), nullable=False),
        sa.Column('composite_score', sa.Float(), nullable=False),
        sa.Column('feedback_note', sa.Text(), nullable=True),
        sa.Column('context_snapshot', postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(['task_id'], ['tasks.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('ix_task_ranking_feedback_user', 'task_ranking_feedback', ['user_id'])
    op.create_index('ix_task_ranking_feedback_task', 'task_ranking_feedback', ['task_id'])

    # 6. user_interventions
    op.create_table(
        'user_interventions',
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('user_id', sa.UUID(), nullable=False),
        sa.Column('associated_task_id', sa.UUID(), nullable=True),
        sa.Column('intervention_type', sa.String(length=64), nullable=False),
        sa.Column('intervention_category', sa.String(length=32), nullable=False),
        sa.Column('title', sa.String(length=255), nullable=False),
        sa.Column('message', sa.Text(), nullable=False),
        sa.Column('trigger_condition', sa.String(length=255), nullable=False),
        sa.Column('supporting_evidence', postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column('expected_outcome', sa.String(length=255), nullable=False),
        sa.Column('estimated_effort', sa.String(length=16), nullable=False, server_default='LOW'),
        sa.Column('relevance_score', sa.Float(), nullable=False),
        sa.Column('confidence', sa.Float(), nullable=False, server_default='1.0'),
        sa.Column('lifecycle_status', sa.String(length=32), nullable=False, server_default='GENERATED'),
        sa.Column('creation_timestamp', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column('expiration_timestamp', sa.DateTime(timezone=True), nullable=False),
        sa.Column('deferred_until', sa.DateTime(timezone=True), nullable=True),
        sa.Column('completed_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('user_feedback_note', sa.Text(), nullable=True),
        sa.ForeignKeyConstraint(['associated_task_id'], ['tasks.id'], ondelete='SET NULL'),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('ix_user_interventions_user_status', 'user_interventions', ['user_id', 'lifecycle_status'])
    op.create_index('ix_user_interventions_type', 'user_interventions', ['intervention_type'])
    op.create_index('ix_user_interventions_category', 'user_interventions', ['intervention_category'])

    # 7. bandit_arm_states, bandit_decision_logs, bandit_reward_logs
    op.create_table(
        'bandit_arm_states',
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('user_id', sa.UUID(), nullable=True),
        sa.Column('arm_id', sa.String(length=64), nullable=False),
        sa.Column('policy_type', sa.String(length=32), nullable=False, server_default='LINUCB'),
        sa.Column('pull_count', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('cumulative_reward', sa.Float(), nullable=False, server_default='0.0'),
        sa.Column('a_matrix', postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column('b_vector', postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column('is_quarantined', sa.Boolean(), nullable=False, server_default=sa.text('false')),
        sa.Column('quarantine_reason', sa.String(length=255), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('ix_bandit_arm_states_user_arm', 'bandit_arm_states', ['user_id', 'arm_id'])

    op.create_table(
        'bandit_decision_logs',
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('user_id', sa.UUID(), nullable=False),
        sa.Column('arm_id', sa.String(length=64), nullable=False),
        sa.Column('context_vector', postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column('predicted_payoff', sa.Float(), nullable=False),
        sa.Column('exploration_bonus', sa.Float(), nullable=False),
        sa.Column('selection_probability', sa.Float(), nullable=False),
        sa.Column('intervention_id', sa.UUID(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(['intervention_id'], ['user_interventions.id'], ondelete='SET NULL'),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('ix_bandit_decisions_user_time', 'bandit_decision_logs', ['user_id', 'created_at'])

    op.create_table(
        'bandit_reward_logs',
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('decision_id', sa.UUID(), nullable=False),
        sa.Column('user_id', sa.UUID(), nullable=False),
        sa.Column('reward_value', sa.Float(), nullable=False),
        sa.Column('attribution_component', sa.String(length=64), nullable=False),
        sa.Column('observation_window_minutes', sa.Integer(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(['decision_id'], ['bandit_decision_logs.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('ix_bandit_rewards_user', 'bandit_reward_logs', ['user_id'])

    # 8. intervention_outcomes & intervention_experiments
    op.create_table(
        'intervention_outcomes',
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('intervention_id', sa.UUID(), nullable=False),
        sa.Column('user_id', sa.UUID(), nullable=False),
        sa.Column('is_treated', sa.Boolean(), nullable=False, server_default=sa.text('true')),
        sa.Column('task_completed_within_window', sa.Boolean(), nullable=False, server_default=sa.text('false')),
        sa.Column('completion_latency_seconds', sa.Float(), nullable=True),
        sa.Column('interruption_count_during_window', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('resumption_latency_seconds', sa.Float(), nullable=True),
        sa.Column('bfi_delta', sa.Float(), nullable=False, server_default='0.0'),
        sa.Column('user_rating', sa.Integer(), nullable=True),
        sa.Column('observation_window_minutes', sa.Integer(), nullable=False, server_default='120'),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(['intervention_id'], ['user_interventions.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('ix_intervention_outcomes_user', 'intervention_outcomes', ['user_id'])
    op.create_index('ix_intervention_outcomes_intervention', 'intervention_outcomes', ['intervention_id'])

    op.create_table(
        'intervention_experiments',
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('experiment_name', sa.String(length=128), nullable=False),
        sa.Column('intervention_type', sa.String(length=64), nullable=False),
        sa.Column('sample_size_treated', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('sample_size_control', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('doubly_robust_ate', sa.Float(), nullable=False, server_default='0.0'),
        sa.Column('ci_lower_95', sa.Float(), nullable=False, server_default='0.0'),
        sa.Column('ci_upper_95', sa.Float(), nullable=False, server_default='0.0'),
        sa.Column('p_value', sa.Float(), nullable=False, server_default='1.0'),
        sa.Column('observational_diff', sa.Float(), nullable=False, server_default='0.0'),
        sa.Column('habituation_slope', sa.Float(), nullable=False, server_default='0.0'),
        sa.Column('evaluation_timestamp', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint('id')
    )

    # 9. user_notifications, user_notification_preferences, notification_fatigue_records
    op.create_table(
        'user_notifications',
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('user_id', sa.UUID(), nullable=False),
        sa.Column('intervention_id', sa.UUID(), nullable=True),
        sa.Column('category', sa.String(length=32), nullable=False),
        sa.Column('priority', sa.String(length=16), nullable=False, server_default='MEDIUM'),
        sa.Column('delivery_strategy', sa.String(length=32), nullable=False, server_default='IMMEDIATE'),
        sa.Column('title', sa.String(length=255), nullable=False),
        sa.Column('body', sa.Text(), nullable=False),
        sa.Column('action_url', sa.String(length=255), nullable=True),
        sa.Column('is_read', sa.Boolean(), nullable=False, server_default=sa.text('false')),
        sa.Column('is_dismissed', sa.Boolean(), nullable=False, server_default=sa.text('false')),
        sa.Column('deferred_until', sa.DateTime(timezone=True), nullable=True),
        sa.Column('expires_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(['intervention_id'], ['user_interventions.id'], ondelete='SET NULL'),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('ix_user_notif_user_time', 'user_notifications', ['user_id', 'created_at'])
    op.create_index('ix_user_notif_read', 'user_notifications', ['user_id', 'is_read'])

    op.create_table(
        'user_notification_preferences',
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('user_id', sa.UUID(), nullable=False),
        sa.Column('quiet_hours_enabled', sa.Boolean(), nullable=False, server_default=sa.text('true')),
        sa.Column('quiet_hours_start', sa.String(length=8), nullable=False, server_default='22:00'),
        sa.Column('quiet_hours_end', sa.String(length=8), nullable=False, server_default='08:00'),
        sa.Column('max_hourly_notifications', sa.Integer(), nullable=False, server_default='3'),
        sa.Column('max_daily_notifications', sa.Integer(), nullable=False, server_default='15'),
        sa.Column('category_preferences', postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column('pause_notifications_until', sa.DateTime(timezone=True), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('user_id')
    )

    op.create_table(
        'notification_fatigue_records',
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('user_id', sa.UUID(), nullable=False),
        sa.Column('fatigue_score', sa.Float(), nullable=False, server_default='0.0'),
        sa.Column('rolling_dismiss_rate_7d', sa.Float(), nullable=False, server_default='0.0'),
        sa.Column('rolling_delivery_count_24h', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('last_interaction_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('ix_notif_fatigue_user', 'notification_fatigue_records', ['user_id'])


def downgrade() -> None:
    op.drop_table('notification_fatigue_records')
    op.drop_table('user_notification_preferences')
    op.drop_table('user_notifications')
    op.drop_table('intervention_experiments')
    op.drop_table('intervention_outcomes')
    op.drop_table('bandit_reward_logs')
    op.drop_table('bandit_decision_logs')
    op.drop_table('bandit_arm_states')
    op.drop_table('user_interventions')
    op.drop_table('task_ranking_feedback')
    op.drop_table('user_focus_windows')
    op.drop_table('profile_audit_logs')
    op.drop_table('profile_snapshots')
    op.drop_table('user_behavioral_profiles')
