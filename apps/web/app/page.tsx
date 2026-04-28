import Link from 'next/link';
import { CumulativeReturnChart, type ReturnSeries } from '@/components/charts/CumulativeReturnChart';
import { MetricCard, Panel, TerminalHero } from '@/components/ui/Terminal';
import {
  getCurrentHoldings,
  getEquityDaily,
  getLatestReportTargetsBySymbol,
  getPositionEpisodes,
  getReportRows,
  getSummaryRows,
  type HoldingRow,
  type ReportRow,
  type SummaryRow,
} from '@/lib/artifacts';
import { formatDays, formatKrw, formatPercent } from '@/lib/format';

const DEFAULT_PERSONA = 'smic_follower_v2';
const STRATEGY_COLORS: Record<string, string> = {
  smic_follower_v2: '#35f2c2',
  smic_follower: '#d7ff4f',
  all_weather: '#8ab4ff',
};

export default function Home() {
  const personas = getSummaryRows();
  const reports = getReportRows();
  const allHoldings = getCurrentHoldings();
  const targetsBySymbol = getLatestReportTargetsBySymbol();
  const episodes = getPositionEpisodes();
  const equity = getEquityDaily();
  const defaultLabel = getPersonaLabel(personas, DEFAULT_PERSONA);
  const holdings = allHoldings
    .filter((row) => row.persona === DEFAULT_PERSONA)
    .sort((a, b) => (b.marketValueKrw ?? 0) - (a.marketValueKrw ?? 0));
  const portfolio = summarizeHoldings(holdings);
  const v2 = personas.find((row) => row.persona === DEFAULT_PERSONA);
  const v1 = personas.find((row) => row.persona === 'smic_follower');
  const allWeather = personas.find((row) => row.persona === 'all_weather');
  const reportStats = buildReportStats(reports);
  const recentWinningEpisodes = episodes
    .filter((row) => row.persona === DEFAULT_PERSONA && row.status === 'closed' && (row.realizedPnlKrw ?? 0) > 0)
    .sort((a, b) => (b.closeDate ?? '').localeCompare(a.closeDate ?? ''))
    .slice(0, 6);
  const openPositions = episodes
    .filter((row) => row.persona === DEFAULT_PERSONA && row.status !== 'closed')
    .sort((a, b) => (b.unrealizedPnlKrw ?? 0) - (a.unrealizedPnlKrw ?? 0))
    .slice(0, 6);
  const returnSeries = buildReturnSeries(equity, personas);
  const conclusion = buildStrategyConclusion(v2, allWeather, v1);

  return (
    <>
      <TerminalHero eyebrow="Portfolio evidence" title="지금 무엇을 들고 있고, 이 전략은 돈이 됐는가.">
        <p>
          메인 화면은 방법론 설명 대신 {defaultLabel}의 현재 보유, 최근 실현 이익, 리포트 성과 분포,
          전략별 손익/낙폭을 한 번에 검증하도록 재구성했습니다. 면적은 돈이 많이 들어간 종목,
          색상은 손익률입니다.
        </p>
        <div className="action-row">
          <Link className="button-link" href="/portfolio">현재 포트폴리오 보기</Link>
          <Link className="button-link secondary" href="/trades">체결 원장 보기</Link>
          <Link className="button-link secondary" href="/reports">리포트 근거 보기</Link>
        </div>
      </TerminalHero>

      <section className="grid cards bento-metrics" style={{ marginBottom: '1rem' }}>
        <MetricCard label={`${defaultLabel} 평가액`} value={formatKrw(portfolio.marketValue)} detail={`${holdings.length.toLocaleString('ko-KR')}개 보유 · 집중도 ${formatPercent(portfolio.top5Weight)}`} tone="accent" />
        <MetricCard label="현재 미실현 손익" value={formatKrw(portfolio.unrealizedPnl)} detail={formatPercent(portfolio.unrealizedReturn)} tone={portfolio.unrealizedPnl >= 0 ? 'good' : 'bad'} />
        <MetricCard label="전략 누적 손익" value={formatKrw(v2?.netProfitKrw)} detail={`MWR ${formatPercent(v2?.moneyWeightedReturn ?? v2?.irr)} · MDD ${formatPercent(v2?.maxDrawdown)}`} tone={(v2?.netProfitKrw ?? 0) >= 0 ? 'good' : 'bad'} />
        <MetricCard label="리포트 목표 터치율" value={formatPercent(reportStats.hitRate)} detail={`${reportStats.hitCount.toLocaleString('ko-KR')}건 / ${reportStats.count.toLocaleString('ko-KR')}건`} tone="good" />
      </section>

      <section className="grid dashboard-hero-grid" style={{ marginBottom: '1rem' }}>
        <Panel title="현재 포트폴리오 히트맵" className="dashboard-main-panel">
          <div className="panel-caption">면적 = 평가금 · 색상 = 현재 평가손익률 · 기준 전략 = {defaultLabel}</div>
          <PortfolioHeatmap holdings={holdings} />
          <div className="heatmap-legend" aria-label="히트맵 색상 범례">
            <span className="legend-bad">손실</span><span className="legend-neutral">중립</span><span className="legend-good">수익</span>
          </div>
        </Panel>

        <Panel title="전략 유의성 요약">
          <p className={`strategy-verdict ${conclusion.tone}`}>{conclusion.label}</p>
          <p>{conclusion.detail}</p>
          <div className="strategy-score-list">
            {personas.filter((row) => ['smic_follower_v2', 'smic_follower', 'all_weather'].includes(row.persona)).map((row) => (
              <div className="strategy-score-row" key={row.persona}>
                <strong>{row.label ?? row.persona}</strong>
                <span>{formatKrw(row.netProfitKrw)}</span>
                <span>MWR {formatPercent(row.moneyWeightedReturn ?? row.irr)}</span>
                <span>MDD {formatPercent(row.maxDrawdown)}</span>
              </div>
            ))}
          </div>
          <p><Link href="/strategies">전략별 실험/파라미터 보기 →</Link></p>
        </Panel>
      </section>

      <section className="panel" style={{ marginBottom: '1rem' }}>
        <h2>누적 수익률 경로</h2>
        <p className="muted">SMIC Follower v2가 단순 all-weather 대비 어떤 경로와 낙폭으로 움직였는지 비교합니다.</p>
        <CumulativeReturnChart series={returnSeries} />
      </section>

      <section className="grid two-col feature-grid" style={{ marginBottom: '1rem' }}>
        <Panel title="최근 이익 실현 포지션">
          <div className="table-wrap inset compact-table">
            <table>
              <thead><tr><th>청산일</th><th>종목</th><th>보유</th><th>평균 진입/청산</th><th>실현손익</th><th>사유</th></tr></thead>
              <tbody>{recentWinningEpisodes.map((episode) => (
                <tr key={`${episode.persona}-${episode.symbol}-${episode.openDate}-${episode.closeDate}`}>
                  <td>{episode.closeDate ?? '—'}</td>
                  <td><Link href={`/reports/${episode.symbol}`}>{episode.company || episode.symbol}</Link><div className="muted">{episode.symbol}</div></td>
                  <td>{formatDays(episode.holdingDays)}<div className="muted">매수 {episode.buyFills ?? 0}회 · 매도 {episode.sellFills ?? 0}회</div></td>
                  <td>{formatKrw(episode.avgEntryPriceKrw)}<div className="muted">→ {formatKrw(episode.avgExitPriceKrw)}</div></td>
                  <td className="good">{formatKrw(episode.realizedPnlKrw)}<div>{formatPercent(positionReturn(episode.avgEntryPriceKrw, episode.avgExitPriceKrw))}</div></td>
                  <td>{humanReason(episode.exitReasons)}</td>
                </tr>
              ))}</tbody>
            </table>
          </div>
        </Panel>

        <Panel title="현재 열려 있는 큰 포지션">
          <div className="table-wrap inset compact-table">
            <table>
              <thead><tr><th>종목</th><th>목표가</th><th>평균 진입</th><th>최근가</th><th>미실현 손익</th></tr></thead>
              <tbody>{openPositions.map((episode) => {
                const target = targetsBySymbol[episode.symbol];
                return (
                  <tr key={`${episode.persona}-${episode.symbol}-${episode.openDate}`}>
                    <td><Link href={`/reports/${episode.symbol}`}>{episode.company || episode.symbol}</Link><div className="muted">{episode.symbol}</div></td>
                    <td>{formatKrw(target?.targetPriceKrw)}<div className="muted">목표까지 {formatPercent(targetGap(episode.lastCloseKrw, target?.targetPriceKrw))}</div></td>
                    <td>{formatKrw(episode.avgEntryPriceKrw)}</td>
                    <td>{formatKrw(episode.lastCloseKrw)}</td>
                    <td className={(episode.unrealizedPnlKrw ?? 0) >= 0 ? 'good' : 'bad'}>{formatKrw(episode.unrealizedPnlKrw)}</td>
                  </tr>
                );
              })}</tbody>
            </table>
          </div>
        </Panel>
      </section>

      <section className="grid dashboard-stats-grid">
        <Panel title="SMIC 리포트 성과 분포">
          <p className="muted">평균만 보면 왜곡됩니다. 평균과 중앙값, 왜도, 꼬리를 함께 봅니다.</p>
          <DistributionGrid stats={reportStats.distributions} />
        </Panel>
        <Panel title="현재 수익률 히스토그램">
          <Histogram bins={reportStats.currentReturnHistogram} />
          <p className="muted">오른쪽 꼬리가 길수록 소수의 큰 승자가 평균을 끌어올립니다. 중앙값이 낮으면 재현 가능한 매매 방식인지 더 보수적으로 봐야 합니다.</p>
        </Panel>
      </section>
    </>
  );
}

function PortfolioHeatmap({ holdings }: { holdings: HoldingRow[] }) {
  const total = holdings.reduce((sum, row) => sum + Math.max(0, row.marketValueKrw ?? 0), 0);
  if (!holdings.length || total <= 0) return <div className="empty-chart">현재 보유 포지션이 없습니다.</div>;
  return (
    <div className="portfolio-heatmap">
      {holdings.slice(0, 28).map((row) => {
        const value = Math.max(0, row.marketValueKrw ?? 0);
        const weight = value / total;
        const returnPct = row.unrealizedReturn ?? 0;
        return (
          <Link
            href={`/reports/${row.symbol}`}
            className="heatmap-cell"
            key={`${row.persona}-${row.symbol}`}
            style={{
              flexGrow: Math.max(1, Math.round(weight * 1000)),
              flexBasis: `${Math.max(11, Math.min(36, weight * 125))}%`,
              background: returnColor(returnPct),
            }}
          >
            <strong>{row.company || row.symbol}</strong>
            <span>{row.symbol}</span>
            <em>{formatKrw(value)}</em>
            <b className={returnPct >= 0 ? 'good' : 'bad'}>{formatPercent(returnPct)}</b>
          </Link>
        );
      })}
    </div>
  );
}

function DistributionGrid({ stats }: { stats: DistributionStat[] }) {
  return (
    <div className="distribution-grid">
      {stats.map((stat) => (
        <article className="distribution-card" key={stat.label}>
          <div className="muted">{stat.label}</div>
          <div className="distribution-main">평균 {formatStat(stat.mean, stat.kind)}</div>
          <div>중앙값 {formatStat(stat.median, stat.kind)} · P25/P75 {formatStat(stat.p25, stat.kind)} / {formatStat(stat.p75, stat.kind)}</div>
          <div className={stat.skewness !== null && Math.abs(stat.skewness) > 1 ? 'warn' : ''}>왜도 {formatNumber(stat.skewness, 2)} · {skewLabel(stat.skewness)}</div>
        </article>
      ))}
    </div>
  );
}

function Histogram({ bins }: { bins: HistogramBin[] }) {
  const max = Math.max(1, ...bins.map((bin) => bin.count));
  return (
    <div className="histogram" aria-label="현재 수익률 분포 히스토그램">
      {bins.map((bin) => (
        <div className="histogram-row" key={bin.label}>
          <span>{bin.label}</span>
          <div className="histogram-track"><div style={{ width: `${(bin.count / max) * 100}%` }} /></div>
          <strong>{bin.count}</strong>
        </div>
      ))}
    </div>
  );
}

type DistributionStat = { label: string; kind: 'percent' | 'days'; mean: number | null; median: number | null; p25: number | null; p75: number | null; skewness: number | null };
type HistogramBin = { label: string; count: number };

function summarizeHoldings(rows: HoldingRow[]) {
  const marketValue = rows.reduce((sum, row) => sum + (row.marketValueKrw ?? 0), 0);
  const unrealizedPnl = rows.reduce((sum, row) => sum + (row.unrealizedPnlKrw ?? 0), 0);
  const cost = marketValue - unrealizedPnl;
  const top5 = rows.slice(0, 5).reduce((sum, row) => sum + (row.marketValueKrw ?? 0), 0);
  return {
    marketValue,
    unrealizedPnl,
    unrealizedReturn: cost > 0 ? unrealizedPnl / cost : null,
    top5Weight: marketValue > 0 ? top5 / marketValue : null,
  };
}

function buildReportStats(reports: ReportRow[]) {
  const actionable = reports.filter((row) => (row.targetUpsideAtPub ?? 0) > 0 && row.entryPriceKrw !== null);
  const currentReturns = actionable.map((row) => row.currentReturn).filter(isNumber);
  const targetUpsides = actionable.map((row) => row.targetUpsideAtPub).filter(isNumber);
  const daysToTarget = actionable.filter((row) => row.targetHit).map((row) => row.daysToTarget).filter(isNumber);
  const peakReturns = actionable.map((row) => row.peakReturn).filter(isNumber);
  const troughReturns = actionable.map((row) => row.troughReturn).filter(isNumber);
  return {
    count: actionable.length,
    hitCount: actionable.filter((row) => row.targetHit).length,
    hitRate: actionable.filter((row) => row.targetHit).length / Math.max(1, actionable.length),
    distributions: [
      distribution('현재 수익률', currentReturns, 'percent'),
      distribution('제시 업사이드', targetUpsides, 'percent'),
      distribution('목표 도달 소요', daysToTarget, 'days'),
      distribution('발간 후 고점 수익률', peakReturns, 'percent'),
      distribution('발간 후 저점 수익률', troughReturns, 'percent'),
    ],
    currentReturnHistogram: histogram(currentReturns, [-1, -0.5, -0.25, 0, 0.25, 0.5, 1, 2, Number.POSITIVE_INFINITY]),
  };
}

function buildReturnSeries(equity: ReturnType<typeof getEquityDaily>, personas: SummaryRow[]): ReturnSeries[] {
  const labels = new Map(personas.map((row) => [row.persona, row.label ?? row.persona]));
  return ['smic_follower_v2', 'smic_follower', 'all_weather'].map((persona) => ({
    id: persona,
    label: labels.get(persona) ?? persona,
    color: STRATEGY_COLORS[persona] ?? '#cbd5e1',
    points: equity.filter((point) => point.persona === persona && point.cumulativeReturn !== null).map((point) => ({ time: point.date, value: point.cumulativeReturn ?? 0 })),
  }));
}

function distribution(label: string, values: number[], kind: 'percent' | 'days'): DistributionStat {
  const sorted = [...values].sort((a, b) => a - b);
  return {
    label,
    kind,
    mean: mean(sorted),
    median: percentile(sorted, 0.5),
    p25: percentile(sorted, 0.25),
    p75: percentile(sorted, 0.75),
    skewness: skewness(sorted),
  };
}

function histogram(values: number[], edges: number[]): HistogramBin[] {
  return edges.slice(0, -1).map((start, index) => {
    const end = edges[index + 1];
    const count = values.filter((value) => value >= start && value < end).length;
    return { label: `${formatHistogramEdge(start)}~${formatHistogramEdge(end)}`, count };
  });
}

function buildStrategyConclusion(v2: SummaryRow | undefined, benchmark: SummaryRow | undefined, v1: SummaryRow | undefined) {
  const v2Return = v2?.moneyWeightedReturn ?? v2?.irr ?? null;
  const benchmarkReturn = benchmark?.moneyWeightedReturn ?? benchmark?.irr ?? null;
  const v1Return = v1?.moneyWeightedReturn ?? v1?.irr ?? null;
  const beatsBenchmark = v2Return !== null && benchmarkReturn !== null && v2Return > benchmarkReturn;
  const improvesV1 = v2Return !== null && v1Return !== null && v2Return > v1Return;
  if (beatsBenchmark && improvesV1) {
    return { tone: 'good', label: '검증 신호: 기준선과 v1을 모두 상회', detail: `v2 MWR ${formatPercent(v2Return)}가 all-weather ${formatPercent(benchmarkReturn)}와 v1 ${formatPercent(v1Return)}를 상회합니다. 다만 drawdown과 거래 비용을 함께 봐야 합니다.` };
  }
  if (beatsBenchmark) {
    return { tone: 'warn', label: '부분 신호: 기준선은 상회하지만 개선 폭 제한', detail: `v2가 all-weather보다 높지만 v1 대비 개선은 뚜렷하지 않습니다. 손절 규칙이 수익보다 리스크 제어에 기여했는지 확인해야 합니다.` };
  }
  return { tone: 'bad', label: '주의: 기준선 대비 우위 부족', detail: `v2 MWR ${formatPercent(v2Return)}가 all-weather ${formatPercent(benchmarkReturn)}를 확실히 넘지 못합니다. 리포트 선택/청산 규칙의 재검토가 필요합니다.` };
}

function returnColor(value: number): string {
  const capped = Math.max(-0.6, Math.min(0.8, value));
  if (capped >= 0) {
    const alpha = 0.18 + Math.min(capped / 0.8, 1) * 0.62;
    return `linear-gradient(135deg, rgba(103, 232, 165, ${alpha}), rgba(53, 242, 194, ${Math.max(0.12, alpha - 0.14)}))`;
  }
  const alpha = 0.20 + Math.min(Math.abs(capped) / 0.6, 1) * 0.58;
  return `linear-gradient(135deg, rgba(255, 111, 145, ${alpha}), rgba(138, 180, 255, ${Math.max(0.12, alpha - 0.2)}))`;
}

function positionReturn(entry: number | null, exit: number | null): number | null {
  if (!entry || !exit || entry <= 0) return null;
  return exit / entry - 1;
}

function targetGap(current: number | null | undefined, target: number | null | undefined): number | null {
  if (!current || !target || current <= 0) return null;
  return target / current - 1;
}

function getPersonaLabel(personas: SummaryRow[], persona: string) {
  return personas.find((row) => row.persona === persona)?.label ?? persona;
}

function humanReason(reason: string): string {
  if (reason.includes('target_hit')) return '목표가 도달';
  if (reason.includes('stop')) return '손절/리스크 제한';
  if (reason.includes('rebalance_buy')) return '리밸런싱 매수';
  if (reason.includes('rebalance_sell')) return '리밸런싱 매도';
  if (reason.includes('time')) return '시간 손절';
  return reason.replace(/[()']/g, '') || '—';
}

function mean(values: number[]): number | null {
  if (!values.length) return null;
  return values.reduce((sum, value) => sum + value, 0) / values.length;
}

function percentile(values: number[], p: number): number | null {
  if (!values.length) return null;
  const index = (values.length - 1) * p;
  const lower = Math.floor(index);
  const upper = Math.ceil(index);
  if (lower === upper) return values[lower];
  return values[lower] + (values[upper] - values[lower]) * (index - lower);
}

function skewness(values: number[]): number | null {
  if (values.length < 3) return null;
  const avg = mean(values);
  if (avg === null) return null;
  const variance = values.reduce((sum, value) => sum + (value - avg) ** 2, 0) / values.length;
  const sd = Math.sqrt(variance);
  if (sd === 0) return 0;
  return values.reduce((sum, value) => sum + ((value - avg) / sd) ** 3, 0) / values.length;
}

function isNumber(value: number | null | undefined): value is number {
  return value !== null && value !== undefined && Number.isFinite(value);
}

function skewLabel(value: number | null): string {
  if (value === null) return '표본 부족';
  if (value > 1) return '오른쪽 꼬리 큼';
  if (value < -1) return '왼쪽 꼬리 큼';
  if (value > 0.3) return '약한 오른쪽 왜도';
  if (value < -0.3) return '약한 왼쪽 왜도';
  return '대체로 대칭';
}

function formatStat(value: number | null, kind: 'percent' | 'days') {
  return kind === 'percent' ? formatPercent(value) : formatDays(value);
}

function formatNumber(value: number | null, digits: number) {
  if (value === null || !Number.isFinite(value)) return '—';
  return value.toLocaleString('ko-KR', { maximumFractionDigits: digits, minimumFractionDigits: digits });
}

function formatHistogramEdge(value: number) {
  if (value === Number.POSITIVE_INFINITY) return '∞';
  return `${Math.round(value * 100)}%`;
}
