import React from 'react';
import { View, Text, StyleSheet } from 'react-native';

interface BadgeProps {
  label: string;
  variant?: 'default' | 'success' | 'warning' | 'danger' | 'indigo';
}

export const Badge: React.FC<BadgeProps> = ({ label, variant = 'default' }) => {
  const getBadgeStyle = () => {
    switch (variant) {
      case 'success':
        return { bg: '#064e3b', text: '#34d399' };
      case 'warning':
        return { bg: '#78350f', text: '#fbbf24' };
      case 'danger':
        return { bg: '#7f1d1d', text: '#f87171' };
      case 'indigo':
        return { bg: '#312e81', text: '#818cf8' };
      default:
        return { bg: '#27272a', text: '#a1a1aa' };
    }
  };

  const colors = getBadgeStyle();

  return (
    <View style={[styles.badge, { backgroundColor: colors.bg }]}>
      <Text style={[styles.text, { color: colors.text }]}>{label}</Text>
    </View>
  );
};

const styles = StyleSheet.create({
  badge: {
    paddingHorizontal: 8,
    paddingVertical: 3,
    borderRadius: 6,
    alignSelf: 'flex-start',
  },
  text: {
    fontSize: 11,
    fontWeight: '600',
    textTransform: 'uppercase',
  },
});
