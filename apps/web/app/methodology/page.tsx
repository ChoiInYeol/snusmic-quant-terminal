import { Panel, TerminalHero } from '@/components/ui/Terminal';

export default function MethodologyPage() {
  return (
    <>
      <TerminalHero eyebrow="Methodology" title="Python은 계산하고, Next.js는 설명합니다.">
        <p>웹 앱은 기존 SNUSMIC 파이프라인의 정적 아티팩트 뷰어이며 두 번째 시뮬레이션 엔진이 아닙니다.</p>
      </TerminalHero>
      <section className="grid">
        <Panel title="파이프라인 경계">
          <p>SNUSMIC PDF를 다운로드해 Markdown으로 변환하고, 목표가·티커·발간일을 CSV로 추출한 뒤, 가격을 KRW로 정규화해 Python 시뮬레이션이 리포트와 페르소나 아티팩트를 <code>data/</code> 아래에 작성합니다.</p>
        </Panel>
        <Panel title="리포트 증거 모델">
          <p>상세 페이지는 <code>data/sim/report_performance.csv</code>, <code>data/warehouse/reports.csv</code>, Markdown 스니펫, <code>data/warehouse/daily_prices.csv</code>를 조인합니다. 차트는 발간일, 추출 목표가, 목표가 도달일을 함께 표시합니다.</p>
        </Panel>
        <Panel title="전략 정직성">
          <p>Oracle/prophet 페르소나는 미래 정보를 가진 상한선입니다. SMIC follower 페르소나는 기계적 기준선입니다. Optuna 탐색은 로컬에서만 실행하고 공개 웹에는 아티팩트만 내보냅니다.</p>
        </Panel>
        <Panel title="정적 배포">
          <p>Next.js는 static export를 사용합니다. 공개 앱은 Optuna, 시장 데이터 갱신, PDF 파싱을 트리거하지 않고 재현 가능한 스냅샷만 제공합니다.</p>
        </Panel>
      </section>
    </>
  );
}
