import { notFound } from 'next/navigation';
import { StrategySummary } from '@/components/strategies/StrategySummary';
import { Panel, TerminalHero } from '@/components/ui/Terminal';

type StrategyRun = {
  run_id: string;
  label: string;
  scope?: string;
  sampler?: string;
  params?: Record<string, string | number | boolean>;
  metrics: Record<string, number | null | undefined>;
  warnings?: string[];
};

type StrategyRunsArtifact = { runs: StrategyRun[] };
type StrategyParams = Promise<{ runId: string }>;

async function loadStrategyRuns(): Promise<StrategyRunsArtifact> {
  try {
    return (await import('../../../public/artifacts/strategy-runs.json')).default as StrategyRunsArtifact;
  } catch {
    return { runs: [] };
  }
}

export async function generateStaticParams() {
  const data = await loadStrategyRuns();
  return data.runs.map((run) => ({ runId: run.run_id }));
}

export default async function StrategyDetailPage({ params }: { params: StrategyParams }) {
  const { runId } = await params;
  const data = await loadStrategyRuns();
  const run = data.runs.find((item) => item.run_id === runId);
  if (!run) notFound();

  return (
    <>
      <TerminalHero eyebrow="Strategy detail" title={run.label}>
        <p>로컬 탐색에서 내보낸 단일 전략 후보입니다. 공개 웹은 이 JSON 스냅샷을 읽기만 합니다.</p>
      </TerminalHero>
      <StrategySummary run={run} />
      <Panel title="파라미터">
        <dl className="param-grid">
          {Object.entries(run.params ?? {}).map(([key, value]) => (
            <div className="param" key={key}>
              <dt>{key}</dt>
              <dd>{String(value)}</dd>
            </div>
          ))}
        </dl>
      </Panel>
    </>
  );
}
