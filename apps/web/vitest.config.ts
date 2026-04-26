import { defineConfig } from 'vitest/config';

/**
 * Phase 8 — vitest config. Uses jsdom so component tests can read CSS
 * variables / window APIs without a real browser. Coverage is opt-in
 * (``npm run test -- --coverage``); the default ``npm test`` runs only the
 * unit tests so it stays fast on every PR.
 */
export default defineConfig({
  test: {
    environment: 'jsdom',
    include: ['src/**/*.test.{ts,tsx}', 'tests/**/*.test.{ts,tsx}'],
    globals: true,
    coverage: {
      provider: 'v8',
      reporter: ['text', 'lcov'],
      exclude: ['**/generated/**', '**/scripts/**'],
    },
  },
});
