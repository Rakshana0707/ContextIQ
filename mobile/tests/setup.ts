import { vi, beforeEach } from 'vitest';

(globalThis as any).jest = vi;
(globalThis as any).fetch = vi.fn();

beforeEach(() => {
  vi.clearAllMocks();
});
