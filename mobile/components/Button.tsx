import React from 'react';
import {
  TouchableOpacity,
  Text,
  ActivityIndicator,
  StyleSheet,
  ViewStyle,
  TextStyle,
} from 'react-native';

interface ButtonProps {
  title: string;
  onPress: () => void;
  variant?: 'primary' | 'secondary' | 'outline' | 'danger';
  isLoading?: boolean;
  disabled?: boolean;
  style?: ViewStyle;
}

export const Button: React.FC<ButtonProps> = ({
  title,
  onPress,
  variant = 'primary',
  isLoading = false,
  disabled = false,
  style,
}) => {
  const getVariantStyles = (): { btn: ViewStyle; text: TextStyle } => {
    switch (variant) {
      case 'secondary':
        return {
          btn: { backgroundColor: '#27272a' },
          text: { color: '#f4f4f5' },
        };
      case 'outline':
        return {
          btn: { backgroundColor: 'transparent', borderWidth: 1, borderColor: '#3f3f46' },
          text: { color: '#e4e4e7' },
        };
      case 'danger':
        return {
          btn: { backgroundColor: '#dc2626' },
          text: { color: '#ffffff' },
        };
      default:
        return {
          btn: { backgroundColor: '#6366f1' }, // indigo-500
          text: { color: '#ffffff' },
        };
    }
  };

  const vStyles = getVariantStyles();

  return (
    <TouchableOpacity
      style={[
        styles.button,
        vStyles.btn,
        (disabled || isLoading) && styles.disabled,
        style,
      ]}
      onPress={onPress}
      disabled={disabled || isLoading}
      activeOpacity={0.7}
    >
      {isLoading ? (
        <ActivityIndicator color={vStyles.text.color} size="small" />
      ) : (
        <Text style={[styles.text, vStyles.text]}>{title}</Text>
      )}
    </TouchableOpacity>
  );
};

const styles = StyleSheet.create({
  button: {
    paddingVertical: 12,
    paddingHorizontal: 16,
    borderRadius: 8,
    alignItems: 'center',
    justifyContent: 'center',
  },
  disabled: {
    opacity: 0.5,
  },
  text: {
    fontSize: 14,
    fontWeight: '600',
  },
});
