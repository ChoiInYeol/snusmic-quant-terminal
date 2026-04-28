import Link from 'next/link';
import { notFound } from 'next/navigation';
import { CumulativeReturnChart } from '@/components/charts/CumulativeReturnChart';
import { StrategySummary } from '@/components/strategies/StrategySummary';
import { MetricCard, Panel, TerminalHero } from '@/components/ui/Terminal';
import { getStrategyExperiment, getStrategyRuns } from '@/lib/artifacts';
import { formatKrw, formatPercent } from '@/lib/format';

type StrategyParams = Promise<{ runId: string }>;

export function generateStaticParams() {
  return getStrategyRuns().runs.map((run) => ({ runId: run.run_id }));
}

export default async function StrategyDetailPage({ params }: { params: StrategyParams }) {
  const { runId } = await params;
  const data = getStrategyRuns();
  const run = data.runs.find((item) => item.run_id === runId);
  if (!run) notFound();
  const experiment = getStrategyExperiment(run);
  const finalReturn = experiment.cumulativeReturnSeries.at(-1)?.value ?? run.metrics.money_weighted_return ?? null;

  return (
    <>
      <TerminalHero eyebrow="Strategy detail" title={run.label}>
        <p><Link href="/strategies">← 전략 기준</Link> · 0.01 단위 이산 파라미터로 실험한 로컬 후보입니다. 아래에는 이 후보가 선택한 실험 포트폴리오와 이벤트 기반 매매내역을 공개합니다.</p>
      </TerminalHero>
      <StrategySummary run={run} />
      <section className="grid cards" style={{ margin: '1rem 0' }}>
        <MetricCard label="실험 선택 종목" value={experiment.positions.length.toLocaleString('ko-KR')} detail={`${experiment.trades.length.toLocaleString('ko-KR')}개 이벤트`} tone="accent" />
        <MetricCard label="실험 누적 수익률" value={formatPercent(finalReturn)} tone={(finalReturn ?? 0) >= 0 ? 'good' : 'bad'} />
        <MetricCard label="공개 후보 최종자산" value={formatKrw(run.metrics.final_equity_krw)} />
      </section>

      <Panel title="이 후보의 누적 수익률 경로" className="dense-panel">
        <CumulativeReturnChart series={[{ id: run.run_id, label: run.label, color: '#d7ff4f', points: experiment.cumulativeReturnSeries }]} />
      </Panel>

      <section className="grid two-col" style={{ marginTop: '1rem' }}>
        <Panel title="실험 포트폴리오">
          <div className="table-wrap inset compact-table">
            <table>
              <thead><tr><th>종목</th><th>발간일</th><th>비중</th><th>진입가</th><th>목표가</th><th>실험 수익률</th><th>상태</th></tr></thead>
              <tbody>{experiment.positions.map((position) => (
                <tr key={`${position.symbol}-${position.publicationDate}`}>
                  <td><Link href={`/reports/${position.symbol}`}>{position.company || position.symbol}</Link><div className="muted">{position.symbol}</div></td>
                  <td>{position.publicationDate}</td>
                  <td>{formatPercent(position.weight)}</td>
                  <td>{formatKrw(position.entryPriceKrw)}</td>
                  <td>{formatKrw(position.targetPriceKrw)}</td>
                  <td className={(position.realizedReturn ?? 0) >= 0 ? 'good' : 'bad'}>{formatPercent(position.realizedReturn)}</td>
                  <td>{position.status === 'closed' ? `청산 · ${position.exitDate}` : '보유/오픈'}</td>
                </tr>
              ))}</tbody>
            </table>
          </div>
        </Panel>
        <Panel title="실험 매매내역">
          <div className="table-wrap inset compact-table">
            <table>
              <thead><tr><th>일자</th><th>구분</th><th>종목</th><th>비중</th><th>참조가격</th><th>기준</th></tr></thead>
              <tbody>{experiment.trades.map((trade) => (
                <tr key={`${trade.date}-${trade.side}-${trade.symbol}`}>
                  <td>{trade.date}</td>
                  <td><span className={`pill ${trade.side === 'buy' ? 'good' : 'warn'}`}>{trade.side === 'buy' ? '매수' : '매도'}</span></td>
                  <td><Link href={`/reports/${trade.symbol}`}>{trade.company || trade.symbol}</Link><div className="muted">{trade.symbol}</div></td>
                  <td>{formatPercent(trade.weight)}</td>
                  <td>{formatKrw(trade.referencePriceKrw)}</td>
                  <td>{trade.reason}</td>
                </tr>
              ))}</tbody>
            </table>
          </div>
        </Panel>
      </section>

      <Panel title="파라미터" className="dense-panel">
        <dl className="param-grid">
          {Object.entries(run.params ?? {}).map(([key, value]) => (
            <div className="param" key={key}>
              <dt>{key}</dt>
              <dd>{formatParam(value)}</dd>
            </div>
          ))}
        </dl>
      </Panel>
    </>
  );
}

function formatParam(value: unknown): string {
  if (typeof value === 'number') return Math.round(value * 100) / 100 === Math.round(value) ? Math.round(value).toLocaleString('ko-KR') : (Math.round(value * 100) / 100).toLocaleString('ko-KR', { minimumFractionDigits: 2, maximumFractionDigits: 2 });
  if (typeof value === 'boolean') return value ? '예' : '아니오';
  return String(value ?? '—');
}
