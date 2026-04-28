import { getDataQuality, getReportRows } from '@/lib/artifacts';
import { formatPercent } from '@/lib/format';

export default function DataQualityPage() {
  const quality = getDataQuality();
  const reports = getReportRows();
  const openRows = reports.filter((report) => !report.targetHit && report.lastCloseKrw !== null);

  return (
    <>
      <section className="hero">
        <div className="eyebrow">Data quality</div>
        <h1>No hidden exclusions.</h1>
        <p>Extraction coverage, price matching, target-hit state, and caveats stay visible so the dashboard is evidence rather than persuasion.</p>
      </section>
      <section className="grid cards">
        <div className="card"><div className="muted">Extracted reports</div><div className="metric">{quality.extractedReports}</div></div>
        <div className="card"><div className="muted">Report-stat universe</div><div className="metric">{quality.totalReports}</div></div>
        <div className="card"><div className="muted">Price-matched</div><div className="metric">{quality.reportsWithPrices}</div></div>
        <div className="card"><div className="muted">Target hit rate</div><div className="metric">{formatPercent(quality.targetHitRate)}</div></div>
      </section>
      <section className="panel" style={{ marginTop: '1rem' }}>
        <h2>Current caveats</h2>
        <ul>
          <li>{quality.missingPriceSymbols} symbols are reported as missing-price symbols in the simulation aggregate.</li>
          <li>{openRows.length} price-matched rows have not reached the extracted base target as of their last available close.</li>
          <li>Targets and prices are normalized to KRW before report-level comparisons.</li>
          <li>All web pages are static readers of committed artifacts; they do not fetch market data or mutate the simulation.</li>
        </ul>
      </section>
      <section className="panel" style={{ marginTop: '1rem' }}>
        <h2>Raw extraction quality artifact</h2>
        <pre className="markdown-snippet">{JSON.stringify(quality.extractionQuality, null, 2)}</pre>
      </section>
    </>
  );
}
