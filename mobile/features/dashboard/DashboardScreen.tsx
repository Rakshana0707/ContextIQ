import React from 'react';
import {
  View,
  Text,
  StyleSheet,
  ScrollView,
  SafeAreaView,
  RefreshControl,
  TouchableOpacity,
} from 'react-native';
import { Header } from '../../components/Header';
import { Card } from '../../components/Card';
import { StatCard } from '../../components/StatCard';
import { RiskBadge } from '../../components/RiskBadge';
import { Badge } from '../../components/Badge';
import { useDashboard } from '../../hooks/useDashboard';

interface DashboardScreenProps {
  onNavigateToTasks: () => void;
  onNavigateToRecommendations: () => void;
  onNavigateToCalendar: () => void;
}

export const DashboardScreen: React.FC<DashboardScreenProps> = ({
  onNavigateToTasks,
  onNavigateToRecommendations,
  onNavigateToCalendar,
}) => {
  const { summary, isLoading, refreshDashboard } = useDashboard();

  return (
    <SafeAreaView style={styles.safeArea}>
      <Header
        title="Behavioral Dashboard"
        subtitle="Real-time cognitive metrics & schedule"
      />

      <ScrollView
        contentContainerStyle={styles.container}
        refreshControl={
          <RefreshControl
            refreshing={isLoading}
            onRefresh={refreshDashboard}
            tintColor="#6366f1"
          />
        }
      >
        {/* Behavioral Friction Index Card */}
        <Card style={styles.bfiCard}>
          <View style={styles.bfiHeader}>
            <Text style={styles.bfiTitle}>Behavioral Friction Index</Text>
            <Badge
              label={summary?.frictionLevel || 'OPTIMAL'}
              variant={
                summary?.frictionLevel === 'OPTIMAL'
                  ? 'success'
                  : summary?.frictionLevel === 'MODERATE'
                  ? 'warning'
                  : 'danger'
              }
            />
          </View>

          <View style={styles.bfiValueContainer}>
            <Text style={styles.bfiScore}>{summary?.behavioralFrictionIndex ?? 32}</Text>
            <Text style={styles.bfiMax}>/ 100</Text>
          </View>

          <Text style={styles.bfiExplanation}>
            {summary?.dailySummary || 'Cognitive disruption is low. Prime window for complex focus tasks.'}
          </Text>
        </Card>

        {/* Quick Metric Stats */}
        <View style={styles.statsRow}>
          <StatCard
            title="High Forgetting Risk"
            value={summary?.highForgettingRiskCount ?? 0}
            subtitle="Needs prompt recall"
            badge="Urgent"
            badgeColor="#ef4444"
          />
          <StatCard
            title="Pending Interventions"
            value={summary?.pendingInterventionsCount ?? 0}
            subtitle="Contextual nudges"
            badge="Adaptive"
            badgeColor="#818cf8"
          />
        </View>

        {/* Focus Window Recommendation */}
        {summary?.activeFocusWindow && (
          <Card style={styles.focusCard}>
            <View style={styles.rowBetween}>
              <Text style={styles.sectionHeader}>Peak Focus Window</Text>
              <Badge label={`Quality ${summary.activeFocusWindow.qualityScore}%`} variant="indigo" />
            </View>
            <Text style={styles.focusTime}>
              {summary.activeFocusWindow.start} — {summary.activeFocusWindow.end}
            </Text>
            <Text style={styles.focusDescription}>
              Optimal cognitive resilience. Recommended for high-concentration deep work.
            </Text>
          </Card>
        )}

        {/* Next Calendar Commitment */}
        {summary?.nextCalendarCommitment && (
          <TouchableOpacity onPress={onNavigateToCalendar} activeOpacity={0.8}>
            <Card style={styles.calendarCard}>
              <View style={styles.rowBetween}>
                <Text style={styles.sectionHeader}>Next Commitment</Text>
                {summary.nextCalendarCommitment.isRecoveryBuffer && (
                  <Badge label="Recovery Buffer" variant="warning" />
                )}
              </View>
              <Text style={styles.eventTitle}>{summary.nextCalendarCommitment.title}</Text>
              <Text style={styles.eventTime}>
                {new Date(summary.nextCalendarCommitment.startTime).toLocaleTimeString([], {
                  hour: '2-digit',
                  minute: '2-digit',
                })}{' '}
                —{' '}
                {new Date(summary.nextCalendarCommitment.endTime).toLocaleTimeString([], {
                  hour: '2-digit',
                  minute: '2-digit',
                })}
              </Text>
            </Card>
          </TouchableOpacity>
        )}

        {/* Today's Tasks Section */}
        <View style={styles.tasksSection}>
          <View style={styles.rowBetween}>
            <Text style={styles.sectionHeader}>Today's Focus Tasks</Text>
            <TouchableOpacity onPress={onNavigateToTasks}>
              <Text style={styles.seeAllText}>View All</Text>
            </TouchableOpacity>
          </View>

          {summary?.todayTasks && summary.todayTasks.length > 0 ? (
            summary.todayTasks.map(t => (
              <Card key={t.id} style={styles.taskCard}>
                <View style={styles.rowBetween}>
                  <Text style={styles.taskTitle} numberOfLines={1}>
                    {t.title}
                  </Text>
                  <RiskBadge isUrgent={t.priority === 'URGENT'} forgettingRisk={t.forgetting_risk} />
                </View>
                <View style={styles.taskMetaRow}>
                  <Badge label={t.priority} variant={t.priority === 'URGENT' ? 'danger' : 'default'} />
                  <Text style={styles.taskDuration}>
                    {t.estimated_duration_minutes || 30} mins
                  </Text>
                </View>
              </Card>
            ))
          ) : (
            <Card>
              <Text style={styles.emptyText}>No pending tasks scheduled for today.</Text>
            </Card>
          )}
        </View>
      </ScrollView>
    </SafeAreaView>
  );
};

const styles = StyleSheet.create({
  safeArea: {
    flex: 1,
    backgroundColor: '#09090b',
  },
  container: {
    padding: 16,
    paddingBottom: 40,
  },
  bfiCard: {
    backgroundColor: '#121218',
    borderColor: '#312e81',
    borderWidth: 1.5,
  },
  bfiHeader: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
  },
  bfiTitle: {
    color: '#c7d2fe',
    fontSize: 14,
    fontWeight: '700',
    letterSpacing: 0.3,
  },
  bfiValueContainer: {
    flexDirection: 'row',
    alignItems: 'baseline',
    marginVertical: 12,
  },
  bfiScore: {
    fontSize: 48,
    fontWeight: '900',
    color: '#ffffff',
  },
  bfiMax: {
    fontSize: 16,
    color: '#71717a',
    marginLeft: 6,
  },
  bfiExplanation: {
    color: '#a1a1aa',
    fontSize: 13,
    lineHeight: 18,
  },
  statsRow: {
    flexDirection: 'row',
    marginHorizontal: -4,
    marginVertical: 6,
  },
  focusCard: {
    borderColor: '#4338ca',
  },
  calendarCard: {
    borderColor: '#27272a',
  },
  rowBetween: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    marginBottom: 6,
  },
  sectionHeader: {
    fontSize: 15,
    fontWeight: '700',
    color: '#e4e4e7',
  },
  focusTime: {
    fontSize: 20,
    fontWeight: '800',
    color: '#ffffff',
    marginVertical: 4,
  },
  focusDescription: {
    fontSize: 12,
    color: '#a1a1aa',
  },
  eventTitle: {
    fontSize: 16,
    fontWeight: '700',
    color: '#f4f4f5',
    marginVertical: 2,
  },
  eventTime: {
    fontSize: 12,
    color: '#818cf8',
    fontWeight: '600',
  },
  tasksSection: {
    marginTop: 12,
  },
  seeAllText: {
    color: '#818cf8',
    fontSize: 13,
    fontWeight: '600',
  },
  taskCard: {
    paddingVertical: 12,
  },
  taskTitle: {
    fontSize: 14,
    fontWeight: '600',
    color: '#ffffff',
    flex: 1,
    marginRight: 8,
  },
  taskMetaRow: {
    flexDirection: 'row',
    alignItems: 'center',
    marginTop: 8,
  },
  taskDuration: {
    color: '#71717a',
    fontSize: 11,
    marginLeft: 8,
  },
  emptyText: {
    color: '#71717a',
    fontSize: 13,
    textAlign: 'center',
    paddingVertical: 8,
  },
});
