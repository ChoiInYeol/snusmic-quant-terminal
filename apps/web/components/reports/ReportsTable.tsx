'use client';

import Link from 'next/link';
import {
  flexRender,
  getCoreRowModel,
  getFilteredRowModel,
  getSortedRowModel,
  type ColumnDef,
  type Row,
  type SortingState,
  useReactTable,
} from '@tanstack/react-table';
import { useMemo, useState } from 'react';
import type { ReportRow } from '@/lib/artifacts';
import { formatDays, formatKrw, formatPercent } from '@/lib/format';

type HitFilter = 'all' | 'hit' | 'open';
type ReturnFilter = 'all' | 'positive' | 'negative';

type ReportsTableProps = {
  reports: ReportRow[];
};

const csvHeaders: Array<[string, (report: ReportRow) => string | number | boolean | null]> = [
  ['리포트 ID', (report) => report.reportId],
  ['기업명', (report) => report.company],
  ['심볼', (report) => report.symbol],
  ['거래소', (report) => report.exchange],
  ['시장구분', (report) => marketLabel(marketRegionForSymbol(report.symbol, report.exchange))],
  ['게시일', (report) => report.publicationDate],
  ['진입가(KRW)', (report) => report.entryPriceKrw],
  ['목표가(KRW)', (report) => report.targetPriceKrw],
  ['제시 상승여력', (report) => report.targetUpsideAtPub],
  ['현재 수익률', (report) => report.currentReturn],
  ['최고 수익률', (report) => report.peakReturn],
  ['최저 수익률', (report) => report.troughReturn],
  ['목표 달성', (report) => report.targetHit],
  ['목표 달성일', (report) => report.targetHitDate],
  ['달성 소요일', (report) => report.daysToTarget],
  ['최근 종가일', (report) => report.lastCloseDate],
  ['PDF URL', (report) => report.pdfUrl],
];

export function ReportsTable({ reports }: ReportsTableProps) {
  const [sorting, setSorting] = useState<SortingState>([{ id: 'currentReturn', desc: true }]);
  const [globalFilter, setGlobalFilter] = useState('');
  const [exchangeFilter, setExchangeFilter] = useState('all');
  const [hitFilter, setHitFilter] = useState<HitFilter>('all');
  const [returnFilter, setReturnFilter] = useState<ReturnFilter>('all');

  const exchanges = useMemo(
    () => ['all', ...Array.from(new Set(reports.map((report) => report.exchange).filter(Boolean))).sort()],
    [reports],
  );

  const columns = useMemo<ColumnDef<ReportRow>[]>(
    () => [
      {
        accessorKey: 'company',
        header: '리포트',
        cell: ({ row }) => (
          <div className="report-title-cell">
            <Link href={`/reports/${row.original.symbol}`}>{row.original.company}</Link>
            <span className="muted">{row.original.symbol} · {row.original.exchange || '—'}</span>
          </div>
        ),
      },
      {
        id: 'marketRegion',
        header: '시장',
        accessorFn: (report) => marketLabel(marketRegionForSymbol(report.symbol, report.exchange)),
        cell: ({ row }) => <span className="pill">{marketLabel(marketRegionForSymbol(row.original.symbol, row.original.exchange))}</span>,
      },
      { accessorKey: 'publicationDate', header: '게시일' },
      {
        accessorKey: 'entryPriceKrw',
        header: '진입가',
        cell: ({ getValue }) => formatKrw(getValue<number | null>()),
      },
      {
        accessorKey: 'targetPriceKrw',
        header: '목표가',
        cell: ({ getValue }) => formatKrw(getValue<number | null>()),
      },
      {
        accessorKey: 'targetUpsideAtPub',
        header: '제시 상승여력',
        cell: ({ getValue }) => formatPercent(getValue<number | null>()),
      },
      {
        accessorKey: 'currentReturn',
        header: '현재 수익률',
        cell: ({ getValue }) => {
          const value = getValue<number | null>();
          return <span className={(value ?? 0) >= 0 ? 'good' : 'bad'}>{formatPercent(value)}</span>;
        },
      },
      {
        accessorKey: 'peakReturn',
        header: '최고',
        cell: ({ getValue }) => <span className="good">{formatPercent(getValue<number | null>())}</span>,
      },
      {
        accessorKey: 'troughReturn',
        header: '최저',
        cell: ({ getValue }) => <span className="bad">{formatPercent(getValue<number | null>())}</span>,
      },
      {
        accessorKey: 'targetHit',
        header: '목표 달성',
        cell: ({ row }) => {
          if (isBearishReport(row.original)) {
            return row.original.targetHit ? (
              <span className="pill good">매도 적중 · {formatDays(row.original.daysToTarget)}</span>
            ) : (
              <span className="pill warn">매도 의견 · 미달성</span>
            );
          }
          if ((row.original.targetUpsideAtPub ?? 0) <= 0) {
            return <span className="pill warn">이미 초과/비실행</span>;
          }
          return row.original.targetHit ? (
            <span className="pill good">달성 · {formatDays(row.original.daysToTarget)}</span>
          ) : (
            <span className="pill">미달성</span>
          );
        },
      },
      {
        accessorKey: 'lastCloseDate',
        header: '최근 가격일',
      },
    ],
    [],
  );

  // TanStack Table intentionally returns imperative helpers; this component does not pass them into memoized children.
  // eslint-disable-next-line react-hooks/incompatible-library
  const table = useReactTable({
    data: reports,
    columns,
    state: { sorting, globalFilter },
    onSortingChange: setSorting,
    onGlobalFilterChange: setGlobalFilter,
    globalFilterFn: globalTextFilter,
    getCoreRowModel: getCoreRowModel(),
    getFilteredRowModel: getFilteredRowModel(),
    getSortedRowModel: getSortedRowModel(),
  });

  const filteredRows = table.getSortedRowModel().rows.filter((row) => {
    const report = row.original;
    if (exchangeFilter !== 'all' && report.exchange !== exchangeFilter) return false;
    if (hitFilter === 'hit' && !report.targetHit) return false;
    if (hitFilter === 'open' && report.targetHit) return false;
    if (returnFilter === 'positive' && (report.currentReturn ?? -Infinity) < 0) return false;
    if (returnFilter === 'negative' && (report.currentReturn ?? Infinity) >= 0) return false;
    return true;
  });

  return (
    <section className="panel report-table-panel">
      <div className="table-toolbar" aria-label="리포트 표 필터">
        <label>
          <span>검색</span>
          <input
            value={globalFilter ?? ''}
            onChange={(event) => setGlobalFilter(event.target.value)}
            placeholder="기업명, 심볼, 리포트 제목 검색"
          />
        </label>
        <label>
          <span>거래소</span>
          <select value={exchangeFilter} onChange={(event) => setExchangeFilter(event.target.value)}>
            {exchanges.map((exchange) => (
              <option key={exchange} value={exchange}>{exchange === 'all' ? '전체' : exchange}</option>
            ))}
          </select>
        </label>
        <label>
          <span>목표 달성</span>
          <select value={hitFilter} onChange={(event) => setHitFilter(event.target.value as HitFilter)}>
            <option value="all">전체</option>
            <option value="hit">달성</option>
            <option value="open">미달성/진행</option>
          </select>
        </label>
        <label>
          <span>현재 수익률</span>
          <select value={returnFilter} onChange={(event) => setReturnFilter(event.target.value as ReturnFilter)}>
            <option value="all">전체</option>
            <option value="positive">0% 이상</option>
            <option value="negative">0% 미만</option>
          </select>
        </label>
        <div className="download-actions">
          <button type="button" onClick={() => downloadCsv('snusmic-reports-all.csv', reports)}>
            전체 CSV
          </button>
          <button type="button" onClick={() => downloadCsv('snusmic-reports-current.csv', filteredRows.map((row) => row.original))}>
            현재 보기 CSV
          </button>
        </div>
      </div>

      <div className="table-meta">
        <span>현재 {filteredRows.length.toLocaleString('ko-KR')}개 / 전체 {reports.length.toLocaleString('ko-KR')}개</span>
        <span className="muted">열 제목을 클릭해 정렬합니다.</span>
      </div>

      <div className="table-wrap">
        <table>
          <thead>
            {table.getHeaderGroups().map((headerGroup) => (
              <tr key={headerGroup.id}>
                {headerGroup.headers.map((header) => (
                  <th key={header.id}>
                    {header.isPlaceholder ? null : (
                      <button
                        type="button"
                        className="sort-button"
                        onClick={header.column.getToggleSortingHandler()}
                        disabled={!header.column.getCanSort()}
                      >
                        {flexRender(header.column.columnDef.header, header.getContext())}
                        <span aria-hidden="true">{sortIndicator(header.column.getIsSorted())}</span>
                      </button>
                    )}
                  </th>
                ))}
              </tr>
            ))}
          </thead>
          <tbody>
            {filteredRows.map((row) => (
              <tr key={row.id}>
                {row.getVisibleCells().map((cell) => (
                  <td key={cell.id}>{flexRender(cell.column.columnDef.cell, cell.getContext())}</td>
                ))}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </section>
  );
}

function globalTextFilter(row: Row<ReportRow>, _columnId: string, filterValue: string): boolean {
  const needle = filterValue.trim().toLocaleLowerCase('ko-KR');
  if (!needle) return true;
  const report = row.original;
  return [report.company, report.symbol, report.exchange, report.title, report.publicationDate]
    .filter(Boolean)
    .some((value) => value.toLocaleLowerCase('ko-KR').includes(needle));
}

function sortIndicator(direction: false | 'asc' | 'desc'): string {
  if (direction === 'asc') return ' ↑';
  if (direction === 'desc') return ' ↓';
  return ' ↕';
}

function downloadCsv(filename: string, rows: ReportRow[]) {
  const csv = [
    csvHeaders.map(([label]) => escapeCsv(label)).join(','),
    ...rows.map((report) => csvHeaders.map(([, read]) => escapeCsv(read(report))).join(',')),
  ].join('\n');
  const blob = new Blob([`\uFEFF${csv}`], { type: 'text/csv;charset=utf-8' });
  const url = URL.createObjectURL(blob);
  const anchor = document.createElement('a');
  anchor.href = url;
  anchor.download = filename;
  document.body.append(anchor);
  anchor.click();
  anchor.remove();
  URL.revokeObjectURL(url);
}

function escapeCsv(value: string | number | boolean | null): string {
  if (value === null) return '';
  const text = String(value);
  if (!/[",\n\r]/.test(text)) return text;
  return `"${text.replaceAll('"', '""')}"`;
}

function isBearishReport(report: ReportRow): boolean {
  return (report.targetUpsideAtPub ?? 0) < 0 && report.caveatFlags.some((flag) => /non_buy_rating:.*(sell|reduce|underperform|매도)/i.test(flag));
}

function marketLabel(region: 'domestic' | 'overseas'): string {
  return region === 'domestic' ? '국내' : '해외';
}

function marketRegionForSymbol(symbol: string, exchange?: string): 'domestic' | 'overseas' {
  const upperExchange = (exchange ?? '').toUpperCase();
  if (symbol.endsWith('.KS') || symbol.endsWith('.KQ') || upperExchange === 'KRX' || upperExchange === 'KOSPI' || upperExchange === 'KOSDAQ') return 'domestic';
  return 'overseas';
}
