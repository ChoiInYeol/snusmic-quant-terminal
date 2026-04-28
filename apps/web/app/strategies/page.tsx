import { StrategySummary } from '@/components/strategies/StrategySummary';
import { getParameterImportance, getStrategyRuns } from '@/lib/artifacts';
import { formatPercent } from '@/lib/format';

export default function StrategiesPage() {
  const data = getStrategyRuns();
  const importance = getParameterImportance();
  const runs = data.runs ?? [];
  const best = runs.find((run) => run.run_id === data.best_run_id) ?? runs[0];

  return (
    <>
      <section className="hero">
        <div className="eyebrow">전략 리더보드</div>
        <h1>로컬 탐색 결과를 있는 그대로 비교합니다.</h1>
        <p>
          {data.study_name} 연구의 상위 조합을 한국어로 해석합니다. 모든 수치는 정적 artifact이며,
          배포된 웹에서는 Optuna·시장데이터·파이썬 시뮬레이션을 실행하지 않습니다.
        </p>
      </section>

      <section className="grid cards" style={{ marginBottom: '1rem' }}>
        <div className="card"><div className="muted">탐색 범위</div><div className="metric">{data.scope ?? '—'}</div><p>인샘플 결과는 과최적화 가능성을 항상 포함합니다.</p></div>
        <div className="card"><div className="muted">전략 후보</div><div className="metric">{runs.length}</div><p>정렬 기준: objective score</p></div>
        <div className="card"><div className="muted">베스트 런</div><div className="metric">#{best?.trial_number ?? '—'}</div><p>{best?.label ?? '내보낸 전략 없음'}</p></div>
      </section>

      {importance.parameters?.length ? (
        <section className="panel" style={{ marginBottom: '1rem' }}>
          <div className="split-header">
            <div>
              <h2>점수에 민감했던 파라미터</h2>
              <p>{importance.method}</p>
            </div>
          </div>
          <div className="bar-list">
            {importance.parameters.slice(0, 6).map((item) => (
              <div className="bar-row" key={item.parameter}>
                <span>{item.parameter}</span>
                <div className="bar-track"><div className="bar-fill" style={{ width: `${Math.min(100, item.importance * 100)}%` }} /></div>
                <strong>{formatPercent(item.importance, 1)}</strong>
              </div>
            ))}
          </div>
        </section>
      ) : null}

      <section className="grid" aria-label="전략 순위">
        {runs.length ? runs.map((run, index) => <StrategySummary key={run.run_id} run={run} rank={index + 1} />) : (
          <div className="panel">전략 artifact가 없습니다. 로컬 탐색과 export 스크립트를 먼저 실행하세요.</div>
        )}
      </section>
    </>
  );
}
