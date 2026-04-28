import Link from 'next/link';
import { getReports } from '@/lib/artifacts';
import { formatKrw, formatNumber, formatPercent } from '@/lib/format';

export default function ReportsPage({ searchParams }: { searchParams?: { q?: string; hit?: string } }) {
  const q = (searchParams?.q ?? '').toLowerCase();
  const hit = searchParams?.hit;
  const reports = getReports()
    .filter((row) => !q || `${row.company} ${row.title} ${row.ticker} ${row.symbol}`.toLowerCase().includes(q))
    .filter((row) => hit === 'yes' ? row.target_hit === true : hit === 'no' ? row.target_hit !== true : true)
    .sort((a, b) => (b.current_return ?? -999) - (a.current_return ?? -999));

  return (
    <>
      <section className="hero">
        <div className="eyebrow">Report explorer</div>
        <h1>Every report, searchable and ranked.</h1>
        <p>URL query로 공유 가능한 검색: <code>?q=비에이치</code>, <code>?q=Chegg&hit=no</code>.</p>
      </section>
      <section className="grid cards spaced"><div className="card"><div className="muted">Rows</div><div className="metric">{formatNumber(reports.length)}</div></div><div className="card"><div className="muted">Target hits</div><div className="metric good">{formatNumber(reports.filter((r) => r.target_hit).length)}</div></div><div className="card"><div className="muted">Missing/caveat rows</div><div className="metric warn">{formatNumber(reports.filter((r) => r.caveat_flags.length > 0).length)}</div></div></section>
      <div className="table-wrap">
        <table>
          <thead><tr><th>Report</th><th>Date</th><th>Entry</th><th>Target</th><th>Current return</th><th>Hit</th><th>Caveats</th></tr></thead>
          <tbody>{reports.map((report) => <tr key={report.report_id}><td><Link href={`/reports/${report.report_id}`}>{report.company}</Link><div className="muted">{report.symbol} · {report.ticker}</div></td><td>{report.date}</td><td>{formatKrw(report.entry_price_krw ?? report.publication_price_krw)}</td><td>{formatKrw(report.target_price_krw)}</td><td className={(report.current_return ?? 0) >= 0 ? 'good' : 'bad'}>{formatPercent(report.current_return)}</td><td>{report.target_hit ? <span className="pill good">hit {report.days_to_target ? `${Math.round(report.days_to_target)}d` : ''}</span> : <span className="pill">open/miss</span>}</td><td>{report.caveat_flags.slice(0, 2).join(', ') || '—'}</td></tr>)}</tbody>
        </table>
      </div>
    </>
  );
}
