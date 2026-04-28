import { CumulativeReturnChart, type ReturnSeries } from '@/components/charts/CumulativeReturnChart';
import { StrategySummary } from '@/components/strategies/StrategySummary';
import { MetricCard, Panel, TerminalHero } from '@/components/ui/Terminal';
import { getEquityDaily, getParameterImportance, getPersonaLabel, getStrategyExperiment, getStrategyRuns } from '@/lib/artifacts';
import { formatPercent } from '@/lib/format';

export default function StrategiesPage() {
  const data = getStrategyRuns();
  const importance = getParameterImportance();
  const bestRun = data.runs.find((run) => run.run_id === data.best_run_id) ?? data.runs[0];
  const chartSeries = buildStrategySeries(data.runs.slice(0, 3));

  return (
    <>
      <TerminalHero
        eyebrow="Local-only Optuna research"
        title="전략 리더보드"
      >
        <p>{data.disclaimer ?? '로컬 Optuna 탐색 결과를 정적 JSON 스냅샷으로 노출합니다. 이 화면은 시장 주문이나 실시간 갱신을 수행하지 않습니다.'} 파라미터는 0.01 단위 이산값으로 실험하고, 화면에는 소수점 2자리까지만 표시합니다.</p>
      </TerminalHero>

      <section className="grid cards" style={{ marginBottom: '1rem' }}>
        <MetricCard label="전략 후보" value={data.runs.length.toLocaleString('ko-KR')} tone="accent" />
        <MetricCard label="최고 후보" value={bestRun?.label ?? '—'} detail={bestRun ? `score ${formatPercent(bestRun.metrics.score)}` : '내보낸 전략 없음'} tone="good" />
        <MetricCard label="스터디" value={data.study_name ?? '—'} />
        <MetricCard label="범위" value={data.scope ?? bestRun?.scope ?? 'local'} />
      </section>

      <Panel title="전략별 누적 수익률 비교" className="dense-panel">
        <p className="muted">기준 전략의 실제 일별 자본 대비 수익률과 상위 실험 후보의 이벤트 기반 실험 경로를 함께 비교합니다.</p>
        <CumulativeReturnChart series={chartSeries} />
      </Panel>

      {importance.parameters?.length ? (
        <Panel title="파라미터 중요도" className="dense-panel">
          <div className="bar-list">
            {importance.parameters.slice(0, 8).map((item) => (
              <div className="bar-row" key={item.parameter}>
                <span>{item.parameter}</span>
                <div className="bar-track"><div className="bar-fill" style={{ width: `${Math.max(2, item.importance * 100)}%` }} /></div>
                <strong>{formatPercent(item.importance)}</strong>
              </div>
            ))}
          </div>
        </Panel>
      ) : null}

      <section className="grid" style={{ marginTop: '1rem' }}>
        {data.runs.length ? data.runs.map((run) => (
          <StrategySummary key={run.run_id} run={run} href={`/strategies/${run.run_id}`} />
        )) : (
          <Panel>
            <p>전략 아티팩트가 없습니다. 로컬 탐색/내보내기 스크립트를 실행한 뒤 JSON을 public artifacts에 복사하세요.</p>
          </Panel>
        )}
      </section>
    </>
  );
}

function buildStrategySeries(runs: ReturnType<typeof getStrategyRuns>['runs']): ReturnSeries[] {
  const palette = ['#d7ff4f', '#35f2c2', '#8ab4ff', '#ffd166', '#ff6f91', '#b892ff'];
  const baselinePersonas = ['smic_follower', 'smic_follower_v2', 'all_weather'];
  const equity = getEquityDaily();
  const series: ReturnSeries[] = baselinePersonas.map((persona, index) => ({
    id: persona,
    label: getPersonaLabel(persona),
    color: palette[index],
    points: equity
      .filter((point) => point.persona === persona && point.cumulativeReturn !== null)
      .map((point) => ({ time: point.date, value: point.cumulativeReturn ?? 0 })),
  }));
  return [
    ...series,
    ...runs.map((run, index) => ({
      id: run.run_id,
      label: run.label,
      color: palette[(index + baselinePersonas.length) % palette.length],
      points: getStrategyExperiment(run).cumulativeReturnSeries,
    })),
  ];
}
