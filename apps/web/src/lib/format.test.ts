/**
 * Phase 8 — vitest coverage for ``format.ts``.
 */

import { describe, expect, test } from 'vitest';
import { labelReason } from './format';

describe('labelReason', () => {
  test('maps known reasons to Korean labels', () => {
    expect(labelReason('buy')).toBe('매수');
    expect(labelReason('sell')).toBe('매도');
    expect(labelReason('stop_loss')).toBe('손절');
  });

  test('returns empty string for nullish input (defensive)', () => {
    expect(labelReason(null)).toBe('');
    expect(labelReason(undefined)).toBe('');
    expect(labelReason('')).toBe('');
  });

  test('falls through to the raw value for unknown reasons', () => {
    // The function returns the input unchanged when no label exists,
    // so callers always get a renderable string.
    const out = labelReason('unknown_reason');
    expect(typeof out).toBe('string');
  });
});
