import type { ChartIndexRow } from '../lib/data';

export function SymbolSelect({ index, value, onChange }: { index: ChartIndexRow[]; value: string; onChange: (symbol: string) => void }) {
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
