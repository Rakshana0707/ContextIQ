import React from 'react';
import { View, Text, StyleSheet } from 'react-native';

interface RiskBadgeProps {
  forgettingRisk?: number; // 0.0 to 1.0
  isUrgent?: boolean;
}

export const RiskBadge: React.FC<RiskBadgeProps> = ({ forgettingRisk, isUrgent }) => {
  const prob = forgettingRisk ?? (isUrgent ? 0.85 : 0.3);
  const percentage = Math.round(prob * 100);

  let label = 'Low Risk';
  let bg = '#14532d'; // green-900
  let color = '#4ade80';

  if (prob >= 0.7 || isUrgent) {
    label = `High Risk (${percentage}%)`;
    bg = '#7f1d1d'; // red-900
    color = '#f87171';
  } else if (prob >= 0.4) {
    label = `Medium (${percentage}%)`;
    bg = '#78350f'; // amber-900
    color = '#fbbf24';
  }

  return (
    <View style={[styles.badge, { backgroundColor: bg }]}>
      <Text style={[styles.text, { color }]}>{label}</Text>
    </View>
  );
};

const styles = StyleSheet.create({
  badge: {
    paddingHorizontal: 8,
    paddingVertical: 2,
    borderRadius: 9999,
    alignSelf: 'flex-start',
  },
  text: {
    fontSize: 10,
    fontWeight: '700',
    letterSpacing: 0.5,
  },
});
