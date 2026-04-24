'use client';

import { type ReactNode, useEffect, useMemo, useState } from 'react';
import { DrawdownChart, EquityChart, StockChart } from '../src/components/ChartCard';
import { StrategyScatter } from '../src/components/PlotlyPanel';
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
import { labelEntryRule, labelReason, num, pct, shortDate } from '../src/lib/format';

export default function Page() {
  const [data, setData] = useState<DashboardData | null>(null);
  const [selectedRunId, setSelectedRunId] = useState('');
  const [selectedSymbol, setSelectedSymbol] = useState('');
  const [chartData, setChartData] = useState<StockChartData | null>(null);
  const [query, setQuery] = useState('');
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
      .sort((a, b) => b.publication_date.localeCompare(a.publication_date))
      .slice(0, 30);
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
        .sort((a, b) => (b.rs_score ?? -1) - (a.rs_score ?? -1))
        .slice(0, 30);
    },
    [data, selectedRunId],
  );
  const latestReports = useMemo(
    () =>
      (data?.reports ?? [])
        .sort((a, b) => (b.publication_date || '').localeCompare(a.publication_date || ''))
        .slice(0, 80),
    [data],
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
      </header>

      <section className="content">
        <header className="hero" id="decision">
          <div>
            <p className="eyebrow">전략 운용판</p>
            <h1>지금 어떤 전략으로 무엇을 얼마나 들고 있는가</h1>
            <p className="lede">
              Candidate pool에서 MTT, RS, 목표가 여력, 손절/익절 조건을 통과한 종목만 execution pool로 들어옵니다.
              이 화면은 과거 로그보다 오늘의 포지션과 그 이유를 먼저 보여줍니다.
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

        <section className="section-block">
          <SectionIntro
            eyebrow="Strategy guide"
            title="전략을 먼저 읽고, 숫자를 봅니다"
            body="이 페이지는 백테스트 리포트라기보다 운용 메모에 가깝습니다. 위쪽은 현재 의사결정, 아래쪽은 그 판단을 만든 가격·신호·원장 데이터입니다."
          />
          <article className="panel strategy-guide">
          <div>
            <p className="eyebrow">전략 설명</p>
            <h2>{selectedStrategy.strategy_name}</h2>
            <p>
              이 전략은 <b>{labelEntryRule(selectedStrategy.entry_rule)}</b> 조건으로 편입 후보를 고르고, execution pool 내부에서
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
            body="사용자 입장에서는 과거 후보군보다 현재 포지션이 우선입니다. 보유 비중, 미실현 수익, 최근 매매 사유를 같은 문맥에서 보이도록 배치했습니다."
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
            body="Lightweight Charts는 최근 가격 행동을 먼저 확대합니다. 이동평균선, 리포트 발간, 매수·매도 marker를 같은 화면에서 확인합니다."
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
            body="여기부터는 왜 후보가 들어오고 나갔는지, 최신 신호 상위 종목은 무엇인지 확인하는 감사 추적 영역입니다."
          />
          <article className="panel">
            <div className="panel-head">
              <div>
                <p className="eyebrow">현재 후보군</p>
                <h2>후보군 지도</h2>
              </div>
              <span>RS 색상 · MTT 테두리</span>
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
                <p className="eyebrow">추세/상대강도</p>
                <h2>신호 상위 종목</h2>
              </div>
              <span>RS 순</span>
            </div>
            <SignalTable rows={signalRows} companyBySymbol={companyBySymbol} />
          </article>
          </div>
        </section>

        <section className="section-block" id="opportunity">
          <SectionIntro
            eyebrow="Opportunity"
            title="리포트 이후의 가격 기회"
            body="발간가, 저가, 분위수 가격을 함께 보면서 리포트가 실제 매수 기회를 줬는지 확인합니다."
          />
          <article className="panel">
          <div className="panel-head">
            <div>
              <p className="eyebrow">가격 기회</p>
              <h2>리포트별 가격 기회</h2>
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
            body="정량 결과가 이상하면 PDF와 OCR Markdown으로 되돌아가 추출 품질과 투자 논리를 직접 확인합니다."
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

function Metric({ title, value, tone = '' }: { title: string; value: string; tone?: string }) {
  return (
    <article className={`metric ${tone}`}>
      <span>{title}</span>
      <strong>{value}</strong>
    </article>
  );
}

function SectionIntro({ eyebrow, title, body }: { eyebrow: string; title: string; body: string }) {
  return (
    <div className="section-intro">
      <p className="eyebrow">{eyebrow}</p>
      <h2>{title}</h2>
      <p>{body}</p>
    </div>
  );
}

type SortState = { key: string; direction: 'asc' | 'desc' };
type Column<T> = {
  key: string;
  label: string;
  value: (row: T) => unknown;
  render?: (row: T) => ReactNode;
  className?: (row: T) => string;
};

function compareValues(a: unknown, b: unknown): number {
  if (a === null || a === undefined || a === '') return 1;
  if (b === null || b === undefined || b === '') return -1;
  if (typeof a === 'number' && typeof b === 'number') return a - b;
  return String(a).localeCompare(String(b), 'ko', { numeric: true });
}

function useSortedRows<T>(rows: T[], columns: Column<T>[], initialKey: string, initialDirection: 'asc' | 'desc' = 'desc') {
  const [sort, setSort] = useState<SortState>({ key: initialKey, direction: initialDirection });
  const sortedRows = useMemo(() => {
    const column = columns.find((item) => item.key === sort.key) ?? columns[0];
    return [...rows].sort((a, b) => {
      const result = compareValues(column.value(a), column.value(b));
      return sort.direction === 'asc' ? result : -result;
    });
  }, [columns, rows, sort]);
  const toggleSort = (key: string) => {
    setSort((current) => ({
      key,
      direction: current.key === key && current.direction === 'desc' ? 'asc' : 'desc',
    }));
  };
  return { sortedRows, sort, toggleSort };
}

function SortHeader<T>({ column, sort, onSort }: { column: Column<T>; sort: SortState; onSort: (key: string) => void }) {
  const marker = sort.key === column.key ? (sort.direction === 'asc' ? '▲' : '▼') : '';
  return (
    <button className="sort-button" onClick={() => onSort(column.key)} type="button">
      {column.label} <span>{marker}</span>
    </button>
  );
}

function csvValue(value: unknown): string {
  if (value === null || value === undefined) return '';
  const text = String(value).replace(/\r?\n/g, ' ');
  return /[",]/.test(text) ? `"${text.replace(/"/g, '""')}"` : text;
}

function downloadCsv<T>(filename: string, rows: T[], columns: Column<T>[]) {
  const header = columns.map((column) => csvValue(column.label)).join(',');
  const body = rows.map((row) => columns.map((column) => csvValue(column.value(row))).join(',')).join('\n');
  const blob = new Blob([`\ufeff${header}\n${body}\n`], { type: 'text/csv;charset=utf-8;' });
  const url = URL.createObjectURL(blob);
  const link = document.createElement('a');
  link.href = url;
  link.download = filename;
  link.click();
  URL.revokeObjectURL(url);
}

function CsvButton<T>({ filename, rows, columns }: { filename: string; rows: T[]; columns: Column<T>[] }) {
  return (
    <button className="csv-button" onClick={() => downloadCsv(filename, rows, columns)} type="button">
      CSV
    </button>
  );
}

function SortableDataTable<T>({
  rows,
  columns,
  filename,
  initialSort,
  initialDirection = 'desc',
  empty,
}: {
  rows: T[];
  columns: Column<T>[];
  filename: string;
  initialSort: string;
  initialDirection?: 'asc' | 'desc';
  empty: string;
}) {
  const { sortedRows, sort, toggleSort } = useSortedRows(rows, columns, initialSort, initialDirection);
  if (!rows.length) return <p className="empty">{empty}</p>;
  return (
    <div className="table-card">
      <div className="table-toolbar">
        <span>{rows.length.toLocaleString('ko-KR')}개 행</span>
        <CsvButton filename={filename} rows={sortedRows} columns={columns} />
      </div>
      <div className="table-wrap wide-table">
        <table>
          <thead>
            <tr>
              {columns.map((column) => (
                <th key={column.key}>
                  <SortHeader column={column} sort={sort} onSort={toggleSort} />
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {sortedRows.map((row, rowIndex) => (
              <tr key={rowIndex}>
                {columns.map((column) => (
                  <td key={column.key} className={column.className?.(row)}>
                    {column.render ? column.render(row) : String(column.value(row) ?? '-')}
                  </td>
                ))}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}

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
            <small>RS {position.rs_score?.toFixed(0) ?? '-'} · {position.mtt_pass ? 'MTT 통과' : 'MTT 미통과'}</small>
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
        const rs = row.rs_score ?? 0;
        const opacity = 0.16 + Math.min(0.68, Math.max(0, rs - 50) / 50 * 0.68);
        return (
          <div
            key={`candidate-${row.run_id}-${row.symbol}`}
            className={row.mtt_pass ? 'heat-tile candidate-pass' : 'heat-tile'}
            style={{ background: `rgba(31, 79, 143, ${opacity})` }}
          >
            <strong>{companyBySymbol.get(row.symbol) ?? row.symbol}</strong>
            <span>RS {rs ? rs.toFixed(0) : '-'}</span>
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
              {position.mtt_pass ? 'MTT 통과' : 'MTT 미통과'} · RS {position.rs_score?.toFixed(0) ?? '-'}
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
    { key: 'rs', label: 'RS', value: (row) => row.rs_score, render: (row) => row.rs_score?.toFixed(0) ?? '-' },
    { key: 'close', label: '현재가', value: (row) => row.close, render: (row) => num(row.close, 'KRW') },
    { key: 'ma50', label: '50MA', value: (row) => row.ma50, render: (row) => num(row.ma50, 'KRW') },
    { key: 'ma150', label: '150MA', value: (row) => row.ma150, render: (row) => num(row.ma150, 'KRW') },
    { key: 'ma200', label: '200MA', value: (row) => row.ma200, render: (row) => num(row.ma200, 'KRW') },
    { key: 'low52', label: '52주 저점 대비', value: (row) => row.pct_above_52w_low, render: (row) => pct(row.pct_above_52w_low) },
  ];
  return <SortableDataTable rows={rows} columns={columns} filename="signals.csv" initialSort="rs" empty="신호 데이터가 없습니다." />;
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
    { key: 'publication_date', label: '발간일', value: (row) => row.publication_date, render: (row) => shortDate(row.publication_date) },
    { key: 'company', label: '회사', value: (row) => row.display_name || row.company, render: (row) => row.display_name || row.company },
    { key: 'current_price', label: '현재가', value: (row) => row.current_price, render: (row) => num(row.current_price, 'KRW') },
    { key: 'publication_buy_price', label: '발간가', value: (row) => row.publication_buy_price, render: (row) => num(row.publication_buy_price, 'KRW') },
    { key: 'lowest_price', label: '저가', value: (row) => row.lowest_price_since_publication, render: (row) => num(row.lowest_price_since_publication, 'KRW') },
    { key: 'q25_price', label: 'Q25', value: (row) => row.q25_price_since_publication, render: (row) => num(row.q25_price_since_publication, 'KRW') },
    { key: 'q75_price', label: 'Q75', value: (row) => row.q75_price_since_publication, render: (row) => num(row.q75_price_since_publication, 'KRW') },
    { key: 'q100_price', label: '고가(Q100)', value: (row) => row.highest_price_since_publication, render: (row) => num(row.highest_price_since_publication, 'KRW') },
    {
      key: 'low_buy_return',
      label: '저가매수',
      value: (row) => row.lowest_price_current_return,
      render: (row) => pct(row.lowest_price_current_return),
      className: (row) => ((row.lowest_price_current_return ?? 0) >= 0 ? 'gain-text' : 'loss-text'),
    },
    {
      key: 'q75_buy_return',
      label: 'Q75매수',
      value: (row) => row.q75_price_current_return,
      render: (row) => pct(row.q75_price_current_return),
      className: (row) => ((row.q75_price_current_return ?? 0) >= 0 ? 'gain-text' : 'loss-text'),
    },
    {
      key: 'q100_sell_return',
      label: '고가매도',
      value: (row) => row.highest_price_realized_return,
      render: (row) => pct(row.highest_price_realized_return),
      className: (row) => ((row.highest_price_realized_return ?? 0) >= 0 ? 'gain-text' : 'loss-text'),
    },
    { key: 'target', label: '목표여력', value: (row) => row.target_upside_remaining, render: (row) => targetUpsideCell(row) },
  ];
  return <SortableDataTable rows={rows} columns={columns} filename="price-opportunity.csv" initialSort="publication_date" empty="가격 기회 데이터가 없습니다." />;
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
  return row.target_hit ? '도달' : pct(row.target_upside_remaining);
}
