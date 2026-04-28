export function formatPercent(value: number | null | undefined, digits = 1): string {
  if (value === null || value === undefined || !Number.isFinite(value)) return '—';
  return `${(value * 100).toLocaleString('ko-KR', { maximumFractionDigits: digits, minimumFractionDigits: digits })}%`;
}

export function formatMultiple(value: number | null | undefined, digits = 2): string {
  if (value === null || value === undefined || !Number.isFinite(value)) return '—';
  return `${value.toLocaleString('ko-KR', { maximumFractionDigits: digits })}배`;
}

export function formatKrw(value: number | null | undefined): string {
  if (value === null || value === undefined || !Number.isFinite(value)) return '—';
  const abs = Math.abs(value);
  if (abs >= 1_0000_0000_0000) return `${(value / 1_0000_0000_0000).toLocaleString('ko-KR', { maximumFractionDigits: 2 })}조원`;
  if (abs >= 1_0000_0000) return `${(value / 1_0000_0000).toLocaleString('ko-KR', { maximumFractionDigits: 2 })}억원`;
  if (abs >= 10_000) return `${(value / 10_000).toLocaleString('ko-KR', { maximumFractionDigits: 1 })}만원`;
  return `${Math.round(value).toLocaleString('ko-KR')}원`;
}

export function formatKrwMillions(value: number | null | undefined): string {
  return formatKrw(value);
}

export function formatDays(value: number | null | undefined): string {
  if (value === null || value === undefined || !Number.isFinite(value)) return '—';
  return `${Math.round(value).toLocaleString('ko-KR')}거래일`;
}

export function formatDateKo(value: string | null | undefined): string {
  if (!value) return '—';
  const [year, month, day] = value.slice(0, 10).split('-');
  if (!year || !month || !day) return value;
  return `${year}.${month}.${day}`;
}

export function signedClass(value: number | null | undefined): string {
  if (value === null || value === undefined || !Number.isFinite(value)) return '';
  return value >= 0 ? 'good' : 'bad';
}
