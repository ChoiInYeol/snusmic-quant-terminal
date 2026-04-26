import type { PriceMetric, StrategyRun } from './generated/types';

export type BaselineBandStats = {
  followerAverage: number | null;
  modelReturn: number | null;
  oracleAverage: number | null;
  modelVsFollowerAlpha: number | null;
  oracleGap: number | null;
  oracleCaptureRatio: number | null;
  sampleSize: number;
};

type BaselineMetricInput = Pick<PriceMetric, 'status' | 'smic_follower_return' | 'oracle_return'>;
type StrategyReturnInput = Pick<StrategyRun, 'total_return'> | null | undefined;

function average(values: Array<number | null | undefined>): number | null {
  const finite = values.filter((value): value is number => typeof value === 'number' && Number.isFinite(value));
  if (!finite.length) return null;
  return finite.reduce((sum, value) => sum + value, 0) / finite.length;
}

export function calculateBaselineBandStats(
  metrics: BaselineMetricInput[],
  selectedStrategy: StrategyReturnInput,
): BaselineBandStats {
  const validMetrics = metrics.filter((metric) => metric.status === 'ok');
  const followerAverage = average(validMetrics.map((metric) => metric.smic_follower_return));
  const oracleAverage = average(validMetrics.map((metric) => metric.oracle_return));
  const modelReturn = selectedStrategy?.total_return ?? null;
  const modelVsFollowerAlpha = modelReturn !== null && followerAverage !== null ? modelReturn - followerAverage : null;
  const oracleGap = oracleAverage !== null && modelReturn !== null ? oracleAverage - modelReturn : null;
  const denominator = oracleAverage !== null && followerAverage !== null ? oracleAverage - followerAverage : null;
  const oracleCaptureRatio =
    modelVsFollowerAlpha !== null && denominator !== null && denominator > 0 ? modelVsFollowerAlpha / denominator : null;

  return {
    followerAverage,
    modelReturn,
    oracleAverage,
    modelVsFollowerAlpha,
    oracleGap,
    oracleCaptureRatio,
    sampleSize: validMetrics.length,
  };
}
