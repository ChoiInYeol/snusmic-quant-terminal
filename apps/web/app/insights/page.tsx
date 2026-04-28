import Link from 'next/link';
import { getOverview, getReportRankings, getStrategyRuns, getSummaryRows } from '@/lib/artifacts';
import { formatDays, formatKrw, formatKrwMillions, formatPercent } from '@/lib/format';

export default function InsightsPage() {
  const overview = getOverview();
  const rankings = getReportRankings();
  const personas = getSummaryRows();
  const strategies = getStrategyRuns();
  const follower = personas.find((row) => row.persona === 'smic_follower');
  const followerV2 = personas.find((row) => row.persona === 'smic_follower_v2');
  const allWeather = personas.find((row) => row.persona === 'all_weather');
  const bestStrategy = strategies.runs.find((run) => run.run_id === strategies.best_run_id) ?? strategies.runs[0];

  return (
    <>
      <section className="hero">
        <div className="eyebrow">핵심 인사이트</div>
        <h1>추천 리포트는 맞았는가, 투자 전략은 견뎠는가.</h1>
        <p>
          목표가 도달·현재 수익률·전략 손익을 한 화면에서 연결합니다. Oracle 계열은 미래 정보를 쓰는 상한선,
          SMIC follower 계열은 실제 운용에 가까운 기계적 기준선으로 구분합니다.
        </p>
      </section>

      <section className="grid cards" style={{ marginBottom: '1rem' }}>
        <div className="card"><div className="muted">목표가 도달</div><div className="metric good">{overview.target_stats?.target_hit_count ?? '—'}</div><p>{formatPercent(overview.target_stats?.target_hit_rate)} of matched reports</p></div>
        <div className="card"><div className="muted">중앙 현재 수익률</div><div className="metric">{formatPercent(overview.target_stats?.median_current_return)}</div><p>평균 {formatPercent(overview.target_stats?.avg_current_return)}</p></div>
        <div className="card"><div className="muted">중앙 목표 도달일</div><div className="metric">{formatDays(overview.target_stats?.median_days_to_target)}</div><p>평균 {formatDays(overview.target_stats?.avg_days_to_target)}</p></div>
        <div className="card"><div className="muted">시뮬레이션 기간</div><div className="metric small-metric">{overview.simulation_window?.report_start ?? '—'}</div><p>~ {overview.simulation_window?.report_end ?? '—'}</p></div>
      </section>

      <section className="grid two-col" style={{ marginBottom: '1rem' }}>
        <article className="panel">
          <h2>실전형 follower 개선</h2>
          <p>
            기본 follower는 {follower ? formatKrwMillions(follower.finalEquityKrw) : '—'}까지 성장했고,
            손절 규칙을 추가한 v2는 {followerV2 ? formatKrwMillions(followerV2.finalEquityKrw) : '—'}를 기록했습니다.
            단순 4자산 all-weather 기준선은 {allWeather ? formatKrwMillions(allWeather.finalEquityKrw) : '—'}입니다.
          </p>
          <p><Link href="/strategies">전략 리더보드로 이동 →</Link></p>
        </article>
        <article className="panel">
          <h2>탐색 전략은 후보일 뿐입니다</h2>
          <p>
            최고 전략 {bestStrategy?.label ?? '—'}의 점수는 {formatPercent(bestStrategy?.metrics.score, 1)}입니다.
            하지만 인샘플 탐색 결과이므로, 배포 화면은 경고와 파라미터를 함께 노출합니다.
          </p>
        </article>
      </section>

      <RankingSection title="상위 수익 리포트" rows={rankings.top_winners ?? []} metric="current" />
      <RankingSection title="하위 수익 리포트" rows={rankings.top_losers ?? []} metric="current" />
      <RankingSection title="가장 공격적인 목표가" rows={rankings.most_aggressive_targets ?? []} metric="upside" />
    </>
  );
}

type RankingRow = {
  report_id: string;
  company: string;
  symbol: string;
  publication_date: string;
  entry_price_krw: number | null;
  target_price_krw: number | null;
  current_return: number | null;
  target_upside_at_pub: number | null;
  target_hit: boolean;
};

function RankingSection({ title, rows, metric }: { title: string; rows: RankingRow[]; metric: 'current' | 'upside' }) {
  return (
    <section className="panel" style={{ marginTop: '1rem' }}>
      <h2>{title}</h2>
      <div className="table-wrap inset">
        <table>
          <thead><tr><th>회사</th><th>발간일</th><th>진입가</th><th>목표가</th><th>{metric === 'current' ? '현재 수익률' : '제시 업사이드'}</th><th>목표 도달</th></tr></thead>
          <tbody>
            {rows.slice(0, 6).map((row) => {
              const value = metric === 'current' ? row.current_return : row.target_upside_at_pub;
              return (
                <tr key={row.report_id}>
                  <td><Link href={`/reports/${row.report_id}`}>{row.company}</Link><div className="muted">{row.symbol}</div></td>
                  <td>{row.publication_date}</td>
                  <td>{formatKrw(row.entry_price_krw)}</td>
                  <td>{formatKrw(row.target_price_krw)}</td>
                  <td className={(value ?? 0) >= 0 ? 'good' : 'bad'}>{formatPercent(value)}</td>
                  <td>{row.target_hit ? <span className="pill good">hit</span> : <span className="pill">open</span>}</td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
    </section>
  );
}
