/**
 * Phase 4 — pre-mortem Scenario 4 mitigation. Renders a red banner when the
 * dashboard's most recent observation is older than ``STALE_THRESHOLD_HOURS``
 * (default 48h). Closes the "Actions pipeline silently stops, dashboard data
 * goes stale, no one notices" failure mode introduced by moving the data
 * pipeline off Vercel and into GitHub Actions.
 *
 * The component is deliberately fail-loud — when ``latestDate`` is null /
 * malformed it falls back to "데이터 시각을 알 수 없음" so a missing run
 * still raises a flag, instead of being silently treated as fresh.
 */

import type { EquityRow } from '../lib/data';

const STALE_THRESHOLD_HOURS = 48;

function newestRunDate(rows: EquityRow[] | null | undefined): Date | null {
  if (!rows || rows.length === 0) return null;
  let newest: number | null = null;
  for (const row of rows) {
    if (!row?.date) continue;
    const ts = Date.parse(row.date);
    if (!Number.isFinite(ts)) continue;
    if (newest === null || ts > newest) newest = ts;
  }
  return newest === null ? null : new Date(newest);
}

export interface StaleDataBannerProps {
  equity: EquityRow[] | null | undefined;
  /** Override "now" for tests. Defaults to ``new Date()`` at render time. */
  now?: Date;
  /** Override the staleness threshold (hours). */
  thresholdHours?: number;
}

export function StaleDataBanner({ equity, now, thresholdHours }: StaleDataBannerProps) {
  const reference = now ?? new Date();
  const threshold = (thresholdHours ?? STALE_THRESHOLD_HOURS) * 60 * 60 * 1000;
  const latest = newestRunDate(equity);

  if (latest === null) {
    return (
      <div role="alert" className="stale-data-banner">
        <strong>Stale data</strong> — 데이터 시각을 알 수 없음. 파이프라인 상태를 점검하세요.
      </div>
    );
  }

  const ageMs = reference.getTime() - latest.getTime();
  if (ageMs <= threshold) return null;

  const ageHours = Math.round(ageMs / (60 * 60 * 1000));
  return (
    <div role="alert" className="stale-data-banner">
      <strong>Stale data (last updated {ageHours}h ago)</strong>
      <span> — 데이터 파이프라인이 멈췄을 수 있습니다.</span>
    </div>
  );
}
