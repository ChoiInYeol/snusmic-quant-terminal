import type { Metadata } from 'next';
import Link from 'next/link';
import { notFound } from 'next/navigation';
import { PriceEvidenceChart } from '@/components/charts/PriceEvidenceChart';
import { getMarkdownSnippet, getPriceSeries, getReportById, getReportRows } from '@/lib/artifacts';
import { formatDays, formatKrw, formatPercent } from '@/lib/format';

export function generateStaticParams() {
  return getReportRows().map((report) => ({ reportId: report.reportId }));
}

export function generateMetadata({ params }: { params: { reportId: string } }): Metadata {
  const report = getReportById(params.reportId);
  return { title: report ? `${report.company} report evidence` : 'Report evidence' };
}

export default function ReportDetailPage({ params }: { params: { reportId: string } }) {
  const report = getReportById(params.reportId);
  if (!report) notFound();
  const prices = getPriceSeries(report.symbol, report.publicationDate, report.lastCloseDate);
  const snippet = getMarkdownSnippet(report);

  return (
    <>
      <section className="hero">
        <div className="eyebrow"><Link href="/reports">← Reports</Link></div>
        <h1>{report.company}</h1>
        <p>{report.title} · {report.symbol} · published {report.publicationDate}</p>
      </section>
      <section className="grid cards" style={{ marginBottom: '1rem' }}>
        <div className="card"><div className="muted">Entry close</div><div className="metric">{formatKrw(report.entryPriceKrw)}</div></div>
        <div className="card"><div className="muted">Extracted target</div><div className="metric">{formatKrw(report.targetPriceKrw)}</div><p>{formatPercent(report.targetUpsideAtPub)} upside at publication</p></div>
        <div className="card"><div className="muted">Current return</div><div className={`metric ${(report.currentReturn ?? 0) >= 0 ? 'good' : 'bad'}`}>{formatPercent(report.currentReturn)}</div></div>
        <div className="card"><div className="muted">Target status</div><div className="metric">{report.targetHit ? 'Hit' : 'Open'}</div><p>{report.targetHit ? `${report.targetHitDate} · ${formatDays(report.daysToTarget)}` : `gap ${formatPercent(report.targetGapPct)}`}</p></div>
      </section>
      <section className="detail-grid">
        <div className="panel">
          <h2>Price path vs extracted target</h2>
          <PriceEvidenceChart priceSeries={prices} targetPrice={report.targetPriceKrw} publicationDate={report.publicationDate} targetHitDate={report.targetHitDate} />
        </div>
        <aside className="grid">
          <div className="panel">
            <h2>Path stats</h2>
            <p>Peak return: <span className="good">{formatPercent(report.peakReturn)}</span></p>
            <p>Trough return: <span className="bad">{formatPercent(report.troughReturn)}</span></p>
            <p>Last close: {formatKrw(report.lastCloseKrw)} on {report.lastCloseDate}</p>
            {report.pdfUrl ? <p><a href={report.pdfUrl}>Original PDF source →</a></p> : null}
          </div>
          <div className="panel">
            <h2>Extracted markdown evidence</h2>
            <div className="markdown-snippet">{snippet}</div>
          </div>
        </aside>
      </section>
    </>
  );
}
