import { StrategySummary } from '@/components/strategies/StrategySummary';
import { MetricCard, Panel, TerminalHero, TerminalLink } from '@/components/ui/Terminal';
import { getParameterImportance, getStrategyRuns } from '@/lib/artifacts';
import { formatPercent } from '@/lib/format';

export default function StrategiesPage() {
  const data = getStrategyRuns();
  const importance = getParameterImportance();
  const bestRun = data.runs.find((run) => run.run_id === data.best_run_id) ?? data.runs[0];

  return (
    <>
      <TerminalHero
        eyebrow="Local-only Optuna research"
        title="전략 리더보드"
        actions={<TerminalLink href="/lab">실험실 보기 →</TerminalLink>}
      >
        <p>{data.disclaimer ?? '로컬 Optuna 탐색 결과를 정적 JSON 스냅샷으로 노출합니다. 이 화면은 시장 주문이나 실시간 갱신을 수행하지 않습니다.'}</p>
      </TerminalHero>

      <section className="grid cards" style={{ marginBottom: '1rem' }}>
        <MetricCard label="전략 후보" value={data.runs.length.toLocaleString('ko-KR')} tone="accent" />
        <MetricCard label="최고 후보" value={bestRun?.label ?? '—'} detail={bestRun ? `score ${formatPercent(bestRun.metrics.score)}` : '내보낸 전략 없음'} tone="good" />
        <MetricCard label="스터디" value={data.study_name ?? '—'} />
        <MetricCard label="범위" value={data.scope ?? bestRun?.scope ?? 'local'} />
      </section>

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
