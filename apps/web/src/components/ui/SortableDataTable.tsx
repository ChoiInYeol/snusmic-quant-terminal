'use client';

/**
 * Phase 6b — UI primitives extracted from the original ``app/page.tsx``
 * monolith. ``SortableDataTable`` is the table primitive used by every
 * dashboard table (positions, trades, opportunities, reports, signals).
 *
 * The plan's Phase 6c will swap the underlying renderer for
 * ``@tanstack/react-table`` + ``@tanstack/react-virtual``; until then this
 * primitive keeps the same column-config API so consumers do not have to
 * change when the swap lands.
 */

import { useMemo, useState, type ReactNode } from 'react';

export type SortState = { key: string; direction: 'asc' | 'desc' };

export type Column<T> = {
  key: string;
  label: string;
  value: (row: T) => unknown;
  render?: (row: T) => ReactNode;
  className?: (row: T) => string;
};

export function compareValues(a: unknown, b: unknown): number {
  if (a === null || a === undefined || a === '') return 1;
  if (b === null || b === undefined || b === '') return -1;
  if (typeof a === 'number' && typeof b === 'number') return a - b;
  return String(a).localeCompare(String(b), 'ko', { numeric: true });
}

export function useSortedRows<T>(
  rows: T[],
  columns: Column<T>[],
  initialKey: string,
  initialDirection: 'asc' | 'desc' = 'desc',
) {
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

export function SortHeader<T>({
  column,
  sort,
  onSort,
}: {
  column: Column<T>;
  sort: SortState;
  onSort: (key: string) => void;
}) {
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

export function downloadCsv<T>(filename: string, rows: T[], columns: Column<T>[]) {
  const header = columns.map((column) => csvValue(column.label)).join(',');
  const body = rows.map((row) => columns.map((column) => csvValue(column.value(row))).join(',')).join('\n');
  const blob = new Blob([`﻿${header}\n${body}\n`], { type: 'text/csv;charset=utf-8;' });
  const url = URL.createObjectURL(blob);
  const link = document.createElement('a');
  link.href = url;
  link.download = filename;
  link.click();
  URL.revokeObjectURL(url);
}

export function CsvButton<T>({ filename, rows, columns }: { filename: string; rows: T[]; columns: Column<T>[] }) {
  return (
    <button className="csv-button" onClick={() => downloadCsv(filename, rows, columns)} type="button">
      CSV
    </button>
  );
}

export function SortableDataTable<T>({
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
