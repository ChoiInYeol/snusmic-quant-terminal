'use client';

import { useMemo, useState } from 'react';
import type { MonthlyHoldingRow, ReportTargetDigest } from '@/lib/artifacts';
import { formatKrw, formatPercent } from '@/lib/format';
import { PaginationControls, SortHeader, pageRows, sortRows, useUrlBackedStrategy, type SortState } from './TableControls';

type Props = {
  monthly: MonthlyHoldingRow[];
  personaLabels: Record<string, string>;
  targetsBySymbol: Record<string, ReportTargetDigest>;
};

type MonthlySortKey = 'month' | 'strategy' | 'market' | 'symbol' | 'target' | 'qty' | 'marketValue' | 'weight';

const STACK_COLORS = ['#d7ff4f', '#35f2c2', '#8ab4ff', '#ffd166', '#ff6f91', '#b892ff', '#7ee787', '#fca5a5', '#cbd5e1'];

export function PortfolioHistory({ monthly, personaLabels, targetsBySymbol }: Props) {
  const personas = useMemo(() => ['all', ...Array.from(new Set(monthly.map((row) => row.persona))).sort()], [monthly]);
  const months = useMemo(() => Array.from(new Set(monthly.map((row) => row.monthEnd))).sort().reverse(), [monthly]);
  const [persona, setPersona] = useState('all');
  const [month, setMonth] = useState(months[0] ?? '');
  const [sort, setSort] = useState<SortState<MonthlySortKey>>({ key: 'weight', direction: 'desc' });
  const [page, setPage] = useState(0);
  const [pageSize, setPageSize] = useState(25);
  useUrlBackedStrategy(persona, setPersona, personas);

  const filtered = useMemo(() => monthly.filter((row) => (persona === 'all' || row.persona === persona) && (!month || row.monthEnd === month)), [month, monthly, persona]);
  const sorted = useMemo(() => sortRows(filtered, sort, {
    month: (row) => row.monthEnd,
    strategy: (row) => personaLabels[row.persona] ?? row.persona,
    market: (row) => marketLabel(targetsBySymbol[row.symbol]?.marketRegion),
    symbol: (row) => row.company || row.symbol,
    target: (row) => targetsBySymbol[row.symbol]?.targetPriceKrw,
    qty: (row) => row.qty,
    marketValue: (row) => row.marketValueKrw,
    weight: (row) => row.weightInPortfolio,
  }), [filtered, personaLabels, sort, targetsBySymbol]);
  const rows = useMemo(() => pageRows(sorted, page, pageSize), [page, pageSize, sorted]);
  const stacks = useMemo(() => buildStacks(monthly, persona), [monthly, persona]);
  const updateSort = (key: MonthlySortKey) => {
    setSort((current) => ({ key, direction: current.key === key && current.direction === 'desc' ? 'asc' : 'desc' }));
    setPage(0);
  };

  return (
    <div className="grid" style={{ gap: '1rem' }}>
      <section className="panel report-table-panel strategy-filter-panel">
        <h2>전략 선택</h2>
        <div className="strategy-tabs" role="group" aria-label="전략 선택">
          {personas.map((item) => (
            <button type="button" key={item} aria-pressed={persona === item} className={persona === item ? 'active' : ''} onClick={() => { setPersona(item); setPage(0); }}>
              {item === 'all' ? '전체 전략' : personaLabels[item] ?? item}
            </button>
          ))}
        </div>
        <div className="table-toolbar" aria-label="월말 포트폴리오 필터">
          <label>
            <span>월말 기준일</span>
            <select value={month} onChange={(event) => { setMonth(event.target.value); setPage(0); }}>
              {months.map((item) => <option key={item} value={item}>{item}</option>)}
            </select>
          </label>
          <button type="button" onClick={() => downloadMonthly(sorted, targetsBySymbol)}>현재 보기 CSV</button>
        </div>
      </section>

      <section className="panel">
        <h2>포트폴리오 비중 추이 · 100% 스택바</h2>
        <p className="muted">월말마다 상위 8개 종목과 기타를 100%로 정규화해 전략별 보유 구조 변화를 보여줍니다.</p>
        <div className="stacked-history" aria-label="월말 포트폴리오 비중 추이">
          {stacks.map((stack) => (
            <div className="stack-row" key={stack.month}>
              <div className="stack-label">{stack.month}</div>
              <div className="stack-bar">
                {stack.segments.map((segment, index) => (
                  <span
                    key={`${stack.month}-${segment.symbol}`}
                    style={{ width: `${Math.max(0, segment.weight * 100)}%`, background: STACK_COLORS[index % STACK_COLORS.length] }}
                    title={`${segment.symbol}: ${formatPercent(segment.weight)}`}
                  />
                ))}
              </div>
              <div className="stack-legend-inline">{stack.segments.slice(0, 4).map((segment) => segment.symbol).join(' · ')}</div>
            </div>
          ))}
        </div>
      </section>

      <section className="panel">
        <h2>{month} 월말 포트폴리오</h2>
        <p className="muted">과거 특정 시점에 어떤 포트폴리오였는지 확인하는 전용 페이지입니다.</p>
        <PaginationControls page={page} pageCount={Math.ceil(sorted.length / pageSize)} totalRows={sorted.length} pageSize={pageSize} onPageChange={setPage} onPageSizeChange={(size) => { setPageSize(size); setPage(0); }} />
        <div className="table-wrap inset">
          <table>
            <thead><tr>
              <th><SortHeader label="월말" sortKey="month" sort={sort} onSort={updateSort} /></th>
              <th><SortHeader label="전략" sortKey="strategy" sort={sort} onSort={updateSort} /></th>
              <th><SortHeader label="시장" sortKey="market" sort={sort} onSort={updateSort} /></th>
              <th><SortHeader label="심볼" sortKey="symbol" sort={sort} onSort={updateSort} /></th>
              <th><SortHeader label="목표가" sortKey="target" sort={sort} onSort={updateSort} /></th>
              <th><SortHeader label="수량" sortKey="qty" sort={sort} onSort={updateSort} /></th>
              <th><SortHeader label="평가액" sortKey="marketValue" sort={sort} onSort={updateSort} /></th>
              <th><SortHeader label="비중" sortKey="weight" sort={sort} onSort={updateSort} /></th>
            </tr></thead>
            <tbody>
              {rows.map((row) => {
                const target = targetsBySymbol[row.symbol];
                return (
                <tr key={`${row.persona}-${row.monthEnd}-${row.symbol}`}>
                  <td>{row.monthEnd}</td>
                  <td>{personaLabels[row.persona] ?? row.persona}</td>
                  <td><span className="pill">{marketLabel(target?.marketRegion)}</span></td>
                  <td>{row.company || row.symbol}<div className="muted"><a href={`/reports/${row.symbol}`}>{row.symbol}</a></div></td>
                  <td>{formatKrw(target?.targetPriceKrw)}<div className="muted">{target?.publicationDate ?? '—'}</div></td>
                  <td>{row.qty?.toLocaleString('ko-KR') ?? '—'}</td>
                  <td>{formatKrw(row.marketValueKrw)}</td>
                  <td>{formatPercent(row.weightInPortfolio)}</td>
                </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      </section>
    </div>
  );
}

function buildStacks(rows: MonthlyHoldingRow[], persona: string) {
  const groups = new Map<string, MonthlyHoldingRow[]>();
  for (const row of rows) {
    if (persona !== 'all' && row.persona !== persona) continue;
    const key = persona === 'all' ? `${row.monthEnd} · ${row.persona}` : row.monthEnd;
    groups.set(key, [...(groups.get(key) ?? []), row]);
  }
  return [...groups.entries()].sort(([a], [b]) => b.localeCompare(a)).slice(0, 24).reverse().map(([month, group]) => {
    const sorted = [...group].sort((a, b) => (b.weightInPortfolio ?? 0) - (a.weightInPortfolio ?? 0));
    const top = sorted.slice(0, 8).map((row) => ({ symbol: row.symbol, weight: Math.max(0, row.weightInPortfolio ?? 0) }));
    const other = sorted.slice(8).reduce((sum, row) => sum + Math.max(0, row.weightInPortfolio ?? 0), 0);
    const total = top.reduce((sum, row) => sum + row.weight, other) || 1;
    const segments = [...top, ...(other > 0 ? [{ symbol: '기타', weight: other }] : [])].map((segment) => ({ ...segment, weight: segment.weight / total }));
    return { month, segments };
  });
}

function downloadMonthly(rows: MonthlyHoldingRow[], targetsBySymbol: Record<string, ReportTargetDigest>) {
  const headers = ['month_end', 'persona', 'market_region', 'symbol', 'company', 'target_price_krw', 'target_publication_date', 'qty', 'market_value_krw', 'weight_in_portfolio'];
  const csv = [headers.join(','), ...rows.map((row) => {
    const target = targetsBySymbol[row.symbol];
    return [row.monthEnd, row.persona, target?.marketRegion ?? '', row.symbol, row.company, target?.targetPriceKrw ?? '', target?.publicationDate ?? '', row.qty ?? '', row.marketValueKrw ?? '', row.weightInPortfolio ?? ''].map(csvEscape).join(',');
  })].join('\n');
  const blob = new Blob([`\ufeff${csv}`], { type: 'text/csv;charset=utf-8;' });
  const url = URL.createObjectURL(blob);
  const a = document.createElement('a');
  a.href = url;
  a.download = 'snusmic-monthly-portfolio.csv';
  document.body.appendChild(a);
  a.click();
  document.body.removeChild(a);
  URL.revokeObjectURL(url);
}

function csvEscape(value: unknown): string {
  const text = String(value ?? '');
  return /[",\n]/.test(text) ? `"${text.replaceAll('"', '""')}"` : text;
}

function marketLabel(region: 'domestic' | 'overseas' | undefined): string {
  return region === 'domestic' ? '국내' : '해외';
}
