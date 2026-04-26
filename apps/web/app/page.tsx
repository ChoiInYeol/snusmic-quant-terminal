'use client';

import { type ReactNode, Suspense, useEffect, useMemo, useState } from 'react';
import { useQueryState, parseAsString } from 'nuqs';
import { DrawdownChart, EquityChart, StockChart } from '../src/components/ChartCard';
import { BaselineBandSummary } from '../src/components/BaselineBandSummary';
import { StrategyScatter } from '../src/components/PlotlyPanel';
import { StaleDataBanner } from '../src/components/StaleDataBanner';
import { ThemeToggle } from '../src/components/ThemeToggle';
import { Metric, SectionIntro } from '../src/components/ui/Metric';
import {
  type Column,
  CsvButton,
  SortHeader,
  SortableDataTable,
  useSortedRows,
} from '../src/components/ui/SortableDataTable';
import {
  bestStrategy,
  fetchJson,
  loadDashboard,
  type ChartIndexRow,
  type DashboardData,
  type PriceMetric,
  type ReportRow,
  type StockChartData,
  type StrategyRun,
} from '../src/lib/data';
import { calculateBaselineBandStats } from '../src/lib/baseline';
import { labelEntryRule, labelReason, num, pct, shortDate } from '../src/lib/format';

// Phase 6c — Next.js static export requires every consumer of
// ``useSearchParams`` (which ``nuqs`` uses internally) to live below a
// ``<Suspense>`` boundary so the static page generator can pre-render the
// non-search-param shell. ``Page`` is a thin Suspense wrapper; the
// ``PageInner`` body holds all the dashboard state + URL hooks.
function PageInner() {
  const [data, setData] = useState<DashboardData | null>(null);
  // Phase 6c — round-trip selectedRunId / selectedSymbol / query through the
  // URL bar via nuqs. ``defaultValue: ''`` keeps the existing useState
  // semantics; ``clearOnDefault`` keeps the URL clean when the value is the
  // default (no ``?runId=`` when the run is the default selection).
  const [selectedRunId, setSelectedRunId] = useQueryState(
    'runId',
    parseAsString.withDefault('').withOptions({ clearOnDefault: true, history: 'replace' }),
  );
  const [selectedSymbol, setSelectedSymbol] = useQueryState(
    'symbol',
    parseAsString.withDefault('').withOptions({ clearOnDefault: true, history: 'replace' }),
  );
  const [chartData, setChartData] = useState<StockChartData | null>(null);
  const [query, setQuery] = useQueryState(
    'q',
    parseAsString.withDefault('').withOptions({ clearOnDefault: true, history: 'replace', throttleMs: 300 }),
  );
  const [error, setError] = useState('');

  useEffect(() => {
    loadDashboard()
      .then((loaded) => {
        setData(loaded);
        const best = bestStrategy(loaded.strategies);
        setSelectedRunId(best?.run_id ?? loaded.strategies[0]?.run_id ?? '');
        const firstPosition = loaded.positions.find((item) => item.run_id === best?.run_id) ?? loaded.positions[0];
        setSelectedSymbol(firstPosition?.symbol ?? loaded.chartIndex[0]?.symbol ?? '');
      })
      .catch((err: Error) => setError(err.message));
  }, []);

  const selectedStrategy = useMemo(
    () => data?.strategies.find((item) => item.run_id === selectedRunId) ?? null,
    [data, selectedRunId],
  );
  const strategies = data?.strategies ?? [];
  const positions = useMemo(
    () =>
      (data?.positions ?? [])
        .filter((item) => item.run_id === selectedRunId)
        .sort((a, b) => b.weight - a.weight),
    [data, selectedRunId],
  );
  const equityRows = useMemo(
    () => (data?.equity ?? []).filter((item) => item.run_id === selectedRunId).sort((a, b) => a.date.localeCompare(b.date)),
    [data, selectedRunId],
  );
  const trades = useMemo(
    () =>
      (data?.trades ?? [])
        .filter((item) => item.run_id === selectedRunId)
        .sort((a, b) => b.date.localeCompare(a.date)),
    [data, selectedRunId],
  );
  const filteredMetrics = useMemo(() => {
    const term = query.trim().toLowerCase();
    return (data?.priceMetrics ?? [])
      .filter((item) => !term || item.display_name.toLowerCase().includes(term) || item.yfinance_symbol.toLowerCase().includes(term))
      .sort((a, b) => b.publication_date.localeCompare(a.publication_date));
  }, [data, query]);
  const candidateEvents = useMemo(
    () =>
      (data?.candidateEvents ?? [])
        .filter((item) => item.run_id === selectedRunId)
        .sort((a, b) => b.date.localeCompare(a.date))
        .slice(0, 24),
    [data, selectedRunId],
  );
  const companyBySymbol = useMemo(
    () => new Map((data?.chartIndex ?? []).map((item) => [item.symbol, item.company])),
    [data],
  );
  const signalRows = useMemo(
    () => {
      const activeRows = (data?.signals ?? []).filter((item) => item.run_id === selectedRunId && item.candidate_universe_active);
      const latestDate = activeRows.reduce((latest, row) => (row.date > latest ? row.date : latest), '');
      return activeRows
        .filter((item) => item.date === latestDate)
        .sort((a, b) => Number(b.mtt_pass) - Number(a.mtt_pass) || (b.pct_above_52w_low ?? -1) - (a.pct_above_52w_low ?? -1))
        .slice(0, 30);
    },
    [data, selectedRunId],
  );
  const latestReports = useMemo(
    () => (data?.reports ?? []).sort((a, b) => (b.publication_date || '').localeCompare(a.publication_date || '')),
    [data],
  );
  const baselineBand = useMemo(
    () => calculateBaselineBandStats(data?.priceMetrics ?? [], selectedStrategy),
    [data?.priceMetrics, selectedStrategy],
  );

  useEffect(() => {
    if (!selectedSymbol || !data) return;
    const found = data.chartIndex.find((item) => item.symbol === selectedSymbol);
    if (!found) return;
    fetchJson<StockChartData>(`quant_v3/chart_series/${found.file}`)
      .then(setChartData)
      .catch((err: Error) => setError(err.message));
  }, [data, selectedSymbol]);

  if (error) {
    return (
      <main className="shell">
        <section className="error-panel">데이터를 불러오지 못했습니다: {error}</section>
      </main>
    );
  }

  if (!data || !selectedStrategy) {
    return (
      <main className="shell">
        <section className="loading-panel">SNUSMIC Quant Terminal을 불러오는 중입니다.</section>
      </main>
    );
  }

  const currentReturn = selectedStrategy.total_return;
  const liveReturn = positions.reduce((acc, item) => acc + (item.model_contribution ?? 0), 0);
  const cashWeight = Math.max(0, 1 - positions.reduce((acc, item) => acc + item.weight, 0));

  return (
    <main className="shell">
      <header className="topbar">
        <a className="brand" href="#decision" aria-label="SNUSMIC Quant Terminal 홈">
          <span>SNUSMIC</span>
          <strong>퀀트 리서치 노트</strong>
        </a>
        <nav aria-label="페이지 섹션">
          <a href="#decision">오늘의 판단</a>
          <a href="#positions">현재 보유</a>
          <a href="#performance">성과/낙폭</a>
          <a href="#stock">종목 차트</a>
          <a href="#ledger">원장/신호</a>
          <a href="#opportunity">가격 기회</a>
          <a href="#reports">리포트</a>
        </nav>
        <ThemeToggle />
      </header>

      <StaleDataBanner equity={data.equity} />

      <section className="content">
        <header className="hero" id="decision">
          <div>
            <p className="eyebrow">전략 운용판</p>
            <h1>지금 어떤 전략으로 무엇을 얼마나 들고 있는가</h1>
            <p className="lede">
              리포트 발간 이후 후보군을 누적하고, MTT와 목표가 여력 조건으로 실제 보유 종목을 결정한다.
              본 화면은 현재 포지션, 성과, 매매 근거를 동일한 기준으로 요약한다.
            </p>
          </div>
          <div className="hero-card">
            <span>선택 전략</span>
            <strong>{selectedStrategy.strategy_name}</strong>
            <select value={selectedRunId} onChange={(event) => setSelectedRunId(event.target.value)} aria-label="전략 선택">
              {strategies.map((strategy) => (
                <option key={strategy.run_id} value={strategy.run_id}>
                  {strategy.strategy_name}
                </option>
              ))}
            </select>
          </div>
        </header>

        <section className="metric-grid" aria-label="선택 전략 핵심 지표">
          <Metric title="총 수익" value={pct(currentReturn)} tone={currentReturn >= 0 ? 'gain' : 'loss'} />
          <Metric title="미실현 기여" value={pct(liveReturn)} tone={liveReturn >= 0 ? 'gain' : 'loss'} />
          <Metric title="최대낙폭" value={pct(selectedStrategy.max_drawdown)} tone="loss" />
          <Metric title="현금 비중" value={pct(cashWeight)} />
          <Metric title="보유 종목" value={`${positions.length}개`} />
          <Metric title="매매 이벤트" value={`${selectedStrategy.turnover_events.toLocaleString('ko-KR')}회`} />
        </section>

        <BaselineBandSummary stats={baselineBand} strategyName={selectedStrategy.strategy_name} />

        <section className="section-block">
          <SectionIntro
            eyebrow="Strategy guide"
            title="전략을 먼저 읽고, 숫자를 봅니다"
            body="전략은 후보군 편입 조건, 보유 비중 산정 방식, 리밸런싱 주기로 정의된다. 아래 지표는 동일 기간의 산술 수익률 기준으로 산출한다."
          />
          <article className="panel strategy-guide">
          <div>
            <p className="eyebrow">전략 설명</p>
            <h2>{selectedStrategy.strategy_name}</h2>
            <p>
              이 전략은 <b>{labelEntryRule(selectedStrategy.entry_rule)}</b> 조건으로 편입 후보를 고르고, 실제 보유군 내부에서
              <b> {selectedStrategy.weighting}</b> 방식으로 비중을 조절합니다. 리밸런싱은 <b>{selectedStrategy.rebalance}</b>,
              lookback은 <b>{selectedStrategy.lookback_days} 거래일</b>입니다.
            </p>
          </div>
          <div className="guide-stats">
            <span>Sharpe {selectedStrategy.sharpe?.toFixed(2) ?? '-'}</span>
            <span>Sortino {selectedStrategy.sortino?.toFixed(2) ?? '-'}</span>
            <span>Calmar {selectedStrategy.calmar?.toFixed(2) ?? '-'}</span>
            <span>승률 {pct(selectedStrategy.win_rate)}</span>
          </div>
          </article>
        </section>

        <section className="section-block" id="positions">
          <SectionIntro
            eyebrow="Current book"
            title="지금 들고 있는 것"
            body="현재 보유 종목, 비중, 미실현 수익률, 최근 매매 사유를 한 영역에서 표시한다."
          />
          <div className="split">
          <article className="panel">
            <div className="panel-head">
              <div>
                <p className="eyebrow">현재 운용</p>
                <h2>현재 보유</h2>
              </div>
              <span>{positions[0]?.date ?? '-'}</span>
            </div>
            <PortfolioHeatmap positions={positions} selectedSymbol={selectedSymbol} onSelect={setSelectedSymbol} />
            <PositionList positions={positions} selectedSymbol={selectedSymbol} onSelect={setSelectedSymbol} />
          </article>
          <article className="panel">
            <div className="panel-head">
              <div>
                <p className="eyebrow">매매 기록</p>
                <h2>최근 매매</h2>
              </div>
            </div>
            <TradeTable trades={trades.slice(0, 20)} />
          </article>
          </div>
        </section>

        <section className="section-block" id="performance">
          <SectionIntro
            eyebrow="Performance"
            title="성과와 낙폭은 분리해서 읽습니다"
            body="누적 자산은 우상향 여부를, 낙폭은 버틸 수 있는 전략인지 판단하게 해줍니다. 두 차트를 분리해 과도한 겹침을 피했습니다."
          />
          <div className="split">
          <article className="panel">
            <div className="panel-head">
              <h2>누적 자산</h2>
              <span>시계열</span>
            </div>
            <EquityChart rows={equityRows} />
          </article>
          <article className="panel">
            <div className="panel-head">
              <h2>낙폭</h2>
              <span>peak 대비</span>
            </div>
            <DrawdownChart rows={equityRows} />
          </article>
          </div>
        </section>

        <section className="section-block">
          <SectionIntro
            eyebrow="Strategy map"
            title="전략 간 비교"
            body="점 하나는 하나의 전략 실행 결과입니다. 수익률과 변동성을 같이 보고, 같은 위험에서 더 높은 수익을 낸 효율적 경계를 확인합니다."
          />
          <div className="split">
          <article className="panel wide">
            <div className="panel-head">
              <h2>전략 지도</h2>
              <span>수익률 vs 변동성</span>
            </div>
            <StrategyScatter strategies={strategies} selectedRunId={selectedRunId} />
          </article>
          <article className="panel">
            <div className="panel-head">
              <h2>전략 순위</h2>
              <span>상위 8개</span>
            </div>
            <StrategyRanking strategies={strategies} selectedRunId={selectedRunId} onSelect={setSelectedRunId} />
          </article>
          </div>
        </section>

        <section className="section-block" id="stock">
          <SectionIntro
            eyebrow="Chart"
            title="종목 차트는 최근 구간부터 봅니다"
            body="최근 가격 구간을 우선 표시한다. 이동평균선, 발간가, 목표가, 매수·매도 표식을 함께 확인한다."
          />
          <article className="panel">
          <div className="panel-head">
            <div>
              <p className="eyebrow">종목 차트</p>
              <h2>{chartData?.meta.company ?? selectedSymbol}</h2>
            </div>
            <SymbolSelect index={data.chartIndex} value={selectedSymbol} onChange={setSelectedSymbol} />
          </div>
          <StockChart data={chartData} runId={selectedRunId} />
          </article>
        </section>

        <section className="section-block" id="ledger">
          <SectionIntro
            eyebrow="Ledger"
            title="후보군과 신호는 근거 자료입니다"
            body="후보군 편입·제외와 최신 MTT 상태를 확인한다. 모든 원장성 데이터는 최신순으로 정렬한다."
          />
          <article className="panel">
            <div className="panel-head">
              <div>
                <p className="eyebrow">현재 후보군</p>
                <h2>후보군 지도</h2>
              </div>
              <span>MTT 상태 · 가격 위치</span>
            </div>
            <CandidateHeatmap rows={signalRows} companyBySymbol={companyBySymbol} />
          </article>
          <div className="split">
          <article className="panel">
            <div className="panel-head">
              <div>
                <p className="eyebrow">후보군 원장</p>
                <h2>후보군 최근 변화</h2>
              </div>
              <span>최신순</span>
            </div>
            <CandidateEventTable rows={candidateEvents} />
          </article>
          <article className="panel">
            <div className="panel-head">
              <div>
                <p className="eyebrow">추세 신호</p>
                <h2>MTT 점검</h2>
              </div>
              <span>최신순</span>
            </div>
            <SignalTable rows={signalRows} companyBySymbol={companyBySymbol} />
          </article>
          </div>
        </section>

        <section className="section-block" id="opportunity">
          <SectionIntro
            eyebrow="Opportunity"
            title="추종자와 예언자 사이의 전략 공간"
            body="스믹 추종자는 발간가에 사서 목표가에 파는 단순 기준선이고, 예언자는 사후 최저가와 이후 최고가를 아는 상한선입니다. 현실 전략은 이 둘 사이를 좁히는 것이 목표입니다."
          />
          <article className="panel">
          <div className="panel-head">
            <div>
              <p className="eyebrow">Baseline band</p>
              <h2>스믹 추종자 ↔ 예언자</h2>
            </div>
            <input value={query} onChange={(event) => setQuery(event.target.value)} placeholder="회사명 검색" />
          </div>
          <OpportunityTable rows={filteredMetrics} />
          </article>
        </section>

        <section className="section-block" id="reports">
          <SectionIntro
            eyebrow="Archive"
            title="원문으로 다시 검증하기"
            body="정량 결과의 근거가 되는 PDF와 OCR Markdown 링크를 제공한다. 추출값 검증은 원문 기준으로 수행한다."
          />
          <article className="panel">
          <div className="panel-head">
            <div>
              <p className="eyebrow">리포트 아카이브</p>
              <h2>리포트 원문</h2>
            </div>
            <span>PDF / Markdown 링크 복구</span>
          </div>
          <ReportArchiveTable rows={latestReports} />
          </article>
        </section>
      </section>
    </main>
  );
}

export default function Page() {
  // Suspense fallback uses the same loading copy the original
  // pre-fetch branch renders so the static export bridges to the
  // hydrated client component without a visible flash.
  return (
    <Suspense
      fallback={
        <main className="shell">
          <section className="loading-panel">SNUSMIC Quant Terminal을 불러오는 중입니다.</section>
        </main>
      }
    >
      <PageInner />
    </Suspense>
  );
}

// (Phase 6b) Metric / SectionIntro / SortableDataTable + helpers extracted to
// apps/web/src/components/ui/{Metric,SortableDataTable}.tsx


function heatColor(value: number | null | undefined, positiveMax = 0.35) {
  if (value === null || value === undefined || Number.isNaN(value)) return 'rgba(148, 163, 184, 0.18)';
  const clamped = Math.max(-positiveMax, Math.min(positiveMax, value));
  const alpha = 0.18 + Math.min(0.62, Math.abs(clamped) / positiveMax * 0.62);
  return clamped >= 0 ? `rgba(4, 120, 87, ${alpha})` : `rgba(180, 35, 24, ${alpha})`;
}

function PortfolioHeatmap({
  positions,
  selectedSymbol,
  onSelect,
}: {
  positions: DashboardData['positions'];
  selectedSymbol: string;
  onSelect: (symbol: string) => void;
}) {
  if (!positions.length) return null;
  return (
    <div className="heatmap portfolio-map" aria-label="현재 포트폴리오 히트맵">
      {positions.map((position) => {
        const width = `${Math.max(18, Math.min(62, position.weight * 100 * 2.2))}%`;
        return (
          <button
            key={`map-${position.run_id}-${position.symbol}`}
            className={position.symbol === selectedSymbol ? 'heat-tile active' : 'heat-tile'}
            style={{ flexBasis: width, flexGrow: Math.max(1, position.weight * 100), background: heatColor(position.gross_return) }}
            onClick={() => onSelect(position.symbol)}
            type="button"
          >
            <strong>{position.company || position.symbol}</strong>
            <span>{pct(position.weight)} · {pct(position.gross_return)}</span>
            <small>{position.mtt_pass ? 'MTT 통과' : 'MTT 미통과'} · 현재가 {num(position.close, 'KRW')}</small>
          </button>
        );
      })}
    </div>
  );
}

function CandidateHeatmap({ rows, companyBySymbol }: { rows: DashboardData['signals']; companyBySymbol: Map<string, string> }) {
  if (!rows.length) return <p className="empty">현재 후보군 신호가 없습니다.</p>;
  return (
    <div className="heatmap candidate-map" aria-label="현재 후보군 히트맵">
      {rows.map((row) => {
        const distance = row.pct_above_52w_low ?? 0;
        const opacity = 0.16 + Math.min(0.68, Math.max(0, distance) / 1.5 * 0.68);
        return (
          <div
            key={`candidate-${row.run_id}-${row.symbol}`}
            className={row.mtt_pass ? 'heat-tile candidate-pass' : 'heat-tile'}
            style={{ background: row.mtt_pass ? `rgba(4, 120, 87, ${opacity})` : `rgba(31, 79, 143, ${opacity})` }}
          >
            <strong>{companyBySymbol.get(row.symbol) ?? row.symbol}</strong>
            <span>{row.mtt_pass ? 'MTT' : '대기'}</span>
            <small>{row.mtt_pass ? 'MTT 통과' : 'MTT 대기'} · 현재가 {num(row.close, 'KRW')}</small>
          </div>
        );
      })}
    </div>
  );
}

function PositionList({
  positions,
  selectedSymbol,
  onSelect,
}: {
  positions: DashboardData['positions'];
  selectedSymbol: string;
  onSelect: (symbol: string) => void;
}) {
  if (!positions.length) return <p className="empty">현재 보유 종목이 없습니다.</p>;
  return (
    <div className="position-list">
      {positions.map((position) => (
        <button
          key={`${position.run_id}-${position.symbol}`}
          className={position.symbol === selectedSymbol ? 'position-row active' : 'position-row'}
          onClick={() => onSelect(position.symbol)}
        >
          <span>
            <strong>{position.company || position.symbol}</strong>
            <small>
              {position.mtt_pass ? 'MTT 통과' : 'MTT 미통과'} · 현재가 {num(position.close, 'KRW')}
            </small>
          </span>
          <span className="right">
            <b>{pct(position.weight)}</b>
            <small className={(position.gross_return ?? 0) >= 0 ? 'gain-text' : 'loss-text'}>{pct(position.gross_return)}</small>
          </span>
        </button>
      ))}
    </div>
  );
}

function TradeTable({ trades }: { trades: DashboardData['trades'] }) {
  const columns: Column<DashboardData['trades'][number]>[] = [
    { key: 'date', label: '날짜', value: (row) => row.date, render: (row) => shortDate(row.date) },
    { key: 'company', label: '종목', value: (row) => row.company || row.symbol, render: (row) => row.company || row.symbol },
    { key: 'reason', label: '구분', value: (row) => labelReason(row.reason), render: (row) => labelReason(row.reason) },
    { key: 'price', label: '가격', value: (row) => row.price, render: (row) => num(row.price, 'KRW') },
    {
      key: 'gross_return',
      label: '수익',
      value: (row) => row.gross_return,
      render: (row) => pct(row.gross_return),
      className: (row) => ((row.gross_return ?? 0) >= 0 ? 'gain-text' : 'loss-text'),
    },
  ];
  return <SortableDataTable rows={trades} columns={columns} filename="recent-trades.csv" initialSort="date" empty="최근 매매가 없습니다." />;
}

function CandidateEventTable({ rows }: { rows: DashboardData['candidateEvents'] }) {
  const columns: Column<DashboardData['candidateEvents'][number]>[] = [
    { key: 'date', label: '날짜', value: (row) => row.date, render: (row) => shortDate(row.date) },
    { key: 'company', label: '종목', value: (row) => row.company || row.symbol, render: (row) => row.company || row.symbol },
    { key: 'event', label: '이벤트', value: (row) => labelReason(row.reason || row.event_type), render: (row) => labelReason(row.reason || row.event_type) },
    { key: 'close', label: '가격', value: (row) => row.close, render: (row) => num(row.close, 'KRW') },
    { key: 'target', label: '목표가', value: (row) => row.target_price, render: (row) => num(row.target_price, 'KRW') },
    { key: 'count', label: '후보 수', value: (row) => row.candidate_count_after, render: (row) => row.candidate_count_after ?? '-' },
  ];
  return <SortableDataTable rows={rows} columns={columns} filename="candidate-events.csv" initialSort="date" empty="후보군 이벤트가 없습니다." />;
}

function SignalTable({ rows, companyBySymbol }: { rows: DashboardData['signals']; companyBySymbol: Map<string, string> }) {
  const columns: Column<DashboardData['signals'][number]>[] = [
    { key: 'date', label: '날짜', value: (row) => row.date, render: (row) => shortDate(row.date) },
    { key: 'company', label: '종목', value: (row) => companyBySymbol.get(row.symbol) ?? row.symbol, render: (row) => companyBySymbol.get(row.symbol) ?? row.symbol },
    {
      key: 'mtt',
      label: 'MTT',
      value: (row) => Number(row.mtt_pass),
      render: (row) => (row.mtt_pass ? '통과' : '미통과'),
      className: (row) => (row.mtt_pass ? 'gain-text' : 'loss-text'),
    },
    { key: 'close', label: '현재가', value: (row) => row.close, render: (row) => num(row.close, 'KRW') },
    { key: 'ma50', label: '50MA', value: (row) => row.ma50, render: (row) => num(row.ma50, 'KRW') },
    { key: 'ma150', label: '150MA', value: (row) => row.ma150, render: (row) => num(row.ma150, 'KRW') },
    { key: 'ma200', label: '200MA', value: (row) => row.ma200, render: (row) => num(row.ma200, 'KRW') },
    { key: 'low52', label: '52주 저점 대비', value: (row) => row.pct_above_52w_low, render: (row) => pct(row.pct_above_52w_low) },
  ];
  return <SortableDataTable rows={rows} columns={columns} filename="signals.csv" initialSort="mtt" empty="신호 데이터가 없습니다." />;
}

function StrategyRanking({
  strategies,
  selectedRunId,
  onSelect,
}: {
  strategies: StrategyRun[];
  selectedRunId: string;
  onSelect: (runId: string) => void;
}) {
  return (
    <div className="ranking">
      {[...strategies]
        .sort((a, b) => b.total_return - a.total_return)
        .slice(0, 8)
        .map((strategy, index) => (
          <button key={strategy.run_id} className={strategy.run_id === selectedRunId ? 'rank active' : 'rank'} onClick={() => onSelect(strategy.run_id)}>
            <span>{index + 1}</span>
            <strong>{strategy.strategy_name}</strong>
            <b>{pct(strategy.total_return)}</b>
          </button>
        ))}
    </div>
  );
}

function SymbolSelect({ index, value, onChange }: { index: ChartIndexRow[]; value: string; onChange: (symbol: string) => void }) {
  return (
    <select value={value} onChange={(event) => onChange(event.target.value)} aria-label="종목 선택">
      {index
        .sort((a, b) => a.company.localeCompare(b.company, 'ko'))
        .map((item) => (
          <option key={item.symbol} value={item.symbol}>
            {displaySymbolOption(item)}
          </option>
        ))}
    </select>
  );
}

function displaySymbolOption(item: ChartIndexRow): string {
  if (/\.(KS|KQ|T)$/.test(item.symbol)) return item.company;
  return `${item.company} · ${item.symbol}`;
}

function OpportunityTable({ rows }: { rows: PriceMetric[] }) {
  const columns: Column<PriceMetric>[] = [
    { key: 'publication_date', label: '일자', value: (row) => row.publication_date, render: (row) => shortDate(row.publication_date) },
    { key: 'company', label: '회사', value: (row) => row.display_name || row.company, render: (row) => row.display_name || row.company },
    { key: 'publication_buy_price', label: '발간가', value: (row) => row.publication_buy_price, render: (row) => num(row.publication_buy_price, 'KRW') },
    {
      key: 'smic_follower_return',
      label: '스믹 추종자',
      value: (row) => row.smic_follower_return,
      render: (row) => pct(row.smic_follower_return),
      className: (row) => ((row.smic_follower_return ?? 0) >= 0 ? 'gain-text' : 'loss-text'),
    },
    {
      key: 'oracle_return',
      label: '예언자 상한',
      value: (row) => row.oracle_return,
      render: (row) => pct(row.oracle_return),
      className: (row) => ((row.oracle_return ?? 0) >= 0 ? 'gain-text' : 'loss-text'),
    },
    { key: 'oracle_entry_price', label: '예언자 매수가', value: (row) => row.oracle_entry_price, render: (row) => num(row.oracle_entry_price, 'KRW') },
    { key: 'oracle_exit_price', label: '예언자 매도가', value: (row) => row.oracle_exit_price, render: (row) => num(row.oracle_exit_price, 'KRW') },
    { key: 'oracle_buy_lag_days', label: '진입대기', value: (row) => row.oracle_buy_lag_days, render: (row) => dayCell(row.oracle_buy_lag_days) },
    { key: 'oracle_holding_days', label: '상한보유', value: (row) => row.oracle_holding_days, render: (row) => dayCell(row.oracle_holding_days) },
    { key: 'smic_follower_status', label: '추종상태', value: (row) => row.smic_follower_status, render: (row) => followerStatus(row) },
    { key: 'target_upside', label: '남은여력', value: (row) => row.target_upside_remaining, render: (row) => targetUpsideCell(row) },
  ];
  return <SortableDataTable rows={rows} columns={columns} filename="price-opportunity.csv" initialSort="publication_date" empty="가격 기회 데이터가 없습니다." />;
}


function dayCell(value: number | null | undefined): string {
  if (value === null || value === undefined || Number.isNaN(value)) return '-';
  return `${value.toLocaleString('ko-KR')}일`;
}

function followerStatus(row: PriceMetric): string {
  if (row.smic_follower_status === 'target_hit') return `목표 도달 · ${dayCell(row.smic_follower_holding_days)}`;
  if (row.smic_follower_status === 'open') return `미도달 · ${dayCell(row.smic_follower_holding_days)}`;
  return '-';
}

function ReportArchiveTable({ rows }: { rows: ReportRow[] }) {
  const columns: Column<ReportRow>[] = [
    { key: 'publication_date', label: '발간일', value: (row) => row.publication_date, render: (row) => shortDate(row.publication_date) },
    { key: 'company', label: '회사', value: (row) => row.company, render: (row) => row.company },
    { key: 'symbol', label: '심볼', value: (row) => row.symbol, render: (row) => (/\.(KS|KQ|T)$/.test(row.symbol) ? row.company : row.symbol) },
    { key: 'report_price', label: '발간가', value: (row) => row.report_current_price_krw, render: (row) => num(row.report_current_price_krw, 'KRW') },
    { key: 'bear', label: 'Bear', value: (row) => row.bear_target_krw, render: (row) => targetPriceCell(row.bear_target_krw, row.report_current_price_krw) },
    { key: 'base', label: 'Base', value: (row) => row.base_target_krw, render: (row) => targetPriceCell(row.base_target_krw, row.report_current_price_krw) },
    { key: 'bull', label: 'Bull', value: (row) => row.bull_target_krw, render: (row) => targetPriceCell(row.bull_target_krw, row.report_current_price_krw) },
    {
      key: 'source',
      label: '원문',
      value: (row) => row.pdf_filename,
      render: (row) => (
        <span className="link-cell">
          {row.pdf_filename ? (
            <a href={githubBlobUrl(`data/pdfs/${row.pdf_filename}`)} target="_blank" rel="noreferrer">
              PDF
            </a>
          ) : null}
          {row.markdown_filename ? (
            <a href={githubBlobUrl(`data/markdown/${row.markdown_filename}`)} target="_blank" rel="noreferrer">
              MD
            </a>
          ) : null}
        </span>
      ),
    },
  ];
  return <SortableDataTable rows={rows} columns={columns} filename="report-archive.csv" initialSort="publication_date" empty="리포트 원문 데이터가 없습니다." />;
}

function githubBlobUrl(path: string) {
  return `https://github.com/ChoiInYeol/snusmic-quant-terminal/blob/main/${path
    .split('/')
    .map((part) => encodeURIComponent(part))
    .join('/')}`;
}

function targetPriceCell(value: number | null, reference: number | null) {
  if (value && reference && value / reference > 20) return '검토';
  return num(value, 'KRW');
}

function targetUpsideCell(row: PriceMetric) {
  if ((row.target_upside_remaining ?? 0) > 20) return '검토';
  return pct(row.target_upside_remaining);
}
