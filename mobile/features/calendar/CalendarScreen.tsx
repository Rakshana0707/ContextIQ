import React, { useState, useEffect } from 'react';
import {
  View,
  Text,
  StyleSheet,
  ScrollView,
  SafeAreaView,
  RefreshControl,
} from 'react-native';
import { Header } from '../../components/Header';
import { Card } from '../../components/Card';
import { Badge } from '../../components/Badge';
import { EmptyState } from '../../components/EmptyState';
import { calendarService, MobileCalendarSummary } from '../../services/calendarService';

export const CalendarScreen: React.FC = () => {
  const [calendar, setCalendar] = useState<MobileCalendarSummary | null>(null);
  const [isLoading, setIsLoading] = useState(true);

  const loadCalendar = async () => {
    setIsLoading(true);
    try {
      const data = await calendarService.getCalendarSummary(3);
      setCalendar(data);
    } finally {
      setIsLoading(false);
    }
  };

  useEffect(() => {
    loadCalendar();
  }, []);

  return (
    <SafeAreaView style={styles.safeArea}>
      <Header
        title="Calendar & Focus"
        subtitle="External commitments & recovery buffers"
      />

      <ScrollView
        contentContainerStyle={styles.container}
        refreshControl={
          <RefreshControl
            refreshing={isLoading}
            onRefresh={loadCalendar}
            tintColor="#6366f1"
          />
        }
      >
        <Card style={styles.summaryCard}>
          <Text style={styles.summaryLabel}>Total Available Focus Time</Text>
          <Text style={styles.summaryHours}>
            {Math.round((calendar?.total_available_minutes || 0) / 60)} hours
          </Text>
          <Text style={styles.summarySub}>
            Across working hours (09:00 - 17:00), excluding meetings and 15m post-meeting recovery buffers.
          </Text>
        </Card>

        {/* Busy Blocks & Meetings */}
        <Text style={styles.sectionTitle}>Commitments & Blackout Windows</Text>
        {calendar?.busy_blocks && calendar.busy_blocks.length > 0 ? (
          calendar.busy_blocks.map((block, idx) => (
            <Card
              key={idx}
              style={[
                styles.blockCard,
                block.is_recovery_buffer && styles.recoveryCard,
              ]}
            >
              <View style={styles.rowBetween}>
                <Text style={styles.blockTitle}>{block.title}</Text>
                <Badge
                  label={block.is_recovery_buffer ? 'Recovery Buffer' : block.source}
                  variant={block.is_recovery_buffer ? 'warning' : 'default'}
                />
              </View>
              <Text style={styles.blockTime}>
                {new Date(block.start_time).toLocaleTimeString([], {
                  hour: '2-digit',
                  minute: '2-digit',
                })}{' '}
                —{' '}
                {new Date(block.end_time).toLocaleTimeString([], {
                  hour: '2-digit',
                  minute: '2-digit',
                })}
              </Text>
            </Card>
          ))
        ) : (
          <EmptyState
            title="No Busy Meetings"
            message="No calendar commitments recorded in the current horizon."
          />
        )}

        {/* Focus Windows */}
        <Text style={styles.sectionTitle}>Calculated Deep Work Windows</Text>
        {calendar?.available_windows && calendar.available_windows.length > 0 ? (
          calendar.available_windows.map((win, idx) => (
            <Card key={idx} style={styles.focusCard}>
              <View style={styles.rowBetween}>
                <Text style={styles.focusTitle}>Focus Slot ({win.duration_minutes}m)</Text>
                <Badge
                  label={win.is_peak_focus ? 'Peak Focus' : 'Standard'}
                  variant={win.is_peak_focus ? 'indigo' : 'default'}
                />
              </View>
              <Text style={styles.focusTime}>
                {new Date(win.start_time).toLocaleTimeString([], {
                  hour: '2-digit',
                  minute: '2-digit',
                })}{' '}
                —{' '}
                {new Date(win.end_time).toLocaleTimeString([], {
                  hour: '2-digit',
                  minute: '2-digit',
                })}
              </Text>
            </Card>
          ))
        ) : (
          <EmptyState
            title="No Free Windows"
            message="Calendar is fully occupied with meetings or outside working hours."
          />
        )}
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
  summaryCard: {
    backgroundColor: '#18181b',
    borderColor: '#312e81',
    borderWidth: 1.5,
    marginBottom: 16,
  },
  summaryLabel: {
    fontSize: 12,
    color: '#a5b4fc',
    fontWeight: '700',
    textTransform: 'uppercase',
  },
  summaryHours: {
    fontSize: 32,
    fontWeight: '900',
    color: '#ffffff',
    marginVertical: 4,
  },
  summarySub: {
    fontSize: 12,
    color: '#a1a1aa',
    lineHeight: 16,
  },
  sectionTitle: {
    fontSize: 16,
    fontWeight: '700',
    color: '#f4f4f5',
    marginTop: 16,
    marginBottom: 8,
  },
  blockCard: {
    paddingVertical: 12,
  },
  recoveryCard: {
    borderColor: '#78350f',
    backgroundColor: '#1c1917',
  },
  rowBetween: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    marginBottom: 4,
  },
  blockTitle: {
    fontSize: 14,
    fontWeight: '600',
    color: '#f4f4f5',
    flex: 1,
    marginRight: 8,
  },
  blockTime: {
    fontSize: 12,
    color: '#818cf8',
    fontWeight: '500',
  },
  focusCard: {
    borderColor: '#3730a3',
    paddingVertical: 12,
  },
  focusTitle: {
    fontSize: 14,
    fontWeight: '600',
    color: '#c7d2fe',
  },
  focusTime: {
    fontSize: 12,
    color: '#ffffff',
    fontWeight: '700',
  },
});
