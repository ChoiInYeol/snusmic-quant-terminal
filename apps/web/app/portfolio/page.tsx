import { PortfolioTables } from '@/components/trading/PortfolioTables';
import { MetricCard, TerminalHero } from '@/components/ui/Terminal';
import { getCurrentHoldings, getMonthlyHoldings, getPersonaLabel, getSummaryRows } from '@/lib/artifacts';
import { formatKrw, formatPercent } from '@/lib/format';

export default function PortfolioPage() {
  const holdings = getCurrentHoldings();
  const monthly = getMonthlyHoldings();
  const summaries = getSummaryRows();
  const personas = Array.from(new Set(holdings.map((row) => row.persona))).sort();
  const personaLabels = Object.fromEntries(personas.map((persona) => [persona, getPersonaLabel(persona)]));
  const capitalByPersona = Object.fromEntries(summaries.map((row) => [row.persona, row.totalContributedKrw ?? row.finalEquityKrw ?? 0]));
  const totalValue = holdings.reduce((sum, row) => sum + (row.marketValueKrw ?? 0), 0);
  const totalPnl = holdings.reduce((sum, row) => sum + (row.unrealizedPnlKrw ?? 0), 0);
  const latestMonth = monthly.reduce((latest, row) => row.monthEnd > latest ? row.monthEnd : latest, '');

  return (
    <>
      <TerminalHero eyebrow="Portfolio book" title="지금 무엇을 보유하고, 과거엔 무엇을 들고 있었나.">
        <p>현재 포트폴리오와 월말 스냅샷을 전략별로 확인합니다. 핵심 질문은 성과 설명이 아니라 “현재 어떤 위험을 들고 있는가”입니다.</p>
      </TerminalHero>
      <section className="grid cards bento-metrics" style={{ marginBottom: '1rem' }}>
        <MetricCard label="현재 보유 종목" value={holdings.length.toLocaleString('ko-KR')} detail={`${personas.length}개 전략`} />
        <MetricCard label="평가액 합계" value={formatKrw(totalValue)} tone="accent" />
        <MetricCard label="미실현 손익" value={formatKrw(totalPnl)} detail={formatPercent(totalPnl / Math.max(1, totalValue - totalPnl))} tone={totalPnl >= 0 ? 'good' : 'bad'} />
        <MetricCard label="최신 월말 스냅샷" value={latestMonth || '—'} />
      </section>
      <PortfolioTables holdings={holdings} monthly={monthly} personaLabels={personaLabels} capitalByPersona={capitalByPersona} />
    </>
  );
}
