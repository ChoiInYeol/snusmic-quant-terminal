import { describe, expect, test } from 'vitest';
import { calculateBaselineBandStats } from './baseline';

describe('calculateBaselineBandStats', () => {
  test('summarizes follower, selected model, and oracle returns', () => {
    const stats = calculateBaselineBandStats(
      [
        { status: 'ok', smic_follower_return: 0.1, oracle_return: 0.5 },
        { status: 'ok', smic_follower_return: 0.2, oracle_return: 0.7 },
        { status: 'no_price_history', smic_follower_return: 9, oracle_return: 9 },
      ],
      { total_return: 0.3 },
    );

    expect(stats.sampleSize).toBe(2);
    expect(stats.followerAverage).toBeCloseTo(0.15);
    expect(stats.modelReturn).toBeCloseTo(0.3);
    expect(stats.oracleAverage).toBeCloseTo(0.6);
    expect(stats.modelVsFollowerAlpha).toBeCloseTo(0.15);
    expect(stats.oracleGap).toBeCloseTo(0.3);
    expect(stats.oracleCaptureRatio).toBeCloseTo(1 / 3);
  });

  test('ignores null values and returns null derived values when incomplete', () => {
    const stats = calculateBaselineBandStats(
      [
        { status: 'ok', smic_follower_return: null, oracle_return: 0.4 },
        { status: 'ok', smic_follower_return: null, oracle_return: null },
      ],
      null,
    );

    expect(stats.sampleSize).toBe(2);
    expect(stats.followerAverage).toBeNull();
    expect(stats.modelReturn).toBeNull();
    expect(stats.oracleAverage).toBeCloseTo(0.4);
    expect(stats.modelVsFollowerAlpha).toBeNull();
    expect(stats.oracleGap).toBeNull();
    expect(stats.oracleCaptureRatio).toBeNull();
  });

  test('does not claim oracle capture when the baseline band has no width', () => {
    const stats = calculateBaselineBandStats(
      [{ status: 'ok', smic_follower_return: 0.2, oracle_return: 0.2 }],
      { total_return: 0.25 },
    );

    expect(stats.oracleCaptureRatio).toBeNull();
  });
});
