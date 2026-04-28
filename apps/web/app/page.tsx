import Link from 'next/link';
import { getDataQuality, getReportRows, getSummaryRows } from '@/lib/artifacts';
import { formatKrwMillions, formatPercent } from '@/lib/format';

export default function HomePage() {
  const reports = getReportRows();
  const quality = getDataQuality();
  const summaries = getSummaryRows();
  const bestPersona = summaries[0];
  const hitRate = reports.filter((report) => report.targetHit).length / Math.max(1, reports.length);

  return (
    <>
      <section className="hero">
        <div className="eyebrow">Artifact-first research lab</div>
        <h1>SMIC reports, translated into investable evidence.</h1>
        <p>
          Browse extracted target prices, publication-date entries, realized price paths, target-hit evidence, and the
          caveats behind the simulation dataset.
        </p>
      </section>
      <section className="grid cards">
        <div className="card"><div className="muted">Price-matched reports</div><div className="metric">{reports.length}</div></div>
        <div className="card"><div className="muted">Target hit rate</div><div className="metric">{formatPercent(hitRate)}</div></div>
        <div className="card"><div className="muted">Extracted reports</div><div className="metric">{quality.extractedReports}</div></div>
        <div className="card"><div className="muted">Top persona</div><div className="metric">{bestPersona?.persona ?? '—'}</div><p>{bestPersona ? formatKrwMillions(bestPersona.finalEquityKrw) : 'Run simulation artifacts first.'}</p></div>
      </section>
      <section className="panel" style={{ marginTop: '1rem' }}>
        <h2>Start exploring</h2>
        <p>The showcase keeps Python as the compute engine. Next.js reads committed CSV/JSON artifacts and renders static pages.</p>
        <p><Link href="/reports">Open report explorer →</Link></p>
      </section>
    </>
  );
}
