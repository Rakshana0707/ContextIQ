import React, { useState } from 'react';
import { View, Text, StyleSheet, TouchableOpacity, SafeAreaView } from 'react-native';
import { useAuth } from '../hooks/useAuth';
import { LoginScreen } from '../features/authentication/LoginScreen';
import { RegisterScreen } from '../features/authentication/RegisterScreen';
import { DashboardScreen } from '../features/dashboard/DashboardScreen';
import { TaskListScreen } from '../features/tasks/TaskListScreen';
import { CalendarScreen } from '../features/calendar/CalendarScreen';
import { RecommendationsScreen } from '../features/recommendations/RecommendationsScreen';
import { NotificationsScreen } from '../features/notifications/NotificationsScreen';
import { ProfileScreen } from '../features/profile/ProfileScreen';
import { SettingsScreen } from '../features/settings/SettingsScreen';

type TabName = 'Dashboard' | 'Tasks' | 'Calendar' | 'Nudges' | 'Alerts' | 'Profile' | 'Settings';

export const AppNavigator: React.FC = () => {
  const { isAuthenticated, isLoading } = useAuth();
  const [authView, setAuthView] = useState<'login' | 'register'>('login');
  const [activeTab, setActiveTab] = useState<TabName>('Dashboard');

  if (isLoading) {
    return (
      <SafeAreaView style={styles.loadingContainer}>
        <Text style={styles.loadingText}>Initializing ContextIQ Mobile...</Text>
      </SafeAreaView>
    );
  }

  if (!isAuthenticated) {
    if (authView === 'register') {
      return <RegisterScreen onNavigateToLogin={() => setAuthView('login')} />;
    }
    return <LoginScreen onNavigateToRegister={() => setAuthView('register')} />;
  }

  const renderActiveScreen = () => {
    switch (activeTab) {
      case 'Dashboard':
        return (
          <DashboardScreen
            onNavigateToTasks={() => setActiveTab('Tasks')}
            onNavigateToRecommendations={() => setActiveTab('Nudges')}
            onNavigateToCalendar={() => setActiveTab('Calendar')}
          />
        );
      case 'Tasks':
        return <TaskListScreen />;
      case 'Calendar':
        return <CalendarScreen />;
      case 'Nudges':
        return <RecommendationsScreen />;
      case 'Alerts':
        return <NotificationsScreen />;
      case 'Profile':
        return <ProfileScreen />;
      case 'Settings':
        return <SettingsScreen />;
      default:
        return (
          <DashboardScreen
            onNavigateToTasks={() => setActiveTab('Tasks')}
            onNavigateToRecommendations={() => setActiveTab('Nudges')}
            onNavigateToCalendar={() => setActiveTab('Calendar')}
          />
        );
    }
  };

  const tabs: { name: TabName; icon: string }[] = [
    { name: 'Dashboard', icon: '📊' },
    { name: 'Tasks', icon: '✓' },
    { name: 'Calendar', icon: '📅' },
    { name: 'Nudges', icon: '⚡' },
    { name: 'Alerts', icon: '🔔' },
    { name: 'Profile', icon: '🧠' },
    { name: 'Settings', icon: '⚙' },
  ];

  return (
    <View style={styles.container}>
      <View style={styles.screenContent}>{renderActiveScreen()}</View>

      {/* Cross-Platform Bottom Navigation Bar */}
      <View style={styles.tabBar}>
        {tabs.map(tab => {
          const isActive = activeTab === tab.name;
          return (
            <TouchableOpacity
              key={tab.name}
              style={styles.tabItem}
              onPress={() => setActiveTab(tab.name)}
              activeOpacity={0.7}
            >
              <Text style={styles.tabIcon}>{tab.icon}</Text>
              <Text style={[styles.tabLabel, isActive && styles.tabLabelActive]}>
                {tab.name}
              </Text>
            </TouchableOpacity>
          );
        })}
      </View>
    </View>
  );
};

const styles = StyleSheet.create({
  container: {
    flex: 1,
    backgroundColor: '#09090b',
  },
  loadingContainer: {
    flex: 1,
    backgroundColor: '#09090b',
    alignItems: 'center',
    justifyContent: 'center',
  },
  loadingText: {
    color: '#818cf8',
    fontSize: 14,
    fontWeight: '600',
  },
  screenContent: {
    flex: 1,
  },
  tabBar: {
    flexDirection: 'row',
    backgroundColor: '#121215',
    borderTopWidth: 1,
    borderTopColor: '#27272a',
    paddingVertical: 8,
    paddingBottom: 14,
  },
  tabItem: {
    flex: 1,
    alignItems: 'center',
    justifyContent: 'center',
  },
  tabIcon: {
    fontSize: 18,
    marginBottom: 2,
  },
  tabLabel: {
    fontSize: 10,
    color: '#71717a',
    fontWeight: '500',
  },
  tabLabelActive: {
    color: '#818cf8',
    fontWeight: '700',
  },
});
