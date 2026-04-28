import type { Metadata } from 'next';
import Link from 'next/link';
import { notFound } from 'next/navigation';
import { PriceEvidenceChart } from '@/components/charts/PriceEvidenceChart';
import { getMarkdownSnippet, getPriceSeries, getReport, getReports } from '@/lib/artifacts';
import { formatKrw, formatPercent } from '@/lib/format';

export function generateStaticParams() {
  return getReports().map((report) => ({ reportId: report.report_id }));
}

export function generateMetadata({ params }: { params: { reportId: string } }): Metadata {
  const report = getReport(params.reportId);
  return { title: report ? `${report.company} evidence` : 'Report evidence' };
}

export default function ReportDetailPage({ params }: { params: { reportId: string } }) {
  const report = getReport(params.reportId);
  if (!report) notFound();
  const prices = getPriceSeries(report.symbol).filter((point) => point.date >= report.date);
  const snippet = getMarkdownSnippet(report);
  return (
    <>
      <section className="hero"><div className="eyebrow"><Link href="/reports">← Reports</Link></div><h1>{report.company}</h1><p>{report.title} · {report.symbol} · published {report.date}</p></section>
      <section className="grid cards spaced"><div className="card"><div className="muted">Entry/publication</div><div className="metric">{formatKrw(report.entry_price_krw ?? report.publication_price_krw)}</div></div><div className="card"><div className="muted">Target</div><div className="metric">{formatKrw(report.target_price_krw)}</div><p>{formatPercent(report.target_upside_at_pub)} upside at publication</p></div><div className="card"><div className="muted">Current return</div><div className={`metric ${(report.current_return ?? 0) >= 0 ? 'good' : 'bad'}`}>{formatPercent(report.current_return)}</div></div><div className="card"><div className="muted">Status</div><div className="metric">{report.target_hit ? 'Hit' : 'Open/Miss'}</div><p>{report.target_hit_date ?? `gap ${formatPercent(report.target_gap_pct)}`}</p></div></section>
      <section className="detail-grid"><div className="panel"><h2>Price path vs extracted target</h2><PriceEvidenceChart priceSeries={prices} targetPriceKrw={report.target_price_krw} publicationDate={report.date} targetHitDate={report.target_hit_date} /></div><aside className="grid"><div className="panel"><h2>Caveats</h2>{report.caveat_flags.length ? <ul>{report.caveat_flags.map((flag) => <li key={flag}>{flag}</li>)}</ul> : <p>No caveat flags for this row.</p>}{report.pdf_url ? <p><a href={report.pdf_url}>Original PDF source →</a></p> : null}</div><div className="panel"><h2>Extraction evidence</h2><pre className="markdown-snippet">{snippet}</pre></div></aside></section>
    </>
  );
}
