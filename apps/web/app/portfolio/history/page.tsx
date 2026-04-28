import { PortfolioHistory } from '@/components/trading/PortfolioHistory';
import { MetricCard, TerminalHero, TerminalLink } from '@/components/ui/Terminal';
import { getMonthlyHoldings, getPersonaLabel } from '@/lib/artifacts';

export default function PortfolioHistoryPage() {
  const monthly = getMonthlyHoldings();
  const personas = Array.from(new Set(monthly.map((row) => row.persona))).sort();
  const months = Array.from(new Set(monthly.map((row) => row.monthEnd))).sort();
  const personaLabels = Object.fromEntries(personas.map((persona) => [persona, getPersonaLabel(persona)]));
  const latestMonth = months.at(-1) ?? '—';
  const firstMonth = months[0] ?? '—';

  return (
    <>
      <TerminalHero eyebrow="Portfolio history" title="과거 월말 포트폴리오는 별도 원장으로 봅니다.">
        <p>현재 보유 포지션과 과거 스냅샷을 분리했습니다. 특정 월말 보유 종목을 표로 보고, 100% 스택바로 전략별 비중 변화를 빠르게 비교합니다.</p>
        <TerminalLink href="/portfolio">현재 포트폴리오로 돌아가기 →</TerminalLink>
      </TerminalHero>
      <section className="grid cards bento-metrics" style={{ marginBottom: '1rem' }}>
        <MetricCard label="월말 스냅샷 행" value={monthly.length.toLocaleString('ko-KR')} detail={`${personas.length}개 전략`} tone="accent" />
        <MetricCard label="기간" value={`${firstMonth} ~ ${latestMonth}`} />
        <MetricCard label="전략 수" value={personas.length.toLocaleString('ko-KR')} />
      </section>
      <PortfolioHistory monthly={monthly} personaLabels={personaLabels} />
    </>
  );
}
