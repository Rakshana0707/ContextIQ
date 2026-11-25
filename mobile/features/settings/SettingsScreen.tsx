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
import { Header } from '../../components/Header';
import { Card } from '../../components/Card';
import { Button } from '../../components/Button';
import { Input } from '../../components/Input';
import { Badge } from '../../components/Badge';
import { useAuth } from '../../hooks/useAuth';
import { useOfflineSync } from '../../hooks/useOfflineSync';
import { getApiBaseUrl, setApiBaseUrl } from '../../services/apiClient';
import { locationService } from '../../services/locationService';
import { clearAllCachedData } from '../../storage/offlineCache';

export const SettingsScreen: React.FC = () => {
  const { user, deviceId, logout } = useAuth();
  const { queueLength, isSyncing, syncNow } = useOfflineSync();
  const [apiUrl, setApiUrl] = useState(getApiBaseUrl());
  const [locationStatus, setLocationStatus] = useState<string>('Foreground Ready');

  const handleSaveApiUrl = () => {
    if (!apiUrl.trim()) return;
    setApiBaseUrl(apiUrl.trim());
    Alert.alert('Configuration Saved', `API Base URL updated to: ${apiUrl.trim()}`);
  };

  const handleTestLocation = async () => {
    const granted = await locationService.requestForegroundPermissions();
    if (!granted) {
      setLocationStatus('Permission Denied');
      Alert.alert(
        'Location Permission Required',
        'Foreground location permission is required for workplace arrival reminders.'
      );
      return;
    }
    const pos = await locationService.getCurrentPosition();
    if (pos) {
      setLocationStatus(`Fix: ${pos.latitude.toFixed(4)}, ${pos.longitude.toFixed(4)}`);
      const matches = await locationService.checkContextualProximity(pos.latitude, pos.longitude);
      const activeMatch = matches.find(m => m.isWithinGeofence);
      if (activeMatch) {
        Alert.alert('Context Detected', `You are at: ${activeMatch.location.name}`);
      } else {
        Alert.alert('Location Check', 'Foreground position captured. No workplace geofence active at this location.');
      }
    } else {
      setLocationStatus('GPS Signal Unavailable');
    }
  };

  const handlePurgeCache = async () => {
    await clearAllCachedData();
    Alert.alert('Offline Cache Cleared', 'Local task and calendar caches have been purged.');
  };

  const handleLogout = () => {
    Alert.alert('Sign Out', 'Are you sure you want to log out from this device?', [
      { text: 'Cancel', style: 'cancel' },
      { text: 'Log Out', style: 'destructive', onPress: logout },
    ]);
  };

  return (
    <SafeAreaView style={styles.safeArea}>
      <Header title="Settings" subtitle="Device telemetry, synchronization & identity" />

      <ScrollView contentContainerStyle={styles.container}>
        {/* User Identity Card */}
        <Card>
          <Text style={styles.sectionTitle}>User Identity</Text>
          <Text style={styles.userEmail}>{user?.email || 'Authenticated User'}</Text>
          <Text style={styles.deviceIdText}>Hardware Device ID: {deviceId || 'Loading...'}</Text>
        </Card>

        {/* Offline Sync Status */}
        <Card style={styles.syncCard}>
          <View style={styles.rowBetween}>
            <Text style={styles.sectionTitle}>Offline Sync Status</Text>
            <Badge
              label={queueLength > 0 ? `${queueLength} Pending` : 'All Synced'}
              variant={queueLength > 0 ? 'warning' : 'success'}
            />
          </View>
          <Text style={styles.syncText}>
            Local mutations are queued safely and replayed idempotently upon network connection.
          </Text>
          <Button
            title={isSyncing ? 'Replaying Actions...' : 'Sync Pending Actions Now'}
            onPress={syncNow}
            isLoading={isSyncing}
            variant="secondary"
            style={styles.syncBtn}
          />
        </Card>

        {/* Contextual Location Settings */}
        <Card>
          <View style={styles.rowBetween}>
            <Text style={styles.sectionTitle}>Workplace Location Reminders</Text>
            <Badge label={locationStatus} variant="indigo" />
          </View>
          <Text style={styles.settingHelp}>
            Only user-initiated or foreground location is checked. Zero continuous background GPS tracking.
          </Text>
          <Button
            title="Check Current Workplace Geofence"
            onPress={handleTestLocation}
            variant="outline"
            style={styles.locationBtn}
          />
        </Card>

        {/* Backend Configuration */}
        <Card>
          <Text style={styles.sectionTitle}>Backend Connection</Text>
          <Input
            label="API Base URL"
            value={apiUrl}
            onChangeText={setApiUrl}
            placeholder="http://10.0.2.2:8000/api/v1"
          />
          <Button
            title="Update API Endpoint"
            onPress={handleSaveApiUrl}
            variant="secondary"
            style={styles.saveBtn}
          />
        </Card>

        {/* Cache Management */}
        <Card>
          <Text style={styles.sectionTitle}>Storage Management</Text>
          <Button
            title="Clear Local Offline Cache"
            onPress={handlePurgeCache}
            variant="outline"
            style={styles.cacheBtn}
          />
        </Card>

        {/* Sign Out Button */}
        <Button
          title="Sign Out of ContextIQ"
          onPress={handleLogout}
          variant="danger"
          style={styles.logoutBtn}
        />
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
  sectionTitle: {
    fontSize: 14,
    fontWeight: '700',
    color: '#ffffff',
    marginBottom: 4,
  },
  userEmail: {
    fontSize: 16,
    fontWeight: '600',
    color: '#818cf8',
  },
  deviceIdText: {
    fontSize: 11,
    color: '#71717a',
    marginTop: 4,
  },
  syncCard: {
    borderColor: '#3730a3',
  },
  rowBetween: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    marginBottom: 6,
  },
  syncText: {
    fontSize: 12,
    color: '#a1a1aa',
    lineHeight: 16,
  },
  syncBtn: {
    marginTop: 10,
  },
  settingHelp: {
    fontSize: 12,
    color: '#a1a1aa',
    lineHeight: 16,
    marginBottom: 10,
  },
  locationBtn: {
    marginTop: 4,
  },
  saveBtn: {
    marginTop: 8,
  },
  cacheBtn: {
    marginTop: 4,
  },
  logoutBtn: {
    marginTop: 20,
    marginBottom: 30,
  },
});
