import React from 'react';
import {
  View,
  Text,
  StyleSheet,
  FlatList,
  SafeAreaView,
  TouchableOpacity,
  Switch,
  RefreshControl,
} from 'react-native';
import { Header } from '../../components/Header';
import { Card } from '../../components/Card';
import { Badge } from '../../components/Badge';
import { EmptyState } from '../../components/EmptyState';
import { useNotifications } from '../../hooks/useNotifications';
import { MobileNotification } from '../../services/notificationService';

export const NotificationsScreen: React.FC = () => {
  const {
    notifications,
    preferences,
    isLoading,
    refreshNotifications,
    acknowledge,
    dismiss,
    updateQuietHours,
  } = useNotifications();

  const handleToggleQuietHours = (value: boolean) => {
    updateQuietHours(value);
  };

  const renderNotificationItem = ({ item }: { item: MobileNotification }) => {
    return (
      <Card style={[styles.notifCard, item.is_read && styles.readCard]}>
        <View style={styles.topRow}>
          <Badge
            label={item.category.replace('_', ' ')}
            variant={item.priority === 'CRITICAL' ? 'danger' : 'indigo'}
          />
          <Text style={styles.timeText}>
            {new Date(item.created_at).toLocaleTimeString([], {
              hour: '2-digit',
              minute: '2-digit',
            })}
          </Text>
        </View>

        <Text style={[styles.title, item.is_read && styles.readText]}>{item.title}</Text>
        <Text style={styles.message}>{item.message}</Text>

        {!item.is_read && (
          <View style={styles.actionRow}>
            <TouchableOpacity
              style={styles.ackBtn}
              onPress={() => acknowledge(item.id)}
            >
              <Text style={styles.ackText}>✓ Acknowledge</Text>
            </TouchableOpacity>

            <TouchableOpacity
              style={styles.dismissBtn}
              onPress={() => dismiss(item.id)}
            >
              <Text style={styles.dismissText}>Dismiss</Text>
            </TouchableOpacity>
          </View>
        )}
      </Card>
    );
  };

  return (
    <SafeAreaView style={styles.safeArea}>
      <Header
        title="Notifications"
        subtitle="Intelligent cognitive load suppression & alerts"
      />

      {/* Quiet Hours Banner */}
      <View style={styles.quietHoursCard}>
        <View style={styles.quietHoursRow}>
          <View style={styles.quietHoursInfo}>
            <Text style={styles.quietHoursTitle}>Cognitive Quiet Hours</Text>
            <Text style={styles.quietHoursSubtitle}>
              {preferences?.quiet_hours_enabled
                ? `Active (${preferences.quiet_hours_start} — ${preferences.quiet_hours_end}). Non-critical alerts muted.`
                : 'Quiet hours disabled. Standard notifications active.'}
            </Text>
          </View>
          <Switch
            value={preferences?.quiet_hours_enabled ?? true}
            onValueChange={handleToggleQuietHours}
            trackColor={{ false: '#3f3f46', true: '#4f46e5' }}
            thumbColor="#ffffff"
          />
        </View>
      </View>

      <FlatList
        data={notifications}
        keyExtractor={item => item.id}
        renderItem={renderNotificationItem}
        contentContainerStyle={styles.listContainer}
        refreshControl={
          <RefreshControl
            refreshing={isLoading}
            onRefresh={refreshNotifications}
            tintColor="#6366f1"
          />
        }
        ListEmptyComponent={
          <EmptyState
            title="Notification Inbox Clear"
            message="No alerts currently waiting. Non-essential notifications are suppressed during deep focus sessions."
          />
        }
      />
    </SafeAreaView>
  );
};

const styles = StyleSheet.create({
  safeArea: {
    flex: 1,
    backgroundColor: '#09090b',
  },
  quietHoursCard: {
    backgroundColor: '#18181b',
    borderBottomWidth: 1,
    borderBottomColor: '#27272a',
    padding: 16,
  },
  quietHoursRow: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
  },
  quietHoursInfo: {
    flex: 1,
    marginRight: 12,
  },
  quietHoursTitle: {
    fontSize: 14,
    fontWeight: '700',
    color: '#ffffff',
  },
  quietHoursSubtitle: {
    fontSize: 12,
    color: '#a1a1aa',
    marginTop: 2,
  },
  listContainer: {
    padding: 16,
    paddingBottom: 40,
  },
  notifCard: {
    padding: 14,
  },
  readCard: {
    opacity: 0.65,
    backgroundColor: '#121215',
  },
  topRow: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    marginBottom: 6,
  },
  timeText: {
    fontSize: 11,
    color: '#71717a',
  },
  title: {
    fontSize: 15,
    fontWeight: '700',
    color: '#f4f4f5',
    marginBottom: 4,
  },
  readText: {
    color: '#a1a1aa',
  },
  message: {
    fontSize: 13,
    color: '#d4d4d8',
    lineHeight: 18,
  },
  actionRow: {
    flexDirection: 'row',
    marginTop: 10,
    gap: 8,
  },
  ackBtn: {
    backgroundColor: '#064e3b',
    paddingVertical: 6,
    paddingHorizontal: 12,
    borderRadius: 6,
  },
  ackText: {
    color: '#34d399',
    fontSize: 12,
    fontWeight: '600',
  },
  dismissBtn: {
    backgroundColor: '#27272a',
    paddingVertical: 6,
    paddingHorizontal: 12,
    borderRadius: 6,
  },
  dismissText: {
    color: '#a1a1aa',
    fontSize: 12,
    fontWeight: '600',
  },
});
