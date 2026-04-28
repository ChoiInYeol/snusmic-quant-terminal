import { getDataQuality, getMissingSymbols, getOverview, getReports } from '@/lib/artifacts';
import { formatNumber, formatPercent } from '@/lib/format';

export default function DataQualityPage() {
  const overview = getOverview();
  const reports = getReports();
  const missing = getMissingSymbols();
  const quality = getDataQuality();
  return (
    <>
      <section className="hero"><div className="eyebrow">Data quality</div><h1>No hidden exclusions.</h1><p>가격 누락, 추출 경고, lookahead bias, 통화 변환을 공개해 대시보드가 설득보다 증거가 되도록 합니다.</p></section>
      <section className="grid cards"><Metric label="Extracted reports" value={formatNumber(overview?.report_counts.extracted_reports)} /><Metric label="Report-stat rows" value={formatNumber(overview?.report_counts.report_stat_rows)} /><Metric label="Price matched" value={formatNumber(overview?.report_counts.price_matched_reports)} /><Metric label="Target hit rate" value={formatPercent(overview?.target_stats.target_hit_rate)} /></section>
      <section className="panel spaced"><h2>Missing price symbols</h2>{missing.length ? <ul>{missing.map((row) => <li key={row.symbol}><code>{row.symbol}</code></li>)}</ul> : <p>No missing symbols.</p>}<p>{reports.filter((row) => row.caveat_flags.includes('missing_price_history')).length} report rows are explicitly flagged as missing price history.</p></section>
      <section className="panel spaced"><h2>Known methodology caveats</h2><ul><li>Prophet and Weak Prophet use future information and are upper bounds, not tradable recommendations.</li><li>Publication prices come from normalized market data, not from screenshots in the PDF.</li><li>All prices are displayed in KRW for comparability; overseas tickers use FX-normalized warehouse rows.</li><li>Missing-price rows are visible; they are not treated as zero-return investments.</li></ul></section>
      <section className="panel spaced"><h2>Raw extraction quality summary</h2><pre className="markdown-snippet">{JSON.stringify(quality, null, 2)}</pre></section>
    </>
  );
}
function Metric({ label, value }: { label: string; value: string }) { return <div className="card"><div className="muted">{label}</div><div className="metric">{value}</div></div>; }
