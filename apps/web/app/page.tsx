import { MetricCard, Panel, TerminalHero, TerminalLink } from '@/components/ui/Terminal';
import { getDataQuality, getReportRows, getSummaryRows } from '@/lib/artifacts';
import { formatKrwMillions, formatPercent } from '@/lib/format';

export default function HomePage() {
  const reports = getReportRows();
  const quality = getDataQuality();
  const summaries = getSummaryRows();
  const overview = getOverview();
  const rankings = getReportRankings();
  const strategies = getStrategyRuns();
  const bestPersona = summaries.find((row) => row.persona === 'smic_follower_v2') ?? summaries[0];
  const bestStrategy = strategies.runs.find((run) => run.run_id === strategies.best_run_id) ?? strategies.runs[0];
  const topWinner = rankings.top_winners?.[0];
  const hitRate = reports.filter((report) => report.targetHit).length / Math.max(1, reports.length);

  return (
    <>
      <TerminalHero
        eyebrow="Artifact-first Korean terminal"
        title="SMIC 리포트를 검증 가능한 투자 근거로 번역합니다."
        actions={<><TerminalLink href="/reports">리포트 탐색 →</TerminalLink><TerminalLink href="/data-quality">품질 점검 →</TerminalLink></>}
      >
        <p>
          추출된 목표가, 발간일 진입가, 실제 가격 경로, 목표가 도달 여부와 데이터 한계를 한 화면에서 확인하는 정적 리서치 터미널입니다.
        </p>
      </TerminalHero>
      <section className="grid cards">
        <MetricCard label="가격 매칭 리포트" value={reports.length.toLocaleString('ko-KR')} tone="accent" />
        <MetricCard label="목표가 도달률" value={formatPercent(hitRate)} tone="good" />
        <MetricCard label="추출 리포트" value={quality.extractedReports.toLocaleString('ko-KR')} />
        <MetricCard label="상위 페르소나" value={bestPersona?.persona ?? '—'} detail={bestPersona ? formatKrwMillions(bestPersona.finalEquityKrw) : '먼저 시뮬레이션 아티팩트를 생성하세요.'} tone="warn" />
      </section>
      <Panel title="터미널 운영 원칙" className="" >
        <p>
          Python 파이프라인은 계산 엔진으로 남기고, Next.js는 커밋된 CSV/JSON/Markdown 결과만 읽습니다. 그래서 Vercel·GitHub Pages 정적 배포에서도 동일한 스냅샷을 재현할 수 있습니다.
        </p>
      </Panel>
    </>
  );
}
