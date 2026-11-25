import React, { useState } from 'react';
import {
  Modal,
  View,
  Text,
  StyleSheet,
  TouchableOpacity,
  ScrollView,
  Alert,
} from 'react-native';
import { Input } from '../../components/Input';
import { Button } from '../../components/Button';

interface TaskCreateModalProps {
  visible: boolean;
  onClose: () => void;
  onCreate: (task: {
    title: string;
    description?: string;
    priority: 'LOW' | 'MEDIUM' | 'HIGH' | 'URGENT';
    estimated_duration_minutes: number;
  }) => Promise<any>;
}

export const TaskCreateModal: React.FC<TaskCreateModalProps> = ({
  visible,
  onClose,
  onCreate,
}) => {
  const [title, setTitle] = useState('');
  const [description, setDescription] = useState('');
  const [priority, setPriority] = useState<'LOW' | 'MEDIUM' | 'HIGH' | 'URGENT'>('MEDIUM');
  const [duration, setDuration] = useState('30');
  const [isLoading, setIsLoading] = useState(false);

  const handleSubmit = async () => {
    if (!title.trim()) {
      Alert.alert('Validation Error', 'Task title is required.');
      return;
    }
    setIsLoading(true);
    try {
      await onCreate({
        title: title.trim(),
        description: description.trim() || undefined,
        priority,
        estimated_duration_minutes: parseInt(duration, 10) || 30,
      });
      setTitle('');
      setDescription('');
      setPriority('MEDIUM');
      setDuration('30');
      onClose();
    } catch (err: any) {
      Alert.alert('Error', err.message || 'Failed to create task');
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <Modal visible={visible} animationType="slide" transparent>
      <View style={styles.overlay}>
        <View style={styles.modalContent}>
          <View style={styles.headerRow}>
            <Text style={styles.modalTitle}>New Focus Task</Text>
            <TouchableOpacity onPress={onClose}>
              <Text style={styles.closeBtn}>✕</Text>
            </TouchableOpacity>
          </View>

          <ScrollView style={styles.formScroll}>
            <Input
              label="Task Title"
              value={title}
              onChangeText={setTitle}
              placeholder="e.g. Design API architecture"
            />

            <Input
              label="Description / Context"
              value={description}
              onChangeText={setDescription}
              placeholder="Optional background notes..."
              multiline
              numberOfLines={3}
            />

            <Text style={styles.sectionLabel}>Priority Tier</Text>
            <View style={styles.priorityRow}>
              {(['LOW', 'MEDIUM', 'HIGH', 'URGENT'] as const).map(p => (
                <TouchableOpacity
                  key={p}
                  style={[
                    styles.priorityPill,
                    priority === p && styles.priorityPillActive,
                  ]}
                  onPress={() => setPriority(p)}
                >
                  <Text
                    style={[
                      styles.priorityPillText,
                      priority === p && styles.priorityPillTextActive,
                    ]}
                  >
                    {p}
                  </Text>
                </TouchableOpacity>
              ))}
            </View>

            <Input
              label="Estimated Duration (Minutes)"
              value={duration}
              onChangeText={setDuration}
              keyboardType="number-pad"
              placeholder="30"
            />

            <Button
              title="Create Task"
              onPress={handleSubmit}
              isLoading={isLoading}
              style={styles.submitBtn}
            />
          </ScrollView>
        </View>
      </View>
    </Modal>
  );
};

const styles = StyleSheet.create({
  overlay: {
    flex: 1,
    backgroundColor: 'rgba(0,0,0,0.7)',
    justifyContent: 'flex-end',
  },
  modalContent: {
    backgroundColor: '#18181b',
    borderTopLeftRadius: 20,
    borderTopRightRadius: 20,
    padding: 20,
    maxHeight: '85%',
  },
  headerRow: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    marginBottom: 16,
  },
  modalTitle: {
    fontSize: 18,
    fontWeight: '700',
    color: '#ffffff',
  },
  closeBtn: {
    fontSize: 18,
    color: '#a1a1aa',
    padding: 4,
  },
  formScroll: {
    marginBottom: 20,
  },
  sectionLabel: {
    color: '#d4d4d8',
    fontSize: 13,
    fontWeight: '500',
    marginTop: 8,
    marginBottom: 6,
  },
  priorityRow: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    marginBottom: 12,
  },
  priorityPill: {
    flex: 1,
    paddingVertical: 8,
    marginHorizontal: 3,
    borderRadius: 8,
    backgroundColor: '#27272a',
    alignItems: 'center',
  },
  priorityPillActive: {
    backgroundColor: '#4f46e5',
  },
  priorityPillText: {
    fontSize: 11,
    fontWeight: '600',
    color: '#a1a1aa',
  },
  priorityPillTextActive: {
    color: '#ffffff',
  },
  submitBtn: {
    marginTop: 20,
  },
});
