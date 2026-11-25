import * as fs from 'fs';
import * as path from 'path';

describe('Mobile App Build & Platform Configuration Verification (Phase 5.6 Task 9 & 10)', () => {
  const mobileDir = path.resolve(__dirname, '..');

  test('app.json contains compliant Android and iOS configuration and permissions', () => {
    const appJsonPath = path.join(mobileDir, 'app.json');
    expect(fs.existsSync(appJsonPath)).toBe(true);

    const appConfig = JSON.parse(fs.readFileSync(appJsonPath, 'utf8'));
    const expo = appConfig.expo;

    // iOS verification
    expect(expo.ios.bundleIdentifier).toBe('com.contextiq.mobile');
    expect(expo.ios.infoPlist.NSLocationWhenInUseUsageDescription).toBeDefined();

    // Android verification
    expect(expo.android.package).toBe('com.contextiq.mobile');
    expect(expo.android.permissions).toContain('POST_NOTIFICATIONS');
    expect(expo.android.permissions).toContain('ACCESS_COARSE_LOCATION');
    expect(expo.android.permissions).toContain('ACCESS_FINE_LOCATION');
    expect(expo.android.permissions).toContain('INTERNET');
  });

  test('package.json contains necessary Expo SDK and navigation dependencies', () => {
    const pkgJsonPath = path.join(mobileDir, 'package.json');
    expect(fs.existsSync(pkgJsonPath)).toBe(true);

    const pkg = JSON.parse(fs.readFileSync(pkgJsonPath, 'utf8'));
    expect(pkg.name).toBe('contextiq-mobile');
    expect(pkg.dependencies.expo).toBeDefined();
    expect(pkg.dependencies['react-native']).toBeDefined();
    expect(pkg.dependencies['expo-secure-store']).toBeDefined();
    expect(pkg.dependencies['expo-notifications']).toBeDefined();
    expect(pkg.dependencies['expo-location']).toBeDefined();
    expect(pkg.dependencies['@react-navigation/native']).toBeDefined();
  });

  test('directory structure adheres to Phase 5.6 modular layout specification', () => {
    const requiredDirs = [
      'components',
      'features/authentication',
      'features/dashboard',
      'features/tasks',
      'features/calendar',
      'features/recommendations',
      'features/interventions',
      'features/profile',
      'features/notifications',
      'features/settings',
      'services',
      'hooks',
      'navigation',
      'storage',
      'tests',
    ];

    for (const dir of requiredDirs) {
      const fullPath = path.join(mobileDir, dir);
      expect(fs.existsSync(fullPath)).toBe(true);
    }
  });
});
