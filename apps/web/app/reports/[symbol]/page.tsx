import type { Metadata } from 'next';
import Link from 'next/link';
import { notFound } from 'next/navigation';
import { PriceEvidenceChart } from '@/components/charts/PriceEvidenceChart';
import { MetricCard, Panel, TerminalHero } from '@/components/ui/Terminal';
import { getMarkdownSnippet, getPriceSeries, getReportBySymbol, getReportRows, getReportsBySymbol, type PricePoint, type ReportRow } from '@/lib/artifacts';
import { formatDays, formatKrw, formatPercent } from '@/lib/format';

type ReportParams = Promise<{ symbol: string }>;

export function generateStaticParams() {
  return Array.from(new Set(getReportRows().map((report) => report.symbol))).map((symbol) => ({ symbol }));
}

export async function generateMetadata({ params }: { params: ReportParams }): Promise<Metadata> {
  const { symbol } = await params;
  const report = getReportBySymbol(decodeURIComponent(symbol));
  return { title: report ? `${report.company} 리포트 증거` : '리포트 증거' };
}

export default async function ReportDetailPage({ params }: { params: ReportParams }) {
  const { symbol } = await params;
  const reportSymbol = decodeURIComponent(symbol);
  const report = getReportBySymbol(reportSymbol);
  if (!report) notFound();
  const siblingReports = getReportsBySymbol(reportSymbol);
  const prices = getPriceSeries(report.symbol, report.publicationDate, report.lastCloseDate);
  const snippet = getMarkdownSnippet(report);
  const pathEvidence = buildPathEvidence(prices, report);
  const memo = buildKoreanInvestmentMemo(report);

  return (
    <>
      <TerminalHero eyebrow="Report detail" title={report.company}>
        <p><Link href="/reports">← 리포트 목록</Link> · URL 기준 티커 {report.symbol} · 최신 발간 {report.publicationDate}</p>
      </TerminalHero>
      <section className="grid cards" style={{ marginBottom: '1rem' }}>
        <MetricCard label="진입 종가" value={formatKrw(report.entryPriceKrw)} />
        <MetricCard label="추출 목표가" value={formatKrw(report.targetPriceKrw)} detail={`${formatPercent(report.targetUpsideAtPub)} 발간 시점 업사이드`} tone="accent" />
        <MetricCard label="현재 수익률" value={formatPercent(report.currentReturn)} tone={(report.currentReturn ?? 0) >= 0 ? 'good' : 'bad'} />
        <MetricCard label="목표 상태" value={targetStatusValue(report)} detail={targetStatusDetail(report)} tone={report.targetHit ? 'good' : 'warn'} />
      </section>
      <section className="detail-grid">
        <Panel title="가격 경로 vs 추출 목표가">
          <PriceEvidenceChart priceSeries={prices} targetPrice={report.targetPriceKrw} publicationDate={report.publicationDate} targetHitDate={report.targetHitDate} evidenceMarkers={pathEvidence.markers} />
        </Panel>
        <aside className="grid">
          <Panel title="경로 통계">
            <p>관측 고점: {pathEvidence.peak ? `${pathEvidence.peak.time} · ${formatKrw(pathEvidence.peak.value)}` : '—'}</p>
            <p>관측 저점: {pathEvidence.trough ? `${pathEvidence.trough.time} · ${formatKrw(pathEvidence.trough.value)}` : '—'}</p>
            <p>최고 수익률: <span className="good">{formatPercent(report.peakReturn)}</span></p>
            <p>최저 수익률: <span className="bad">{formatPercent(report.troughReturn)}</span></p>
            <p>마지막 종가: {formatKrw(report.lastCloseKrw)} ({report.lastCloseDate})</p>
            <p><a href={githubBlobUrl(`data/markdown/${report.markdownFilename}`)}>GitHub Markdown →</a></p>
            {report.pdfFilename ? <p><a href={githubBlobUrl(`data/pdfs/${report.pdfFilename}`)}>GitHub PDF →</a></p> : null}
            {report.pdfUrl ? <p><a href={report.pdfUrl}>SNUSMIC 원본 PDF →</a></p> : null}
          </Panel>
          <Panel title="동일 티커 리포트">
            <ul>{siblingReports.map((item) => <li key={item.reportId}>{item.publicationDate} · {item.title}</li>)}</ul>
          </Panel>
          <Panel title="한국어 투자 메모">
            <p>{memo.summary}</p>
            <ul>{memo.bullets.map((item) => <li key={item.label}><strong>{item.label}</strong>: {item.text}</li>)}</ul>
          </Panel>
          <Panel title="추출 Markdown 증거">
            <div className="markdown-snippet">{snippet}</div>
          </Panel>
        </aside>
      </section>
    </>
  );
}

type PathEvidence = {
  peak: PricePoint | null;
  trough: PricePoint | null;
  markers: Array<{ time: string; kind: 'publication' | 'target-hit' | 'peak' | 'trough'; label: string; value?: number | null }>;
};

function buildPathEvidence(prices: PricePoint[], report: ReportRow): PathEvidence {
  const peak = prices.reduce<PricePoint | null>((best, point) => (!best || point.value > best.value ? point : best), null);
  const trough = prices.reduce<PricePoint | null>((best, point) => (!best || point.value < best.value ? point : best), null);
  const markers: PathEvidence['markers'] = [
    { time: report.publicationDate, kind: 'publication', label: '발간', value: report.entryPriceKrw },
  ];
  if (report.targetHitDate) markers.push({ time: report.targetHitDate, kind: 'target-hit', label: '목표 도달', value: report.targetPriceKrw });
  if (peak) markers.push({ time: peak.time, kind: 'peak', label: '관측 고점', value: peak.value });
  if (trough) markers.push({ time: trough.time, kind: 'trough', label: '관측 저점', value: trough.value });
  return { peak, trough, markers };
}

function buildKoreanInvestmentMemo(report: ReportRow) {
  const targetSentence = isBearishReport(report)
    ? report.targetHit
      ? `매도/회피 의견의 하락 목표가는 ${formatDays(report.daysToTarget)} 만에 도달했습니다.`
      : `매도/회피 의견이지만 아직 하락 목표가에는 도달하지 않았습니다.`
    : (report.targetUpsideAtPub ?? 0) <= 0
      ? '첫 거래 가능 가격이 목표가를 이미 넘어선 비실행 케이스라 목표가 달성 통계에서는 제외했습니다.'
      : report.targetHit
        ? `목표가는 ${formatDays(report.daysToTarget)} 만에 도달해 리포트의 단기 가격 근거가 실제 거래 경로에서 확인됐습니다.`
        : `아직 목표가에는 도달하지 못했고 현재 목표가까지 ${formatPercent(report.targetGapPct)}의 갭이 남아 있습니다.`;
  const riskTone = (report.troughReturn ?? 0) < -0.2
    ? '발간 이후 하방 변동성이 컸으므로 분할 진입과 손실 제한 기준을 먼저 확인해야 합니다.'
    : '관측 저점 기준 하방 훼손은 제한적이지만, 목표가 미도달 상태라면 시간 비용을 함께 점검해야 합니다.';

  return {
    summary: `${report.company} 리포트는 발간일 종가 ${formatKrw(report.entryPriceKrw)} 대비 목표가 ${formatKrw(report.targetPriceKrw)}를 제시했습니다. ${targetSentence}`,
    bullets: [
      { label: '상승 여력', text: `발간 시점 목표 업사이드는 ${formatPercent(report.targetUpsideAtPub)}이며, 관측 최고 수익률은 ${formatPercent(report.peakReturn)}입니다.` },
      { label: '리스크', text: `${riskTone} 관측 최저 수익률은 ${formatPercent(report.troughReturn)}입니다.` },
      { label: '현재 판단', text: `마지막 종가는 ${formatKrw(report.lastCloseKrw)}(${report.lastCloseDate ?? '날짜 없음'})이고 현재 수익률은 ${formatPercent(report.currentReturn)}입니다.` },
    ],
  };
}

function targetStatusValue(report: ReportRow): string {
  if (isBearishReport(report)) return report.targetHit ? '매도 적중' : '매도 의견';
  if ((report.targetUpsideAtPub ?? 0) <= 0) return '비실행';
  return report.targetHit ? '도달' : '진행';
}

function targetStatusDetail(report: ReportRow): string {
  if (isBearishReport(report)) {
    return report.targetHit ? `${report.targetHitDate} · ${formatDays(report.daysToTarget)}` : '하락 목표가 미도달';
  }
  if ((report.targetUpsideAtPub ?? 0) <= 0) return '첫 거래 가능 가격이 목표가 이상';
  return report.targetHit ? `${report.targetHitDate} · ${formatDays(report.daysToTarget)}` : `격차 ${formatPercent(report.targetGapPct)}`;
}

function isBearishReport(report: ReportRow): boolean {
  return (report.targetUpsideAtPub ?? 0) < 0 && report.caveatFlags.some((flag) => /non_buy_rating:.*(sell|reduce|underperform|매도)/i.test(flag));
}

function githubBlobUrl(path: string): string {
  return `https://github.com/ChoiInYeol/snusmic-quant-terminal/blob/main/${encodeURI(path)}`;
}
