import * as fs from 'fs';
import * as path from 'path';

describe('Mobile Design System Components Verification (Phase 5.6 Task 10)', () => {
  const componentsDir = path.resolve(__dirname, '../components');

  test('all required design system component files exist and export React components', () => {
    const requiredComponents = [
      'Card.tsx',
      'Badge.tsx',
      'RiskBadge.tsx',
      'StatCard.tsx',
      'Button.tsx',
      'EmptyState.tsx',
      'Input.tsx',
      'Header.tsx',
    ];

    for (const comp of requiredComponents) {
      const fullPath = path.join(componentsDir, comp);
      expect(fs.existsSync(fullPath)).toBe(true);

      const content = fs.readFileSync(fullPath, 'utf8');
      expect(content).toContain('export const');
      expect(content).toContain('React.FC');
    }
  });

  test('RiskBadge component implements correct forgetting risk thresholds', () => {
    const content = fs.readFileSync(path.join(componentsDir, 'RiskBadge.tsx'), 'utf8');
    expect(content).toContain('prob >= 0.7');
    expect(content).toContain('High Risk');
    expect(content).toContain('Low Risk');
  });

  test('Button component implements primary, secondary, outline, and danger variants', () => {
    const content = fs.readFileSync(path.join(componentsDir, 'Button.tsx'), 'utf8');
    expect(content).toContain('primary');
    expect(content).toContain('secondary');
    expect(content).toContain('outline');
    expect(content).toContain('danger');
    expect(content).toContain('ActivityIndicator');
  });

  test('Badge component implements cognitive theme variants', () => {
    const content = fs.readFileSync(path.join(componentsDir, 'Badge.tsx'), 'utf8');
    expect(content).toContain('success');
    expect(content).toContain('warning');
    expect(content).toContain('danger');
    expect(content).toContain('indigo');
  });
});
