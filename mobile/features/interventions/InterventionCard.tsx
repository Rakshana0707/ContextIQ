import React, { useState } from 'react';
import { View, Text, StyleSheet, TouchableOpacity } from 'react-native';
import { Card } from '../../components/Card';
import { Badge } from '../../components/Badge';
import { Button } from '../../components/Button';
import { MobileIntervention } from '../../services/recommendationService';

interface InterventionCardProps {
  intervention: MobileIntervention;
  onAccept: (id: string) => void;
  onDismiss: (id: string) => void;
  onDefer: (id: string) => void;
}

export const InterventionCard: React.FC<InterventionCardProps> = ({
  intervention,
  onAccept,
  onDismiss,
  onDefer,
}) => {
  const [showExplanation, setShowExplanation] = useState(false);

  const getCategoryVariant = () => {
    switch (intervention.category) {
      case 'FOCUS':
        return 'indigo';
      case 'RECOVERY':
        return 'success';
      case 'WORKLOAD':
        return 'warning';
      default:
        return 'default';
    }
  };

  return (
    <Card style={styles.card}>
      <View style={styles.headerRow}>
        <Badge label={intervention.category} variant={getCategoryVariant()} />
        <Text style={styles.confidence}>
          Confidence: {Math.round((intervention.confidence_score || 0.85) * 100)}%
        </Text>
      </View>

      <Text style={styles.title}>{intervention.title}</Text>
      <Text style={styles.message}>{intervention.message}</Text>

      {/* Expected Outcome Indicator */}
      {intervention.expected_outcome && (
        <View style={styles.outcomeContainer}>
          <Text style={styles.outcomeLabel}>Expected Cognitive Gain:</Text>
          <Text style={styles.outcomeText}>{intervention.expected_outcome}</Text>
        </View>
      )}

      {/* LinUCB Behavioral Explanation Toggle */}
      <TouchableOpacity
        onPress={() => setShowExplanation(!showExplanation)}
        style={styles.explanationToggle}
      >
        <Text style={styles.explanationToggleText}>
          {showExplanation ? '▼ Hide Behavioral Rationale' : '▶ View Behavioral Rationale'}
        </Text>
      </TouchableOpacity>

      {showExplanation && (
        <View style={styles.explanationBox}>
          <Text style={styles.explanationText}>
            {intervention.rationale ||
              'LinUCB Contextual Bandit selected this arm based on current cognitive fatigue, interruption history, and peak circadian focus alignment.'}
          </Text>
        </View>
      )}

      {/* Action Buttons */}
      <View style={styles.actionRow}>
        <Button
          title="Accept"
          onPress={() => onAccept(intervention.id)}
          style={[styles.btn, styles.acceptBtn]}
        />
        <Button
          title="Defer (+30m)"
          onPress={() => onDefer(intervention.id)}
          variant="secondary"
          style={styles.btn}
        />
        <Button
          title="Dismiss"
          onPress={() => onDismiss(intervention.id)}
          variant="outline"
          style={styles.btn}
        />
      </View>
    </Card>
  );
};

const styles = StyleSheet.create({
  card: {
    borderColor: '#3730a3',
    padding: 16,
    marginVertical: 8,
  },
  headerRow: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    marginBottom: 8,
  },
  confidence: {
    fontSize: 11,
    color: '#818cf8',
    fontWeight: '600',
  },
  title: {
    fontSize: 16,
    fontWeight: '700',
    color: '#ffffff',
    marginBottom: 4,
  },
  message: {
    fontSize: 13,
    color: '#d4d4d8',
    lineHeight: 18,
    marginBottom: 10,
  },
  outcomeContainer: {
    backgroundColor: '#0c0a09',
    padding: 8,
    borderRadius: 6,
    marginBottom: 8,
    borderLeftWidth: 3,
    borderLeftColor: '#34d399',
  },
  outcomeLabel: {
    fontSize: 10,
    fontWeight: '700',
    color: '#34d399',
    textTransform: 'uppercase',
  },
  outcomeText: {
    fontSize: 12,
    color: '#e4e4e7',
    marginTop: 2,
  },
  explanationToggle: {
    paddingVertical: 4,
    marginBottom: 6,
  },
  explanationToggleText: {
    fontSize: 12,
    color: '#a5b4fc',
    fontWeight: '600',
  },
  explanationBox: {
    backgroundColor: '#1e1b4b',
    padding: 10,
    borderRadius: 8,
    marginBottom: 12,
  },
  explanationText: {
    fontSize: 12,
    color: '#c7d2fe',
    lineHeight: 16,
  },
  actionRow: {
    flexDirection: 'row',
    marginTop: 8,
    gap: 8,
  },
  btn: {
    flex: 1,
    paddingVertical: 10,
  },
  acceptBtn: {
    backgroundColor: '#4f46e5',
  },
});
