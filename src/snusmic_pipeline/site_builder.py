from __future__ import annotations

import csv
import json
import shutil
from pathlib import Path
from typing import Any


def read_csv_dicts(path: Path) -> list[dict[str, str]]:
    if not path.exists():
        return []
    with path.open(encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def read_json(path: Path) -> Any:
    if not path.exists():
        return []
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def repo_pdf_url(filename: str, repo: str = "ChoiInYeol/snusmic-google-finance-sheets", branch: str = "main") -> str:
    return f"https://github.com/{repo}/blob/{branch}/data/pdfs/{filename}"


def repo_markdown_url(filename: str, repo: str = "ChoiInYeol/snusmic-google-finance-sheets", branch: str = "main") -> str:
    return f"https://github.com/{repo}/blob/{branch}/data/markdown/{Path(filename).with_suffix('.md').name}"


def build_reports_json(data_dir: Path, public_dir: Path) -> list[dict[str, Any]]:
    reports = read_csv_dicts(data_dir / "extracted_reports.csv")
    metrics = {item.get("title", ""): item for item in read_json(data_dir / "price_metrics.json")}
    for report in reports:
        filename = report.get("PDF 파일명", "")
        report["GitHub PDF"] = repo_pdf_url(filename) if filename else ""
        report["Markdown"] = repo_markdown_url(filename) if filename else ""
        metric = metrics.get(report.get("리포트명", ""), {})
        report["Company"] = report.get("종목명", "")
        report["Report Date"] = format_kst_datetime(report.get("게시일", ""))
        report["Report Price"] = metric.get("publication_buy_price", "")
    write_json(public_dir / "data" / "reports.json", reports)
    return reports


def format_kst_datetime(value: str) -> str:
    if not value:
        return ""
    normalized = value.replace("T", " ")
    return normalized[:16]


def render_index_html() -> str:
    script = Path("site/quarto/dashboard.js").read_text(encoding="utf-8")
    css = Path("site/quarto/styles.css").read_text(encoding="utf-8")
    return f"""<!doctype html>
<html lang="ko">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>SNUSMIC Quant Terminal</title>
  <script src="https://cdn.plot.ly/plotly-2.35.2.min.js"></script>
  <style>
{css}
  </style>
</head>
<body class="vercel-app">
  <aside class="app-sidebar">
    <div class="brand-block">
      <span class="brand-kicker">SNUSMIC</span>
      <strong>Quant Terminal</strong>
      <small>candidate pool 기반 전략 운용판</small>
    </div>
    <nav class="side-nav" aria-label="dashboard sections">
      <a href="#guide">전략 가이드</a>
      <a href="#now">현재 포트폴리오</a>
      <a href="#risk">수익/리스크</a>
      <a href="#pool">풀 타임라인</a>
      <a href="#opportunity">가격 기회</a>
      <a href="#reports">리포트 아카이브</a>
    </nav>
    <div class="sidebar-note">
      GitHub는 데이터 갱신과 원본 보관을 맡고, Vercel은 이 대시보드를 빠르게 배포합니다.
    </div>
  </aside>

  <main class="app-main">
    <header class="app-hero">
      <div>
        <p class="eyebrow">Walk-forward quant dashboard</p>
        <h1>지금 무엇을 얼마나 들고 있고, 왜 들고 있는가</h1>
        <p>SNUSMIC 리포트가 쌓이는 candidate pool에서 MTT, RS, 목표가 여력, 손절/익절 조건을 통과한 종목만 execution pool로 운용합니다.</p>
      </div>
      <div id="v3OverviewStats" class="metric-grid hero-stats"></div>
    </header>

    <section id="guide" class="section-band">
      <div class="section-head">
        <div>
          <p class="eyebrow">Strategy guide</p>
          <h2>전략을 읽는 방법</h2>
        </div>
        <p>이 화면은 과거 원장보다 현재 의사결정에 초점을 둡니다. 후보군, 실제 보유, 매매 사유, 누적 성과를 같은 전략 기준으로 연결해서 봅니다.</p>
      </div>
      <div class="guide-grid">
        <article class="guide-card"><strong>1. Candidate pool</strong><span>리포트 발간 다음 거래일부터 추적 후보가 됩니다. 목표가 도달, 만료, 새 리포트가 상태를 바꿉니다.</span></article>
        <article class="guide-card"><strong>2. Execution pool</strong><span>전략 조건을 통과한 종목만 실제 보유합니다. 수익은 보유 기간에만 계산합니다.</span></article>
        <article class="guide-card"><strong>3. Weighting</strong><span>비중 최적화는 execution pool 내부에서만 쓰고, lookback 이전 데이터만 사용합니다.</span></article>
        <article class="guide-card"><strong>4. Exit</strong><span>손절, R:R 익절, 목표가 도달, 신호 이탈, 추적 만료로 실현 수익을 확정합니다.</span></article>
      </div>
    </section>

    <section id="now" class="section-band">
      <div class="section-head">
        <div>
          <p class="eyebrow">Current book</p>
          <h2>현재 포트폴리오</h2>
        </div>
        <p>선택한 전략이 지금 실제로 보유하는 종목과 비중입니다. 현금 비중은 회색으로 표시됩니다.</p>
      </div>
      <div class="toolbar sticky-toolbar">
        <select id="strategyRunSelect" aria-label="전략 선택"></select>
        <select id="strategyWeightingFilter" aria-label="비중 방식"></select>
        <select id="strategyEntryFilter" aria-label="편입 조건"></select>
        <select id="strategyLookbackFilter" aria-label="Lookback"></select>
      </div>
      <div class="dashboard-grid now-grid">
        <article id="v3BestStrategy" class="panel lead-panel"></article>
        <article class="panel">
          <h3>현재 비중</h3>
          <div id="strategyAllocationPlot" class="plotly-panel compact-plot"></div>
        </article>
      </div>
      <div class="table-wrap focus-table"><table id="strategyCurrentHoldingsTable"></table></div>
    </section>

    <section id="risk" class="section-band">
      <div class="section-head">
        <div>
          <p class="eyebrow">Performance</p>
          <h2>누적 성과와 리스크</h2>
        </div>
        <p>Equity curve와 drawdown은 분리해서 봅니다. 좋은 전략은 높은 수익보다 회복 가능한 낙폭과 일관성이 먼저 보여야 합니다.</p>
      </div>
      <div class="dashboard-grid two">
        <article class="panel"><h3>누적 자산</h3><div id="strategyEquityPlot" class="plotly-panel"></div></article>
        <article class="panel"><h3>최대낙폭</h3><div id="strategyDrawdownPlot" class="plotly-panel"></div></article>
      </div>
      <div class="dashboard-grid two">
        <article class="panel"><h3>전략 수익/낙폭 지도</h3><div id="strategyRiskMapPlot" class="plotly-panel"></div></article>
        <article class="panel"><h3>전략 순위</h3><div class="table-wrap embedded"><table id="strategyLeaderboardTable"></table></div></article>
      </div>
    </section>

    <section id="pool" class="section-band">
      <div class="section-head">
        <div>
          <p class="eyebrow">Pool ledger</p>
          <h2>편입·편출 타임라인</h2>
        </div>
        <p>후보군과 실제 보유는 다릅니다. 최신 매매와 현재 포지션을 먼저 보고, 후보 변화는 필요할 때만 내려가서 봅니다.</p>
      </div>
      <div class="toolbar">
        <select id="poolRunSelect" aria-label="풀 전략 선택"></select>
        <input id="poolSearch" placeholder="종목, 사유, 이벤트 검색">
      </div>
      <div class="dashboard-grid two">
        <article class="panel"><h3>후보군 vs 실제 보유</h3><div id="poolTimelinePlot" class="plotly-panel"></div></article>
        <article class="panel"><h3>현재 비중 재확인</h3><div id="holdingsAreaPlot" class="plotly-panel"></div></article>
      </div>
      <div class="dashboard-grid two table-grid">
        <article class="panel"><h3>최근 매매</h3><div class="table-wrap embedded"><table id="tradeJournalTable"></table></div></article>
        <article class="panel"><h3>후보군 최근 변화</h3><div class="table-wrap embedded"><table id="candidateEventsTable"></table></div></article>
      </div>
      <div class="table-wrap"><table id="positionLedgerTable"></table></div>
    </section>

    <section id="opportunity" class="section-band">
      <div class="section-head">
        <div>
          <p class="eyebrow">Price opportunity</p>
          <h2>리포트별 가격 기회</h2>
        </div>
        <p>발간일 종가, 발간 이후 저가, Q25/Q75 가격, 현재가를 같이 보면서 “언제 샀어야 했나”와 목표가 여력을 확인합니다.</p>
      </div>
      <div class="toolbar">
        <input id="opportunitySearch" placeholder="종목 검색">
        <select id="opportunityTargetFilter"><option value="">전체 목표 상태</option><option value="hit">목표 도달</option><option value="miss">목표 미도달</option></select>
      </div>
      <div class="dashboard-grid two">
        <article class="panel"><h3>저가 매수 기회</h3><div id="opportunityPlot" class="plotly-panel"></div></article>
        <article class="panel"><h3>월별 코호트 지도</h3><div id="frontierPlot" class="plotly-panel"></div></article>
      </div>
      <div class="table-wrap"><table id="priceOpportunityTable"></table></div>
    </section>

    <section id="legacy-portfolio" class="section-band">
      <div class="section-head">
        <div>
          <p class="eyebrow">Legacy cohort view</p>
          <h2>코호트 포트폴리오 참고표</h2>
        </div>
        <p>v3 엔진의 주 화면은 위 전략 대시보드입니다. 이 표는 이전 cohort 방식 결과를 참고용으로 남긴 것입니다.</p>
      </div>
      <div id="overviewStats" class="metric-grid"></div>
      <div id="bestPortfolio" class="panel"></div>
      <div class="toolbar">
        <select id="portfolioCohort"></select>
        <select id="portfolioRf"></select>
        <select id="portfolioStrategy"></select>
      </div>
      <div id="portfolioBarPlot" class="plotly-panel panel"></div>
      <div class="table-wrap"><table id="topPortfolioTable"></table></div>
      <div class="table-wrap"><table id="portfolioTable"></table></div>
    </section>

    <section id="reports" class="section-band">
      <div class="section-head">
        <div>
          <p class="eyebrow">Reports</p>
          <h2>리포트 아카이브</h2>
        </div>
        <p>PDF와 Markdown 원문을 함께 보관합니다. 한국·일본 종목은 숫자 티커보다 회사명을 우선 표시합니다.</p>
      </div>
      <div class="toolbar">
        <input id="reportSearch" placeholder="종목, 리포트명 검색">
        <input id="metricsSearch" placeholder="가격 지표 검색">
        <select id="targetFilter"><option value="">전체</option><option value="hit">목표 도달</option><option value="miss">목표 미도달</option></select>
      </div>
      <div id="reportStats" class="metric-grid"></div>
      <div class="table-wrap"><table id="reportsTable"></table></div>
      <div class="table-wrap"><table id="metricsTable"></table></div>
    </section>

    <section id="signals" class="section-band">
      <div class="section-head">
        <div>
          <p class="eyebrow">Signals</p>
          <h2>MTT / RS 신호 탐색</h2>
        </div>
        <p>전략이 편입 판단에 사용한 추세와 상대강도 신호입니다. 신호는 해당 날짜 이전 데이터만 사용합니다.</p>
      </div>
      <div class="toolbar">
        <select id="signalRunSelect"></select>
        <input id="signalSearch" placeholder="종목, 날짜 검색">
      </div>
      <div id="signalScatterPlot" class="plotly-panel panel"></div>
      <div class="table-wrap"><table id="signalTable"></table></div>
    </section>
  </main>
  <script>
{script}
  </script>
</body>
</html>
"""


def build_site(data_dir: Path, public_dir: Path) -> None:
    resolved_public = public_dir.resolve()
    resolved_cwd = Path.cwd().resolve()
    if resolved_public == resolved_cwd or resolved_public == Path(resolved_public.anchor):
        raise ValueError(f"Refusing to clear unsafe public directory: {public_dir}")
    if public_dir.exists():
        shutil.rmtree(public_dir)
    public_dir.mkdir(parents=True, exist_ok=True)
    reports = build_reports_json(data_dir, public_dir)
    write_json(public_dir / "data" / "price_metrics.json", read_json(data_dir / "price_metrics.json"))
    write_json(public_dir / "data" / "portfolio_backtests.json", read_json(data_dir / "portfolio_backtests.json"))
    for name in [
        "strategy_runs.json",
        "equity_daily.json",
        "pool_timeline.json",
        "candidate_pool_events.json",
        "current_positions.json",
        "recent_trades.json",
        "signals_daily.json",
        "strategy_heatmap.json",
        "optuna_trials.json",
    ]:
        write_json(public_dir / "data" / "quant_v3" / name, read_json(data_dir / "quant_v3" / name))
    (public_dir / "index.html").write_text(render_index_html(), encoding="utf-8")
    write_json(public_dir / "data" / "site_summary.json", {"reports": len(reports)})
