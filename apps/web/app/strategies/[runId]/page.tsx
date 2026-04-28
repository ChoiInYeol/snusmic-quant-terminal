import Link from 'next/link';
import { notFound } from 'next/navigation';
import { StrategySummary } from '@/components/strategies/StrategySummary';
import { getStrategyRuns } from '@/lib/artifacts';

export function generateStaticParams() {
  return getStrategyRuns().runs.map((run) => ({ runId: run.run_id }));
}

export default async function StrategyDetailPage({ params }: { params: Promise<{ runId: string }> }) {
  const { runId } = await params;
  const data = getStrategyRuns();
  const run = data.runs.find((item) => item.run_id === runId);
  if (!run) notFound();
  return (
    <>
      <section className="hero">
        <div className="eyebrow"><Link href="/strategies">← 전략 리더보드</Link></div>
        <h1>{run.label}</h1>
        <p>파라미터와 점수를 그대로 공개해 재현성과 과최적화 위험을 함께 보여줍니다.</p>
      </section>
      <StrategySummary run={run} />
      <section className="panel" style={{ marginTop: '1rem' }}>
        <h2>원본 파라미터</h2>
        <pre className="markdown-snippet">{JSON.stringify(run.params ?? {}, null, 2)}</pre>
      </section>
      <section className="panel" style={{ marginTop: '1rem' }}>
        <h2>원본 지표</h2>
        <pre className="markdown-snippet">{JSON.stringify(run.metrics, null, 2)}</pre>
      </section>
    </>
  );
}
