import { MetricCard, Panel, TerminalHero } from '@/components/ui/Terminal';
import { getDataQuality, getReportRows } from '@/lib/artifacts';
import { formatPercent } from '@/lib/format';

export default function DataQualityPage() {
  const quality = getDataQuality();
  const webQuality = getWebDataQuality();
  const overview = getOverview();
  const reports = getReportRows();
  const openRows = reports.filter((report) => !report.targetHit && report.lastCloseKrw !== null);
  const coverage = webQuality.coverage ?? {};
  const extraction = webQuality.extraction_quality ?? quality.extractionQuality;
  const ratingCounts = asRecord(extraction.rating_counts);
  const currencyCounts = asRecord(extraction.currency_counts);
  const reasonCounts = asRecord(extraction.reason_counts);
  const reviewRows = Array.isArray(extraction.review_rows) ? extraction.review_rows.slice(0, 8) : [];

  return (
    <>
      <TerminalHero eyebrow="Data quality" title="제외와 한계를 숨기지 않습니다.">
        <p>추출 커버리지, 가격 매칭, 목표가 도달 상태, 데이터 주의사항을 함께 노출해 설득보다 증거에 가까운 대시보드를 유지합니다.</p>
      </TerminalHero>
      <section className="grid cards">
        <MetricCard label="추출 리포트" value={quality.extractedReports.toLocaleString('ko-KR')} />
        <MetricCard label="리포트 통계 모집단" value={quality.totalReports.toLocaleString('ko-KR')} />
        <MetricCard label="가격 매칭" value={quality.reportsWithPrices.toLocaleString('ko-KR')} tone="accent" />
        <MetricCard label="목표가 도달률" value={formatPercent(quality.targetHitRate)} tone="good" />
      </section>
      <Panel title="현재 주의사항">
        <ul>
          <li>{quality.missingPriceSymbols.toLocaleString('ko-KR')}개 심볼은 시뮬레이션 집계에서 가격 누락 심볼로 보고됩니다.</li>
          <li>{openRows.length.toLocaleString('ko-KR')}개 가격 매칭 행은 마지막 종가 기준 추출 목표가에 도달하지 못했습니다.</li>
          <li>리포트 단위 비교 전에 목표가와 가격은 KRW 기준으로 정규화됩니다.</li>
          <li>모든 웹 페이지는 커밋된 아티팩트만 읽는 정적 뷰어이며, 시장 데이터 갱신이나 시뮬레이션 변경을 수행하지 않습니다.</li>
        </ul>
      </Panel>
      <Panel title="원본 추출 품질 아티팩트">
        <pre className="markdown-snippet">{JSON.stringify(quality.extractionQuality, null, 2)}</pre>
      </Panel>
    </>
  );
}

function Distribution({ title, rows }: { title: string; rows: Record<string, unknown> }) {
  const entries = Object.entries(rows).sort(([, a], [, b]) => Number(b) - Number(a));
  const total = entries.reduce((sum, [, value]) => sum + Number(value || 0), 0);
  return (
    <section className="panel">
      <h2>{title}</h2>
      <div className="bar-list">
        {entries.map(([key, value]) => {
          const count = Number(value || 0);
          return (
            <div className="bar-row" key={key}>
              <span>{key || '누락'}</span>
              <div className="bar-track"><div className="bar-fill" style={{ width: `${total ? (count / total) * 100 : 0}%` }} /></div>
              <strong>{count.toLocaleString('ko-KR')}</strong>
            </div>
          );
        })}
      </div>
    </section>
  );
}

function asRecord(value: unknown): Record<string, unknown> {
  if (!value || typeof value !== 'object' || Array.isArray(value)) return {};
  return value as Record<string, unknown>;
}

function translateReason(reason: string): string {
  if (reason === 'missing_rating') return '투자의견 누락';
  if (reason.startsWith('non_buy_rating')) return `비매수 의견(${reason.split(':')[1] ?? ''})`;
  if (reason === 'note_case_target_ambiguous') return '케이스별 목표가 검토 필요';
  return reason;
}
