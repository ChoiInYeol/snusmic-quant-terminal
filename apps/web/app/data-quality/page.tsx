import { getDataQuality, getOverview, getReportRows, getWebDataQuality } from '@/lib/artifacts';
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
      <section className="hero">
        <div className="eyebrow">데이터 품질</div>
        <h1>누락·제외·검토 사유를 숨기지 않습니다.</h1>
        <p>
          리포트 추출 커버리지, 가격 매칭, 목표가 도달 상태, 수동 검토 사유를 한 곳에 공개합니다.
          이 페이지는 모델 주장을 강화하기 위한 장식이 아니라 표본의 한계를 드러내기 위한 감사 로그입니다.
        </p>
      </section>

      <section className="grid cards" style={{ marginBottom: '1rem' }}>
        <div className="card"><div className="muted">추출 리포트</div><div className="metric">{quality.extractedReports.toLocaleString('ko-KR')}</div><p>warehouse reports {coverage.warehouse_reports ?? overview.report_counts?.web_report_rows ?? '—'}</p></div>
        <div className="card"><div className="muted">성과 산출 행</div><div className="metric">{quality.totalReports.toLocaleString('ko-KR')}</div><p>performance rows {coverage.report_performance_rows ?? quality.totalReports}</p></div>
        <div className="card"><div className="muted">가격 매칭</div><div className="metric good">{quality.reportsWithPrices.toLocaleString('ko-KR')}</div><p>미매칭 심볼 {quality.missingPriceSymbols.toLocaleString('ko-KR')}개</p></div>
        <div className="card"><div className="muted">목표 도달률</div><div className="metric">{formatPercent(quality.targetHitRate)}</div><p>open / 미도달 {openRows.length.toLocaleString('ko-KR')}건</p></div>
      </section>

      <section className="grid two-col" style={{ marginBottom: '1rem' }}>
        <Distribution title="투자의견 분포" rows={ratingCounts} />
        <Distribution title="통화 분포" rows={currencyCounts} />
      </section>

      <section className="panel" style={{ marginBottom: '1rem' }}>
        <h2>검토 사유</h2>
        <div className="tag-row">
          {Object.entries(reasonCounts).length ? Object.entries(reasonCounts).map(([key, value]) => (
            <span className="pill" key={key}>{translateReason(key)} · {String(value)}</span>
          )) : <span className="pill">검토 사유 없음</span>}
        </div>
      </section>

      <section className="panel" style={{ marginBottom: '1rem' }}>
        <h2>가격 미매칭 심볼</h2>
        {webQuality.missing_symbols?.length ? (
          <div className="tag-row">
            {webQuality.missing_symbols.map((item) => <span className="pill" key={item.symbol}>{item.symbol}{item.company ? ` · ${item.company}` : ''}</span>)}
          </div>
        ) : <p>현재 공개된 missing-symbol artifact가 없거나 미매칭 심볼이 없습니다.</p>}
      </section>

      <section className="panel">
        <h2>수동 검토 샘플</h2>
        <div className="table-wrap inset">
          <table>
            <thead><tr><th>회사</th><th>티커</th><th>의견</th><th>목표가</th><th>사유</th></tr></thead>
            <tbody>
              {reviewRows.map((row, index) => {
                const item = row as Record<string, unknown>;
                return (
                  <tr key={`${String(item.ticker)}-${index}`}>
                    <td>{String(item.company ?? '—')}</td>
                    <td>{String(item.ticker ?? '—')}</td>
                    <td>{String(item.rating || '누락')}</td>
                    <td>{String(item.base_target ?? '—')}</td>
                    <td>{Array.isArray(item.reasons) ? item.reasons.map(String).join(', ') : String(item.reasons ?? '—')}</td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      </section>
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
