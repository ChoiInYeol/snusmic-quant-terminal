import { ReportsTable } from '@/components/reports/ReportsTable';
import { getReportRows } from '@/lib/artifacts';
import { formatPercent } from '@/lib/format';

export default function ReportsPage() {
  const reports = getReportRows();
  const targetHitCount = reports.filter((report) => report.targetHit).length;
  const positiveReturnCount = reports.filter((report) => (report.currentReturn ?? -Infinity) >= 0).length;
  const latestDate = reports.reduce((latest, report) => report.publicationDate > latest ? report.publicationDate : latest, '');

  return (
    <>
      <section className="hero">
        <div className="eyebrow">리포트 탐색기</div>
        <h1>추출된 SNUSMIC 리포트를 한눈에 검증합니다.</h1>
        <p>
          기업명·심볼 검색, 거래소/목표 달성/현재 수익률 필터, 열별 정렬을 지원합니다. 현재 필터 결과만
          내려받거나 전체 데이터셋을 CSV로 내려받아 Google Sheets에서 이어서 분석할 수 있습니다.
        </p>
      </section>
      <section className="grid cards" style={{ marginBottom: '1rem' }}>
        <div className="card"><div className="muted">가격 매칭 리포트</div><div className="metric">{reports.length.toLocaleString('ko-KR')}</div><p>시뮬레이션 성과 테이블 기준</p></div>
        <div className="card"><div className="muted">목표가 달성</div><div className="metric good">{targetHitCount.toLocaleString('ko-KR')}</div><p>{formatPercent(targetHitCount / Math.max(1, reports.length))}</p></div>
        <div className="card"><div className="muted">현재 플러스 수익률</div><div className="metric warn">{positiveReturnCount.toLocaleString('ko-KR')}</div><p>{formatPercent(positiveReturnCount / Math.max(1, reports.length))}</p></div>
        <div className="card"><div className="muted">최신 게시일</div><div className="metric">{latestDate || '—'}</div><p>정적 artifact에서 직접 렌더링</p></div>
      </section>
      <ReportsTable reports={reports} />
    </>
  );
}
