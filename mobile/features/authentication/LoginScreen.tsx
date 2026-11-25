import React, { useState } from 'react';
import {
  View,
  Text,
  StyleSheet,
  ScrollView,
  SafeAreaView,
  TouchableOpacity,
  Alert,
} from 'react-native';
import { Input } from '../../components/Input';
import { Button } from '../../components/Button';
import { useAuth } from '../../hooks/useAuth';

interface LoginScreenProps {
  onNavigateToRegister: () => void;
}

export const LoginScreen: React.FC<LoginScreenProps> = ({ onNavigateToRegister }) => {
  const [email, setEmail] = useState('demo@contextiq.ai');
  const [password, setPassword] = useState('password123');
  const { login, isLoading, error } = useAuth();

  const handleLogin = async () => {
    if (!email.trim()) {
      Alert.alert('Validation Error', 'Please enter your email.');
      return;
    }
    try {
      await login(email.trim(), password);
    } catch (err: any) {
      Alert.alert('Login Failed', err.message || 'Unable to authenticate with ContextIQ backend.');
    }
  };

  return (
    <SafeAreaView style={styles.safeArea}>
      <ScrollView contentContainerStyle={styles.container}>
        <View style={styles.header}>
          <Text style={styles.appName}>ContextIQ</Text>
          <Text style={styles.tagline}>Behavioral Intelligence & Adaptive Micro-Delay Analytics</Text>
        </View>

        <View style={styles.formCard}>
          <Text style={styles.formTitle}>Sign In</Text>

          {error && <Text style={styles.errorBanner}>{error}</Text>}

          <Input
            label="Email Address"
            value={email}
            onChangeText={setEmail}
            keyboardType="email-address"
            autoCapitalize="none"
            placeholder="you@company.com"
          />

          <Input
            label="Password"
            value={password}
            onChangeText={setPassword}
            secureTextEntry
            placeholder="••••••••••••"
          />

          <Button
            title="Authenticate Session"
            onPress={handleLogin}
            isLoading={isLoading}
            style={styles.submitBtn}
          />

          <View style={styles.footerRow}>
            <Text style={styles.footerText}>New to ContextIQ? </Text>
            <TouchableOpacity onPress={onNavigateToRegister}>
              <Text style={styles.linkText}>Create an Account</Text>
            </TouchableOpacity>
          </View>
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
    flexGrow: 1,
    justifyContent: 'center',
    padding: 24,
  },
  header: {
    alignItems: 'center',
    marginBottom: 32,
  },
  appName: {
    fontSize: 32,
    fontWeight: '900',
    color: '#6366f1',
    letterSpacing: -1,
  },
  tagline: {
    fontSize: 12,
    color: '#71717a',
    textAlign: 'center',
    marginTop: 6,
    maxWidth: 280,
  },
  formCard: {
    backgroundColor: '#18181b',
    borderRadius: 16,
    padding: 24,
    borderWidth: 1,
    borderColor: '#27272a',
  },
  formTitle: {
    fontSize: 20,
    fontWeight: '700',
    color: '#f4f4f5',
    marginBottom: 16,
  },
  errorBanner: {
    backgroundColor: '#7f1d1d',
    color: '#fca5a5',
    padding: 10,
    borderRadius: 8,
    fontSize: 12,
    marginBottom: 12,
  },
  submitBtn: {
    marginTop: 16,
  },
  footerRow: {
    flexDirection: 'row',
    justifyContent: 'center',
    marginTop: 20,
  },
  footerText: {
    color: '#a1a1aa',
    fontSize: 13,
  },
  linkText: {
    color: '#818cf8',
    fontSize: 13,
    fontWeight: '600',
  },
});
