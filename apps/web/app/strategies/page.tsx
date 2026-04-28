import { StrategySummary } from '@/components/strategies/StrategySummary';
import { Panel, TerminalHero } from '@/components/ui/Terminal';

type StrategyRun = {
  run_id: string;
  label: string;
  scope?: string;
  sampler?: string;
  metrics: Record<string, number | null | undefined>;
  warnings?: string[];
};

type StrategyRunsArtifact = {
  study_name?: string;
  disclaimer?: string;
  runs: StrategyRun[];
};

async function loadStrategyRuns(): Promise<StrategyRunsArtifact> {
  try {
    const artifact = (await import('../../public/artifacts/strategy-runs.json')).default as StrategyRunsArtifact;
    return artifact;
  } catch {
    return { study_name: 'No local export yet', runs: [], disclaimer: 'scripts/export_optuna_artifacts.py를 실행해 전략 아티팩트를 생성하세요.' };
  }
}

  return (
    <>
      <TerminalHero eyebrow="Local-only Optuna research" title="전략 리더보드">
        <p>{data.disclaimer}</p>
      </TerminalHero>
      <section className="grid">
        {data.runs.length ? data.runs.map((run) => <StrategySummary key={run.run_id} run={run} href={`/strategies/${run.run_id}`} />) : (
          <Panel>
            <p>전략 아티팩트가 없습니다. 로컬 탐색/내보내기 스크립트를 실행한 뒤 JSON을 public artifacts에 복사하세요.</p>
          </Panel>
        )}
      </section>
    </>
  );
}
