import { ReportsTable } from '@/components/reports/ReportsTable';
import { MetricCard, TerminalHero } from '@/components/ui/Terminal';
import { getReportRows } from '@/lib/artifacts';
import { formatPercent } from '@/lib/format';

export default function ReportsPage() {
  const reports = getReportRows();
  const targetHitCount = reports.filter((report) => report.targetHit).length;
  const positiveReturnCount = reports.filter((report) => (report.currentReturn ?? -Infinity) >= 0).length;
  const latestDate = reports.reduce((latest, report) => report.publicationDate > latest ? report.publicationDate : latest, '');

  return (
    <>
      <TerminalHero eyebrow="Report explorer" title="모든 추출 리포트를 정렬·필터·CSV로 검토합니다.">
        <p>기업명/심볼 검색, 거래소·목표달성·수익률 필터, 열 정렬, 전체/현재 보기 CSV 다운로드를 제공합니다. 상세 페이지는 Lightweight Charts 기반 가격 경로와 Markdown 증거를 함께 표시합니다.</p>
      </TerminalHero>
      <section className="grid cards" style={{ marginBottom: '1rem' }}>
        <MetricCard label="전체 행" value={reports.length.toLocaleString('ko-KR')} detail={`최신 발간일 ${latestDate || '—'}`} />
        <MetricCard label="목표가 도달" value={targetHitCount.toLocaleString('ko-KR')} detail={formatPercent(targetHitCount / Math.max(1, reports.length))} tone="good" />
        <MetricCard label="현재 플러스" value={positiveReturnCount.toLocaleString('ko-KR')} detail={formatPercent(positiveReturnCount / Math.max(1, reports.length))} tone="accent" />
      </section>
      <ReportsTable reports={reports} />
    </>
  );
}
