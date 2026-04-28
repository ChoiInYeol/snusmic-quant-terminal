import { Panel, TerminalHero } from '@/components/ui/Terminal';

export default function LabPage() {
  return (
    <>
      <TerminalHero eyebrow="Research lab" title="로컬 전략 탐색 워크플로우">
        <p>Optuna와 전략 탐색은 Python 로컬 환경에서만 실행됩니다. 배포된 웹 앱은 정적 JSON 내보내기를 읽을 뿐 Optuna, yfinance, 시뮬레이션 코드를 가져오지 않습니다.</p>
      </TerminalHero>
      <Panel title="재현 절차">
        <ol>
          <li><code>uv run python scripts/run_optuna_search.py --trials 100</code>로 로컬 탐색을 실행합니다.</li>
          <li><code>uv run python scripts/export_optuna_artifacts.py</code>로 웹 아티팩트를 내보냅니다.</li>
          <li><code>/strategies</code>에서 in-sample 결과와 위험 경고 배지를 검토합니다.</li>
        </ol>
      </Panel>
    </>
  );
}
