import Link from 'next/link';
import { getMissingSymbols, getOverview, getPersonas, getStrategyRuns } from '@/lib/artifacts';
import { formatKrwCompact, formatNumber, formatPercent } from '@/lib/format';

export default function HomePage() {
  const overview = getOverview();
  const personas = getPersonas();
  const follower = personas.find((row) => row.persona === 'smic_follower');
  const allWeather = personas.find((row) => row.persona === 'all_weather');
  const bestBaseline = [...personas].sort((a, b) => b.final_equity_krw - a.final_equity_krw)[0];
  const bestLocal = getStrategyRuns()[0];
  const missing = getMissingSymbols();

  if (!overview) {
    return <section className="empty"><h1>Artifacts missing</h1><p>Run <code>uv run python scripts/export_web_artifacts.py --check</code> first.</p></section>;
  }

  return (
    <>
      <section className="hero two-col">
        <div>
          <div className="eyebrow">Artifact-first research lab</div>
          <h1>SMIC 리포트를 발간일 기준으로 따라 샀다면?</h1>
          <p>PDF에서 추출한 목표가, 발간일 가격, 이후 가격 경로, 목표가 도달 여부를 한 화면에서 확인하는 공개용 리서치 랩입니다.</p>
        </div>
        <div className="card accent-card">
          <div className="muted">SMIC Follower 최종 평가금</div>
          <div className="mega">{formatKrwCompact(follower?.final_equity_krw)}</div>
          <p>All-Weather: {formatKrwCompact(allWeather?.final_equity_krw)} · 최고 baseline: {bestBaseline?.label}</p>
        </div>
      </section>
      <section className="grid cards">
        <Metric label="원천 리포트" value={formatNumber(overview.report_counts.extracted_reports)} />
        <Metric label="가격 매칭 리포트" value={formatNumber(overview.report_counts.price_matched_reports)} />
        <Metric label="목표가 도달률" value={formatPercent(overview.target_stats.target_hit_rate)} />
        <Metric label="누락 가격 심볼" value={formatNumber(missing.length)} tone={missing.length ? 'warn' : 'good'} />
        <Metric label="로컬 Optuna 최고" value={bestLocal ? formatKrwCompact(bestLocal.metrics.final_equity_krw) : '준비 전'} />
      </section>
      <section className="panel spaced">
        <h2>Baseline personas</h2>
        <div className="table-wrap">
          <table>
            <thead><tr><th>Persona</th><th>최종 평가금</th><th>순이익</th><th>MWR</th><th>MDD</th><th>거래 수</th></tr></thead>
            <tbody>{personas.map((row) => <tr key={row.persona}><td>{row.label}<div className="muted">{row.persona}</div></td><td>{formatKrwCompact(row.final_equity_krw)}</td><td>{formatKrwCompact(row.net_profit_krw)}</td><td>{formatPercent(row.money_weighted_return)}</td><td className="bad">{formatPercent(row.max_drawdown)}</td><td>{formatNumber(row.trade_count)}</td></tr>)}</tbody>
          </table>
        </div>
      </section>
      <section className="grid cards spaced">
        <Link className="card link-card" href="/reports"><h2>리포트 탐색</h2><p>비에이치, DL이앤씨, Chegg 등 모든 리포트를 검색하고 수익률/목표가 도달 여부로 정렬합니다.</p></Link>
        <Link className="card link-card" href="/strategies"><h2>전략 비교</h2><p>로컬 Optuna가 찾은 SMIC follower 변형을 baseline과 비교합니다.</p></Link>
        <Link className="card link-card" href="/data-quality"><h2>데이터 품질</h2><p>누락 심볼, 추출 경고, lookahead bias를 숨기지 않고 표시합니다.</p></Link>
      </section>
    </>
  );
}

function Metric({ label, value, tone }: { label: string; value: string; tone?: 'good' | 'bad' | 'warn' }) {
  return <div className="card"><div className="muted">{label}</div><div className={`metric ${tone ?? ''}`}>{value}</div></div>;
}
