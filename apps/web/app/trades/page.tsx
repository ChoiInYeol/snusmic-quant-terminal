import { TradesTable } from '@/components/trading/TradesTable';
import { MetricCard, TerminalHero } from '@/components/ui/Terminal';
import { getPersonaLabel, getPositionEpisodes, getSummaryRows, getTrades } from '@/lib/artifacts';
import { formatKrw } from '@/lib/format';

export default function TradesPage() {
  const trades = getTrades();
  const episodes = getPositionEpisodes();
  const summaries = getSummaryRows();
  const personas = Array.from(new Set(trades.map((trade) => trade.persona))).sort();
  const personaLabels = Object.fromEntries(personas.map((persona) => [persona, getPersonaLabel(persona)]));
  const capitalByPersona = Object.fromEntries(summaries.map((row) => [row.persona, row.totalContributedKrw ?? row.finalEquityKrw ?? 0]));
  const buyCount = trades.filter((trade) => trade.side === 'buy').length;
  const sellCount = trades.filter((trade) => trade.side === 'sell').length;
  const realizedPnl = episodes.reduce((sum, episode) => sum + (episode.realizedPnlKrw ?? 0), 0);
  const openEpisodes = episodes.filter((episode) => episode.status !== 'closed').length;

  return (
    <>
      <TerminalHero eyebrow="Trading ledger" title="언제 사고, 언제 팔았는지부터 봅니다.">
        <p>리포트 쇼케이스가 아니라 매매 제품 기준의 원장입니다. 포지션 단위 요약과 체결 단위 로그를 함께 제공하고, 필터된 결과는 CSV로 내려받을 수 있습니다.</p>
      </TerminalHero>
      <section className="grid cards bento-metrics" style={{ marginBottom: '1rem' }}>
        <MetricCard label="총 체결" value={trades.length.toLocaleString('ko-KR')} detail={`매수 ${buyCount.toLocaleString('ko-KR')} · 매도 ${sellCount.toLocaleString('ko-KR')}`} />
        <MetricCard label="포지션 에피소드" value={episodes.length.toLocaleString('ko-KR')} detail={`현재 보유 ${openEpisodes.toLocaleString('ko-KR')}건`} tone="accent" />
        <MetricCard label="실현 손익 합계" value={formatKrw(realizedPnl)} tone={realizedPnl >= 0 ? 'good' : 'bad'} />
      </section>
      <TradesTable trades={trades} episodes={episodes} personaLabels={personaLabels} capitalByPersona={capitalByPersona} />
    </>
  );
}
