import { MetricCard, Panel, TerminalHero, TerminalLink } from '@/components/ui/Terminal';
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
      <TerminalHero
        eyebrow="Artifact-first Korean terminal"
        title="SMIC 리포트를 검증 가능한 투자 근거로 번역합니다."
        actions={<><TerminalLink href="/reports">리포트 탐색 →</TerminalLink><TerminalLink href="/insights">인사이트 →</TerminalLink><TerminalLink href="/data-quality">품질 점검 →</TerminalLink></>}
      >
        <p>추출 목표가, 발간일 진입가, 실제 가격 경로, 목표가 도달 여부와 데이터 한계를 한 화면에서 확인하는 정적 리서치 터미널입니다.</p>
      </TerminalHero>

      <section className="grid cards">
        <MetricCard label="가격 매칭 리포트" value={reports.length.toLocaleString('ko-KR')} tone="accent" />
        <MetricCard label="목표가 도달률" value={formatPercent(hitRate)} detail={`${overview.target_stats?.target_hit_count ?? reports.filter((report) => report.targetHit).length}건 도달`} tone="good" />
        <MetricCard label="추출 리포트" value={quality.extractedReports.toLocaleString('ko-KR')} detail={`${quality.missingPriceSymbols.toLocaleString('ko-KR')}개 심볼 가격 누락`} />
        <MetricCard label="상위 페르소나" value={bestPersona?.label ?? bestPersona?.persona ?? '—'} detail={bestPersona ? formatKrwMillions(bestPersona.finalEquityKrw) : '시뮬레이션 아티팩트 없음'} tone="warn" />
      </section>

      <section className="grid two-col" style={{ marginTop: '1rem' }}>
        <Panel title="핵심 투자 인사이트">
          <p>최고 수익 리포트는 {topWinner ? `${topWinner.company}(${formatPercent(topWinner.current_return)})` : '—'}입니다.</p>
          <p>목표 도달 중앙 소요일은 {formatDays(overview.target_stats?.median_days_to_target)}이며, 현재 수익률 중앙값은 {formatPercent(overview.target_stats?.median_current_return)}입니다.</p>
          <TerminalLink href="/insights">인사이트 상세 보기 →</TerminalLink>
        </Panel>
        <Panel title="전략 탐색 스냅샷">
          <p>{bestStrategy ? `${bestStrategy.label} 후보가 score ${formatPercent(bestStrategy.metrics.score)}로 표시됩니다.` : '전략 탐색 아티팩트가 없습니다.'}</p>
          <p>Optuna 결과는 인샘플 연구 후보이므로 경고, 파라미터, 데이터 한계와 함께 해석해야 합니다.</p>
          <TerminalLink href="/strategies">전략 리더보드 →</TerminalLink>
        </Panel>
      </section>

      <Panel title="터미널 운영 원칙" className="dense-panel">
        <p>Python 파이프라인은 계산 엔진으로 남기고, Next.js는 커밋된 CSV/JSON/Markdown 결과만 읽습니다. 그래서 Vercel 정적 배포에서도 동일한 스냅샷을 재현할 수 있습니다.</p>
      </Panel>
    </>
  );
}
