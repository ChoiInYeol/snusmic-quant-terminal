'use client';

import { useEffect } from 'react';

export type SortDirection = 'asc' | 'desc';
export type SortState<Key extends string> = { key: Key; direction: SortDirection };

export function SortHeader<Key extends string>({
  label,
  sortKey,
  sort,
  onSort,
}: {
  label: string;
  sortKey: Key;
  sort: SortState<Key>;
  onSort: (key: Key) => void;
}) {
  const active = sort.key === sortKey;
  const indicator = active ? (sort.direction === 'asc' ? '↑' : '↓') : '↕';
  return (
    <button type="button" className="sort-button" onClick={() => onSort(sortKey)} aria-label={`${label} 정렬 ${active ? sort.direction : 'none'}`}>
      {label}<span aria-hidden="true"> {indicator}</span>
    </button>
  );
}

export function PaginationControls({
  page,
  pageCount,
  totalRows,
  pageSize,
  onPageChange,
  onPageSizeChange,
}: {
  page: number;
  pageCount: number;
  totalRows: number;
  pageSize: number;
  onPageChange: (page: number) => void;
  onPageSizeChange: (size: number) => void;
}) {
  const lastPage = Math.max(0, pageCount - 1);
  const safePage = Math.min(Math.max(0, page), lastPage);
  const hasPrevious = safePage > 0;
  const hasNext = pageCount > 0 && safePage < lastPage;
  return (
    <nav className="pagination-bar" aria-label="페이지 이동">
      <span>총 {totalRows.toLocaleString('ko-KR')}행 · {pageCount ? safePage + 1 : 0}/{Math.max(1, pageCount)}쪽</span>
      <label className="page-size-label">
        <span>페이지당</span>
        <select value={pageSize} onChange={(event) => onPageSizeChange(Number(event.target.value))}>
          {[10, 25, 50, 100].map((size) => <option key={size} value={size}>{size}</option>)}
        </select>
      </label>
      <button type="button" onClick={() => onPageChange(0)} disabled={!hasPrevious}>처음</button>
      <button type="button" onClick={() => onPageChange(Math.max(0, safePage - 1))} disabled={!hasPrevious}>이전</button>
      <button type="button" onClick={() => onPageChange(Math.min(lastPage, safePage + 1))} disabled={!hasNext}>다음</button>
      <button type="button" onClick={() => onPageChange(lastPage)} disabled={!hasNext}>끝</button>
    </nav>
  );
}

export function useUrlBackedStrategy(persona: string, setPersona: (value: string) => void, validPersonas: string[]) {
  useEffect(() => {
    const query = new URLSearchParams(window.location.search);
    const requested = query.get('strategy');
    if (requested && validPersonas.includes(requested)) setPersona(requested);
  }, [setPersona, validPersonas]);

  useEffect(() => {
    const url = new URL(window.location.href);
    if (persona === 'all') url.searchParams.delete('strategy');
    else url.searchParams.set('strategy', persona);
    const nextUrl = `${url.pathname}${url.search}${url.hash}`;
    const currentUrl = `${window.location.pathname}${window.location.search}${window.location.hash}`;
    if (nextUrl !== currentUrl) window.history.replaceState(null, '', nextUrl);
  }, [persona]);
}

export function sortRows<T, Key extends string>(rows: T[], sort: SortState<Key>, read: Record<Key, (row: T) => string | number | null | undefined>): T[] {
  const getValue = read[sort.key];
  return [...rows].sort((a, b) => compare(getValue(a), getValue(b), sort.direction));
}

export function compare(a: string | number | null | undefined, b: string | number | null | undefined, direction: SortDirection): number {
  const modifier = direction === 'asc' ? 1 : -1;
  if (a === null || a === undefined || a === '') return 1;
  if (b === null || b === undefined || b === '') return -1;
  if (typeof a === 'number' && typeof b === 'number') return (a - b) * modifier;
  return String(a).localeCompare(String(b), 'ko-KR', { numeric: true }) * modifier;
}

export function pageRows<T>(rows: T[], page: number, pageSize: number): T[] {
  const safePage = Math.max(0, page);
  return rows.slice(safePage * pageSize, safePage * pageSize + pageSize);
}
