import Link from 'next/link';
import { getReportRows } from '@/lib/artifacts';
import { formatDays, formatKrw, formatPercent } from '@/lib/format';

export default function ReportsPage() {
  const reports = getReportRows();
  const topRows = [...reports]
    .sort((a, b) => (b.currentReturn ?? -Infinity) - (a.currentReturn ?? -Infinity))
    .slice(0, 120);

  return (
    <>
      <section className="hero">
        <div className="eyebrow">Report explorer</div>
        <h1>Every extracted report with price evidence.</h1>
        <p>
          Sorted by realized return for fast triage. Detail pages show the publication marker, target line, hit date,
          and the extracted markdown evidence that fed the simulation.
        </p>
      </section>
      <section className="grid cards" style={{ marginBottom: '1rem' }}>
        <div className="card"><div className="muted">Rows shown</div><div className="metric">{topRows.length}</div><p>of {reports.length} price-matched reports</p></div>
        <div className="card"><div className="muted">Target hits</div><div className="metric good">{reports.filter((report) => report.targetHit).length}</div></div>
        <div className="card"><div className="muted">Still open/missed</div><div className="metric warn">{reports.filter((report) => !report.targetHit).length}</div></div>
      </section>
      <div className="table-wrap">
        <table>
          <thead>
            <tr><th>Report</th><th>Published</th><th>Entry</th><th>Target</th><th>Upside promised</th><th>Realized</th><th>Hit evidence</th></tr>
          </thead>
          <tbody>
            {topRows.map((report) => (
              <tr key={report.reportId}>
                <td><Link href={`/reports/${report.reportId}`}>{report.company}</Link><div className="muted">{report.symbol} · {report.exchange}</div></td>
                <td>{report.publicationDate}</td>
                <td>{formatKrw(report.entryPriceKrw)}</td>
                <td>{formatKrw(report.targetPriceKrw)}</td>
                <td>{formatMultiple(report.targetUpsideAtPub)}</td>
                <td className={(report.currentReturn ?? 0) >= 0 ? 'good' : 'bad'}>{formatPercent(report.currentReturn)}</td>
                <td>{report.targetHit ? <span className="pill good">hit in {formatDays(report.daysToTarget)}</span> : <span className="pill">not hit</span>}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </>
  );
}

function formatMultiple(value: number | null): string {
  if (value === null || !Number.isFinite(value)) return '—';
  return `${value.toFixed(2)}×`;
}
