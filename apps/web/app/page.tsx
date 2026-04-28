import Link from 'next/link';
import { getDataQuality, getOverview, getReportRankings, getReportRows, getStrategyRuns, getSummaryRows } from '@/lib/artifacts';
import { formatDays, formatKrwMillions, formatPercent } from '@/lib/format';

export default function HomePage() {
  const reports = getReportRows();
  const quality = getDataQuality();
  const summaries = getSummaryRows();
  const overview = getOverview();
  const rankings = getReportRankings();
  const strategies = getStrategyRuns();
  const bestPersona = summaries.find((row) => row.persona === 'smic_follower_v2') ?? summaries[0];
  const bestStrategy = strategies.runs.find((run) => run.run_id === strategies.best_run_id) ?? strategies.runs[0];
  const topWinner = rankings.top_winners?.[0];
  const hitRate = reports.filter((report) => report.targetHit).length / Math.max(1, reports.length);

  return (
    <>
      <section className="hero dashboard-hero">
        <div className="eyebrow">SNUSMIC 정적 리서치 대시보드</div>
        <h1>리포트 추천을 가격 경로와 전략 성과로 검증합니다.</h1>
        <p>
          PDF 추출 → 목표가 정규화 → 가격 매칭 → 시뮬레이션까지는 파이썬이 수행하고,
          이 웹 앱은 커밋된 artifact만 읽어 투자 가설·성과·데이터 품질을 한국어로 설명합니다.
        </p>
        <div className="action-row">
          <Link className="button" href="/insights">핵심 인사이트 보기</Link>
          <Link className="button secondary" href="/reports">리포트 탐색</Link>
        </div>
      </section>

      <section className="grid cards" style={{ marginBottom: '1rem' }}>
        <div className="card"><div className="muted">가격 매칭 리포트</div><div className="metric">{reports.length}</div><p>전체 추출 {quality.extractedReports.toLocaleString('ko-KR')}건 중 시뮬레이션 가능 표본</p></div>
        <div className="card"><div className="muted">목표가 도달률</div><div className="metric good">{formatPercent(hitRate)}</div><p>평균 도달 기간 {formatDays(overview.target_stats?.avg_days_to_target)}</p></div>
        <div className="card"><div className="muted">SMIC 실전형 베이스라인</div><div className="metric">{bestPersona?.persona ?? '—'}</div><p>{bestPersona ? formatKrwMillions(bestPersona.finalEquityKrw) : '시뮬레이션 artifact 필요'}</p></div>
        <div className="card"><div className="muted">최상위 전략 후보</div><div className="metric">#{bestStrategy?.trial_number ?? '—'}</div><p>{bestStrategy ? formatPercent(bestStrategy.metrics.score, 1) : '전략 artifact 필요'}</p></div>
      </section>

      <section className="grid two-col">
        <article className="panel">
          <div className="eyebrow">Best evidence</div>
          <h2>가장 강한 리포트 성과</h2>
          {topWinner ? (
            <p>
              <Link href={`/reports/${topWinner.report_id}`}>{topWinner.company}</Link> 리포트는 발간가 대비 현재 수익률이
              <span className="good"> {formatPercent(topWinner.current_return)}</span> 입니다. 목표가 도달 여부, 고점/저점,
              원문 근거는 상세 페이지에서 확인할 수 있습니다.
            </p>
          ) : <p>랭킹 artifact가 없습니다.</p>}
        </article>
        <article className="panel">
          <div className="eyebrow">Data honesty</div>
          <h2>제외와 결측을 숨기지 않습니다</h2>
          <p>
            가격 미매칭 심볼 {quality.missingPriceSymbols.toLocaleString('ko-KR')}개, 성과 미생성 리포트
            {(overview.report_counts?.missing_price_symbols ?? 0).toLocaleString('ko-KR')}개를 별도 페이지에서 공개합니다.
          </p>
          <p><Link href="/data-quality">데이터 품질 점검 →</Link></p>
        </article>
      </section>
    </>
  );
}
