import Link from 'next/link';
import { MetricCard, Panel, TerminalHero } from '@/components/ui/Terminal';
import { getCurrentHoldings, getPositionEpisodes, getSummaryRows, getTrades } from '@/lib/artifacts';
import { formatKrw, formatPercent } from '@/lib/format';

export default function Home() {
  const personas = getSummaryRows();
  const holdings = getCurrentHoldings();
  const trades = getTrades();
  const episodes = getPositionEpisodes();
  const bestPersona = [...personas].sort((a, b) => (b.finalEquityKrw ?? 0) - (a.finalEquityKrw ?? 0))[0];
  const totalValue = holdings.reduce((sum, row) => sum + (row.marketValueKrw ?? 0), 0);
  const totalPnl = holdings.reduce((sum, row) => sum + (row.unrealizedPnlKrw ?? 0), 0);
  const latestTradeDate = trades[0]?.date ?? '—';
  const recentSells = trades.filter((trade) => trade.side === 'sell').slice(0, 5);
  const currentOpen = episodes.filter((episode) => episode.status !== 'closed').slice(0, 5);

  return (
    <>
      <TerminalHero eyebrow="Product dashboard" title="리포트가 아니라 매매 장부를 먼저 보여줍니다.">
        <p>사용자가 알고 싶은 것은 방법론 설명이 아니라 언제 샀고, 언제 팔았고, 지금 무엇을 들고 있으며, 그 근거가 어떤 리포트였는지입니다.</p>
        <div className="action-row">
          <Link className="button-link" href="/trades">매매내역 보기</Link>
          <Link className="button-link secondary" href="/portfolio">현재 포트폴리오</Link>
        </div>
      </TerminalHero>

      <section className="grid cards bento-metrics" style={{ marginBottom: '1rem' }}>
        <MetricCard label="현재 평가액" value={formatKrw(totalValue)} detail={`${holdings.length.toLocaleString('ko-KR')}개 보유 행`} tone="accent" />
        <MetricCard label="미실현 손익" value={formatKrw(totalPnl)} detail={formatPercent(totalPnl / Math.max(1, totalValue - totalPnl))} tone={totalPnl >= 0 ? 'good' : 'bad'} />
        <MetricCard label="총 체결" value={trades.length.toLocaleString('ko-KR')} detail={`최근 체결 ${latestTradeDate}`} />
        <MetricCard label="상위 전략" value={bestPersona?.label ?? '—'} detail={bestPersona ? formatKrw(bestPersona.finalEquityKrw) : '—'} tone="good" />
      </section>

      <section className="grid two-col feature-grid" style={{ marginBottom: '1rem' }}>
        <Panel title="최근 매도 체결">
          <div className="table-wrap inset compact-table">
            <table>
              <thead><tr><th>일자</th><th>전략</th><th>심볼</th><th>금액</th><th>사유</th></tr></thead>
              <tbody>{recentSells.map((trade, index) => <tr key={`${trade.date}-${trade.symbol}-${index}`}><td>{trade.date}</td><td>{trade.persona}</td><td>{trade.symbol}</td><td>{formatKrw(trade.grossKrw)}</td><td>{trade.reason}</td></tr>)}</tbody>
            </table>
          </div>
          <p><Link href="/trades">전체 체결 원장 →</Link></p>
        </Panel>
        <Panel title="현재 열린 포지션">
          <div className="table-wrap inset compact-table">
            <table>
              <thead><tr><th>전략</th><th>종목</th><th>진입일</th><th>미실현 손익</th></tr></thead>
              <tbody>{currentOpen.map((episode) => <tr key={`${episode.persona}-${episode.symbol}-${episode.openDate}`}><td>{episode.persona}</td><td>{episode.company || episode.symbol}</td><td>{episode.openDate}</td><td className={(episode.unrealizedPnlKrw ?? 0) >= 0 ? 'good' : 'bad'}>{formatKrw(episode.unrealizedPnlKrw)}</td></tr>)}</tbody>
            </table>
          </div>
          <p><Link href="/portfolio">포트폴리오 스냅샷 →</Link></p>
        </Panel>
      </section>

      <section className="grid two-col feature-grid">
        <Panel title="매수·매도 기준">
          <p>Follower 계열은 리포트 발간 후 목표가 도달, 리밸런싱, 손절/시간손절 규칙으로 거래합니다. 각 체결 행의 사유와 연결 리포트 ID를 함께 노출합니다.</p>
          <p><Link href="/strategies">전략 기준 확인 →</Link></p>
        </Panel>
        <Panel title="근거 원문">
          <p>리포트 상세 화면에서 GitHub에 저장된 Markdown/PDF와 원본 SNUSMIC PDF 링크를 제공합니다. 접근 불가능한 내부 데이터 품질 화면은 제품 내비에서 제거했습니다.</p>
          <p><Link href="/reports">리포트 근거 보기 →</Link></p>
        </Panel>
      </section>
    </>
  );
}
