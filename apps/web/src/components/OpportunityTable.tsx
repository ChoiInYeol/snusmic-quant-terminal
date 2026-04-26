import { type Column, SortableDataTable } from './ui/SortableDataTable';
import type { PriceMetric } from '../lib/data';
import { num, pct, shortDate } from '../lib/format';

export function OpportunityTable({ rows }: { rows: PriceMetric[] }) {
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

function targetUpsideCell(row: PriceMetric) {
  if ((row.target_upside_remaining ?? 0) > 20) return '검토';
  return pct(row.target_upside_remaining);
}
