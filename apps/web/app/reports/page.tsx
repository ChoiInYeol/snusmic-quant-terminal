import Link from 'next/link';
import { MetricCard, StatusPill, TerminalHero } from '@/components/ui/Terminal';
import { getReportRows } from '@/lib/artifacts';
import { formatDays, formatKrw, formatMultiple, formatPercent } from '@/lib/format';

export default function ReportsPage() {
  const reports = getReportRows();
  const targetHitCount = reports.filter((report) => report.targetHit).length;
  const positiveReturnCount = reports.filter((report) => (report.currentReturn ?? -Infinity) >= 0).length;
  const latestDate = reports.reduce((latest, report) => report.publicationDate > latest ? report.publicationDate : latest, '');

  return (
    <>
      <TerminalHero eyebrow="Report explorer" title="모든 추출 리포트를 가격 증거와 함께 봅니다.">
        <p>실현 수익률 기준 상위 행을 먼저 보여줍니다. 상세 페이지는 발간일 마커, 목표가 선, 도달일, 시뮬레이션에 사용된 Markdown 증거를 함께 표시합니다.</p>
      </TerminalHero>
      <section className="grid cards" style={{ marginBottom: '1rem' }}>
        <MetricCard label="표시 행" value={topRows.length.toLocaleString('ko-KR')} detail={`전체 ${reports.length.toLocaleString('ko-KR')}개 가격 매칭 리포트 중`} />
        <MetricCard label="목표가 도달" value={reports.filter((report) => report.targetHit).length.toLocaleString('ko-KR')} tone="good" />
        <MetricCard label="미도달/진행 중" value={reports.filter((report) => !report.targetHit).length.toLocaleString('ko-KR')} tone="warn" />
      </section>
      <div className="table-wrap">
        <table>
          <thead>
            <tr><th>리포트</th><th>발간일</th><th>진입가</th><th>목표가</th><th>제시 업사이드</th><th>실현 수익률</th><th>도달 증거</th></tr>
          </thead>
          <tbody>
            {topRows.map((report) => (
              <tr key={report.reportId}>
                <td><Link href={`/reports/${report.reportId}`}>{report.company}</Link><div className="muted">{report.symbol} · {report.exchange}</div></td>
                <td>{report.publicationDate}</td>
                <td>{formatKrw(report.entryPriceKrw)}</td>
                <td>{formatKrw(report.targetPriceKrw)}</td>
                <td>{formatMultiple(report.targetUpsideAtPub, 2)}</td>
                <td className={(report.currentReturn ?? 0) >= 0 ? 'good' : 'bad'}>{formatPercent(report.currentReturn)}</td>
                <td>{report.targetHit ? <StatusPill tone="good">{formatDays(report.daysToTarget)} 만에 도달</StatusPill> : <StatusPill>미도달</StatusPill>}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </>
  );
}
