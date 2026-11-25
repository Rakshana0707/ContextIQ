import React from 'react';
import {
  View,
  Text,
  StyleSheet,
  FlatList,
  SafeAreaView,
  RefreshControl,
  Alert,
} from 'react-native';
import { Header } from '../../components/Header';
import { EmptyState } from '../../components/EmptyState';
import { InterventionCard } from '../interventions/InterventionCard';
import { useRecommendations } from '../../hooks/useRecommendations';
import { MobileIntervention } from '../../services/recommendationService';

export const RecommendationsScreen: React.FC = () => {
  const {
    recommendations,
    isLoading,
    refreshRecommendations,
    accept,
    dismiss,
    defer,
  } = useRecommendations();

  const handleAccept = async (id: string) => {
    try {
      await accept(id);
      Alert.alert('Accepted', 'Intervention accepted! Contextual reinforcement updated.');
    } catch (err: any) {
      Alert.alert('Error', err.message || 'Failed to accept recommendation');
    }
  };

  const handleDismiss = async (id: string) => {
    try {
      await dismiss(id);
    } catch (err: any) {
      Alert.alert('Error', err.message || 'Failed to dismiss recommendation');
    }
  };

  const handleDefer = async (id: string) => {
    try {
      await defer(id, 30);
      Alert.alert('Deferred', 'Recommendation postponed for 30 minutes.');
    } catch (err: any) {
      Alert.alert('Error', err.message || 'Failed to defer recommendation');
    }
  };

  return (
    <SafeAreaView style={styles.safeArea}>
      <Header
        title="Recommendations"
        subtitle="Contextual bandit adaptive interventions"
      />

      <FlatList
        data={recommendations}
        keyExtractor={item => item.id}
        renderItem={({ item }: { item: MobileIntervention }) => (
          <InterventionCard
            intervention={item}
            onAccept={handleAccept}
            onDismiss={handleDismiss}
            onDefer={handleDefer}
          />
        )}
        contentContainerStyle={styles.listContainer}
        refreshControl={
          <RefreshControl
            refreshing={isLoading}
            onRefresh={refreshRecommendations}
            tintColor="#6366f1"
          />
        }
        ListEmptyComponent={
          <EmptyState
            title="All Recommendations Addressed"
            message="No active interventions pending. The bandit engine is continuously monitoring your context and cognitive load."
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
  listContainer: {
    padding: 16,
    paddingBottom: 40,
  },
});
