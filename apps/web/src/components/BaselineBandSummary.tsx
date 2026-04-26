import type { BaselineBandStats } from '../lib/baseline';
import { pct } from '../lib/format';

export function BaselineBandSummary({ stats, strategyName }: { stats: BaselineBandStats; strategyName: string }) {
  return (
    <section className="baseline-band" aria-label="스믹 추종자와 예언자 사이의 baseline band 요약">
      <div className="baseline-copy">
        <p className="eyebrow">Baseline band</p>
        <h2>스믹 추종자보다 낫고, 예언자보다 겸손하게</h2>
        <p>
          목표는 예언자를 이기는 것이 아니라, 스믹 추종자보다 일관되게 나은 전략을 찾는 것이다. 현재
          선택 전략 <b>{strategyName}</b>을 리포트별 baseline band 안에서 읽습니다.
        </p>
      </div>
      <div className="baseline-rail" role="list" aria-label="baseline band 핵심 수익률">
        <BaselineCard
          label="스믹 추종자"
          value={pct(stats.followerAverage)}
          caption={`${stats.sampleSize.toLocaleString('ko-KR')}개 리포트 평균`}
        />
        <BaselineCard
          label="선택 전략"
          value={pct(stats.modelReturn)}
          caption={`추종자 대비 ${signedPct(stats.modelVsFollowerAlpha)}`}
          featured
        />
        <BaselineCard
          label="예언자 상한"
          value={pct(stats.oracleAverage)}
          caption={`남은 상한 격차 ${signedPct(stats.oracleGap)}`}
        />
      </div>
      <div className="baseline-footnote">
        <span>Oracle capture</span>
        <strong>{pct(stats.oracleCaptureRatio)}</strong>
        <small>추종자→예언자 구간 중 선택 전략이 확보한 비율</small>
      </div>
    </section>
  );
}

function BaselineCard({
  label,
  value,
  caption,
  featured = false,
}: {
  label: string;
  value: string;
  caption: string;
  featured?: boolean;
}) {
  return (
    <article className={featured ? 'baseline-card featured' : 'baseline-card'} role="listitem">
      <span>{label}</span>
      <strong>{value}</strong>
      <small>{caption}</small>
    </article>
  );
}

function signedPct(value: number | null): string {
  if (value === null) return '-';
  return `${value >= 0 ? '+' : ''}${pct(value)}`;
}
