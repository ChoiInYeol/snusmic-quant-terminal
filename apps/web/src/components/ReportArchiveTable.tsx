import { type Column, SortableDataTable } from './ui/SortableDataTable';
import type { ReportRow } from '../lib/data';
import { num, shortDate } from '../lib/format';

export function ReportArchiveTable({ rows }: { rows: ReportRow[] }) {
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
