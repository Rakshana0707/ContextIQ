import React, { useState } from 'react';
import {
  View,
  Text,
  StyleSheet,
  FlatList,
  SafeAreaView,
  TouchableOpacity,
  RefreshControl,
  Alert,
} from 'react-native';
import { Header } from '../../components/Header';
import { Card } from '../../components/Card';
import { Badge } from '../../components/Badge';
import { RiskBadge } from '../../components/RiskBadge';
import { Button } from '../../components/Button';
import { EmptyState } from '../../components/EmptyState';
import { TaskCreateModal } from './TaskCreateModal';
import { useTasks } from '../../hooks/useTasks';
import { MobileTask } from '../../services/taskService';

export const TaskListScreen: React.FC = () => {
  const {
    tasks,
    isLoading,
    refreshTasks,
    createTask,
    completeTask,
    postponeTask,
    updatePriority,
  } = useTasks();

  const [filter, setFilter] = useState<'ALL' | 'PENDING' | 'COMPLETED'>('PENDING');
  const [modalVisible, setModalVisible] = useState(false);

  const filteredTasks = tasks.filter(t => {
    if (filter === 'PENDING') return t.status === 'PENDING' || t.status === 'IN_PROGRESS';
    if (filter === 'COMPLETED') return t.status === 'COMPLETED';
    return true;
  });

  const handleComplete = async (taskId: string) => {
    try {
      await completeTask(taskId);
    } catch (err: any) {
      Alert.alert('Error', err.message || 'Failed to complete task');
    }
  };

  const handlePostpone = async (taskId: string) => {
    const tomorrow = new Date(Date.now() + 86400000).toISOString();
    try {
      await postponeTask(taskId, tomorrow);
      Alert.alert('Postponed', 'Task due date extended by 24 hours.');
    } catch (err: any) {
      Alert.alert('Error', err.message || 'Failed to postpone task');
    }
  };

  const renderTaskItem = ({ item }: { item: MobileTask }) => {
    const isCompleted = item.status === 'COMPLETED';

    return (
      <Card style={[styles.taskCard, isCompleted && styles.completedCard]}>
        <View style={styles.topRow}>
          <Text style={[styles.taskTitle, isCompleted && styles.completedText]} numberOfLines={2}>
            {item.title}
          </Text>
          <RiskBadge forgettingRisk={item.forgetting_risk} isUrgent={item.priority === 'URGENT'} />
        </View>

        {item.description ? (
          <Text style={styles.description} numberOfLines={2}>
            {item.description}
          </Text>
        ) : null}

        <View style={styles.metaRow}>
          <Badge
            label={item.priority}
            variant={
              item.priority === 'URGENT'
                ? 'danger'
                : item.priority === 'HIGH'
                ? 'warning'
                : 'default'
            }
          />
          <Text style={styles.durationText}>
            ⏱ {item.estimated_duration_minutes || 30}m
          </Text>
          {item.due_at && (
            <Text style={styles.dueText}>
              📅 {new Date(item.due_at).toLocaleDateString()}
            </Text>
          )}
        </View>

        {!isCompleted && (
          <View style={styles.actionsRow}>
            <TouchableOpacity
              style={[styles.actionBtn, styles.completeBtn]}
              onPress={() => handleComplete(item.id)}
            >
              <Text style={styles.completeBtnText}>✓ Complete</Text>
            </TouchableOpacity>

            <TouchableOpacity
              style={[styles.actionBtn, styles.postponeBtn]}
              onPress={() => handlePostpone(item.id)}
            >
              <Text style={styles.postponeBtnText}>+24h Defer</Text>
            </TouchableOpacity>
          </View>
        )}
      </Card>
    );
  };

  return (
    <SafeAreaView style={styles.safeArea}>
      <Header
        title="Tasks & Micro-Delays"
        subtitle="Forgetting-risk ranking & scheduling"
        rightAction={
          <Button
            title="+ Add Task"
            onPress={() => setModalVisible(true)}
            style={styles.addBtn}
          />
        }
      />

      {/* Filter Tabs */}
      <View style={styles.filterRow}>
        {(['PENDING', 'COMPLETED', 'ALL'] as const).map(tab => (
          <TouchableOpacity
            key={tab}
            style={[styles.filterTab, filter === tab && styles.filterTabActive]}
            onPress={() => setFilter(tab)}
          >
            <Text
              style={[
                styles.filterTabText,
                filter === tab && styles.filterTabTextActive,
              ]}
            >
              {tab}
            </Text>
          </TouchableOpacity>
        ))}
      </View>

      <FlatList
        data={filteredTasks}
        keyExtractor={item => item.id}
        renderItem={renderTaskItem}
        contentContainerStyle={styles.listContainer}
        refreshControl={
          <RefreshControl
            refreshing={isLoading}
            onRefresh={refreshTasks}
            tintColor="#6366f1"
          />
        }
        ListEmptyComponent={
          <EmptyState
            title="No Tasks Found"
            message={
              filter === 'PENDING'
                ? 'All caught up! No pending tasks right now.'
                : 'No tasks match the selected filter.'
            }
            action={
              <Button
                title="Create New Task"
                onPress={() => setModalVisible(true)}
              />
            }
          />
        }
      />

      <TaskCreateModal
        visible={modalVisible}
        onClose={() => setModalVisible(false)}
        onCreate={createTask}
      />
    </SafeAreaView>
  );
};

const styles = StyleSheet.create({
  safeArea: {
    flex: 1,
    backgroundColor: '#09090b',
  },
  listContainer: {
    padding: 16,
    paddingBottom: 32,
  },
  addBtn: {
    paddingVertical: 8,
    paddingHorizontal: 12,
  },
  filterRow: {
    flexDirection: 'row',
    paddingHorizontal: 16,
    paddingVertical: 8,
    backgroundColor: '#121215',
    borderBottomWidth: 1,
    borderBottomColor: '#27272a',
  },
  filterTab: {
    paddingVertical: 6,
    paddingHorizontal: 14,
    borderRadius: 8,
    marginRight: 8,
    backgroundColor: '#18181b',
  },
  filterTabActive: {
    backgroundColor: '#312e81',
  },
  filterTabText: {
    color: '#a1a1aa',
    fontSize: 12,
    fontWeight: '600',
  },
  filterTabTextActive: {
    color: '#ffffff',
  },
  taskCard: {
    padding: 14,
  },
  completedCard: {
    opacity: 0.6,
  },
  topRow: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'flex-start',
  },
  taskTitle: {
    fontSize: 15,
    fontWeight: '600',
    color: '#f4f4f5',
    flex: 1,
    marginRight: 10,
  },
  completedText: {
    textDecorationLine: 'line-through',
    color: '#71717a',
  },
  description: {
    fontSize: 12,
    color: '#a1a1aa',
    marginTop: 6,
    lineHeight: 16,
  },
  metaRow: {
    flexDirection: 'row',
    alignItems: 'center',
    marginTop: 10,
  },
  durationText: {
    fontSize: 11,
    color: '#71717a',
    marginLeft: 10,
  },
  dueText: {
    fontSize: 11,
    color: '#818cf8',
    marginLeft: 10,
  },
  actionsRow: {
    flexDirection: 'row',
    marginTop: 12,
    paddingTop: 10,
    borderTopWidth: 1,
    borderTopColor: '#27272a',
  },
  actionBtn: {
    paddingVertical: 6,
    paddingHorizontal: 12,
    borderRadius: 6,
    marginRight: 8,
  },
  completeBtn: {
    backgroundColor: '#064e3b',
  },
  completeBtnText: {
    color: '#34d399',
    fontSize: 12,
    fontWeight: '600',
  },
  postponeBtn: {
    backgroundColor: '#27272a',
  },
  postponeBtnText: {
    color: '#d4d4d8',
    fontSize: 12,
    fontWeight: '600',
  },
});
