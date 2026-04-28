import type { Metadata } from 'next';
import Link from 'next/link';
import { notFound } from 'next/navigation';
import { PriceEvidenceChart } from '@/components/charts/PriceEvidenceChart';
import { getMarkdownSnippet, getPriceSeries, getReportById, getReportRows, type PricePoint, type ReportRow } from '@/lib/artifacts';
import { formatDays, formatKrw, formatPercent } from '@/lib/format';

export function generateStaticParams() {
  return getReportRows().map((report) => ({ reportId: report.reportId }));
}

export function generateMetadata({ params }: { params: { reportId: string } }): Metadata {
  const report = getReportById(params.reportId);
  return { title: report ? `${report.company} 리포트 검증` : '리포트 검증' };
}

export default function ReportDetailPage({ params }: { params: { reportId: string } }) {
  const report = getReportById(params.reportId);
  if (!report) notFound();
  const prices = getPriceSeries(report.symbol, report.publicationDate, report.lastCloseDate);
  const snippet = getMarkdownSnippet(report);
  const pathEvidence = buildPathEvidence(prices, report);
  const memo = buildKoreanInvestmentMemo(report);

  return (
    <>
      <section className="hero">
        <div className="eyebrow"><Link href="/reports">← 리포트 목록</Link></div>
        <h1>{report.company}</h1>
        <p>{report.title} · {report.symbol} · 발간일 {report.publicationDate}</p>
      </section>
      <section className="grid cards" style={{ marginBottom: '1rem' }}>
        <div className="card"><div className="muted">진입 종가</div><div className="metric">{formatKrw(report.entryPriceKrw)}</div></div>
        <div className="card"><div className="muted">추출 목표가</div><div className="metric">{formatKrw(report.targetPriceKrw)}</div><p>발간 시점 대비 {formatPercent(report.targetUpsideAtPub)} 업사이드</p></div>
        <div className="card"><div className="muted">현재 수익률</div><div className={`metric ${(report.currentReturn ?? 0) >= 0 ? 'good' : 'bad'}`}>{formatPercent(report.currentReturn)}</div></div>
        <div className="card"><div className="muted">목표가 판정</div><div className="metric">{report.targetHit ? '도달' : '미도달'}</div><p>{report.targetHit ? `${report.targetHitDate} · ${formatDays(report.daysToTarget)}` : `잔여 갭 ${formatPercent(report.targetGapPct)}`}</p></div>
      </section>
      <section className="detail-grid">
        <div className="panel">
          <h2>목표가 대비 가격 경로</h2>
          <p>
            발간일, 목표가 도달일, 관측 고점/저점을 한 차트에 표시했습니다. 마우스를 올리면 해당일 종가와
            목표가까지 남은 갭을 확인할 수 있습니다.
          </p>
          <PriceEvidenceChart
            priceSeries={prices}
            targetPrice={report.targetPriceKrw}
            publicationDate={report.publicationDate}
            targetHitDate={report.targetHitDate}
            evidenceMarkers={pathEvidence.markers}
          />
        </div>
        <aside className="grid">
          <div className="panel">
            <h2>경로 통계</h2>
            <div className="stat-row"><span className="muted">최고 수익률</span><strong className="good">{formatPercent(report.peakReturn)}</strong></div>
            <div className="stat-row"><span className="muted">최저 수익률</span><strong className="bad">{formatPercent(report.troughReturn)}</strong></div>
            <div className="stat-row"><span className="muted">관측 고점</span><strong>{pathEvidence.peak ? `${formatKrw(pathEvidence.peak.value)} · ${pathEvidence.peak.time}` : '—'}</strong></div>
            <div className="stat-row"><span className="muted">관측 저점</span><strong>{pathEvidence.trough ? `${formatKrw(pathEvidence.trough.value)} · ${pathEvidence.trough.time}` : '—'}</strong></div>
            <div className="stat-row"><span className="muted">마지막 종가</span><strong>{formatKrw(report.lastCloseKrw)} · {report.lastCloseDate ?? '—'}</strong></div>
            {report.pdfUrl ? <p><a href={report.pdfUrl}>원문 PDF source →</a></p> : null}
          </div>
          <div className="panel">
            <h2>투자 메모</h2>
            <p>{memo.summary}</p>
            <ul className="memo-list">
              {memo.bullets.map((bullet) => <li key={bullet.label}><strong>{bullet.label}</strong> — {bullet.text}</li>)}
            </ul>
          </div>
          <div className="panel">
            <h2>추출 Markdown 근거</h2>
            <div className="markdown-snippet">{snippet}</div>
          </div>
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
  const targetSentence = report.targetHit
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
