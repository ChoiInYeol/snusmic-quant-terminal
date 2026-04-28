'use client';

import { useMemo, useState } from 'react';
import type { HoldingRow, MonthlyHoldingRow } from '@/lib/artifacts';
import { formatDays, formatKrw, formatPercent } from '@/lib/format';

type Props = {
  holdings: HoldingRow[];
  monthly: MonthlyHoldingRow[];
  personaLabels: Record<string, string>;
  capitalByPersona: Record<string, number>;
};

export function PortfolioTables({ holdings, monthly, personaLabels, capitalByPersona = {} }: Props) {
  const personas = useMemo(() => ['all', ...Array.from(new Set(holdings.map((row) => row.persona))).sort()], [holdings]);
  const months = useMemo(() => Array.from(new Set(monthly.map((row) => row.monthEnd))).sort().reverse(), [monthly]);
  const [persona, setPersona] = useState('all');
  const [month, setMonth] = useState(months[0] ?? '');
  const currentRows = holdings.filter((row) => persona === 'all' || row.persona === persona);
  const monthRows = monthly.filter((row) => row.monthEnd === month && (persona === 'all' || row.persona === persona));

  return (
    <div className="grid" style={{ gap: '1rem' }}>
      <section className="panel report-table-panel">
        <div className="table-toolbar" aria-label="포트폴리오 필터">
          <label><span>전략</span><select value={persona} onChange={(event) => setPersona(event.target.value)}>{personas.map((item) => <option key={item} value={item}>{item === 'all' ? '전체' : personaLabels[item] ?? item}</option>)}</select></label>
          <label><span>과거 월말</span><select value={month} onChange={(event) => setMonth(event.target.value)}>{months.map((item) => <option key={item} value={item}>{item}</option>)}</select></label>
          <button type="button" onClick={() => downloadHoldings(currentRows)}>현재 포트폴리오 CSV</button>
        </div>
      </section>

      <section className="panel">
        <h2>현재 보유 포트폴리오</h2>
        <p className="muted">현재 어떤 종목을 얼마나 들고 있는지, 평단·최근가·미실현 손익을 바로 확인합니다.</p>
        <div className="table-wrap inset">
          <table>
            <thead><tr><th>전략</th><th>종목</th><th>수량</th><th>평단</th><th>최근가</th><th>평가액</th><th>종목 수익률</th><th>자본 기여</th><th>최초 매수</th></tr></thead>
            <tbody>
              {currentRows.slice(0, 300).map((row) => {
                const contribution = capitalContribution(row.unrealizedPnlKrw, capitalByPersona[row.persona]);
                return (
                  <tr key={`${row.persona}-${row.symbol}`}>
                    <td>{personaLabels[row.persona] ?? row.persona}</td>
                    <td><strong>{row.company || row.symbol}</strong><div className="muted">{row.symbol}</div></td>
                    <td>{row.qty?.toLocaleString('ko-KR') ?? '—'}</td>
                    <td>{formatKrw(row.avgCostKrw)}</td>
                    <td>{formatKrw(row.lastCloseKrw)}</td>
                    <td>{formatKrw(row.marketValueKrw)}<div className="muted">손익 {formatKrw(row.unrealizedPnlKrw)}</div></td>
                    <td className={(row.unrealizedReturn ?? 0) >= 0 ? 'good' : 'bad'}>{formatPercent(row.unrealizedReturn)}</td>
                    <td className={(contribution ?? 0) >= 0 ? 'good' : 'bad'}>{formatPercent(contribution)}</td>
                    <td>{row.firstBuyDate}<div className="muted">{formatDays(row.holdingDays)}</div></td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      </section>

      <section className="panel">
        <h2>{month} 월말 포트폴리오</h2>
        <p className="muted">과거 특정 시점에 어떤 포트폴리오였는지 확인합니다.</p>
        <div className="table-wrap inset">
          <table>
            <thead><tr><th>전략</th><th>심볼</th><th>수량</th><th>평가액</th><th>비중</th></tr></thead>
            <tbody>
              {monthRows.slice(0, 300).map((row) => (
                <tr key={`${row.persona}-${row.monthEnd}-${row.symbol}`}>
                  <td>{personaLabels[row.persona] ?? row.persona}</td>
                  <td>{row.company || row.symbol}<div className="muted">{row.symbol}</div></td>
                  <td>{row.qty?.toLocaleString('ko-KR') ?? '—'}</td>
                  <td>{formatKrw(row.marketValueKrw)}</td>
                  <td>{formatPercent(row.weightInPortfolio)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </section>
    </div>
  );
}

function downloadHoldings(rows: HoldingRow[]) {
  const headers = ['persona', 'symbol', 'company', 'qty', 'avg_cost_krw', 'last_close_krw', 'market_value_krw', 'unrealized_pnl_krw', 'unrealized_return', 'first_buy_date'];
  const csv = [headers.join(','), ...rows.map((row) => [row.persona, row.symbol, row.company, row.qty ?? '', row.avgCostKrw ?? '', row.lastCloseKrw ?? '', row.marketValueKrw ?? '', row.unrealizedPnlKrw ?? '', row.unrealizedReturn ?? '', row.firstBuyDate ?? ''].map(csvEscape).join(','))].join('\n');
  const blob = new Blob([`\ufeff${csv}`], { type: 'text/csv;charset=utf-8;' });
  const url = URL.createObjectURL(blob);
  const a = document.createElement('a');
  a.href = url;
  a.download = 'snusmic-current-portfolio.csv';
  document.body.appendChild(a);
  a.click();
  document.body.removeChild(a);
  URL.revokeObjectURL(url);
}

function csvEscape(value: unknown): string {
  const text = String(value ?? '');
  return /[",\n]/.test(text) ? `"${text.replaceAll('"', '""')}"` : text;
}

function capitalContribution(pnl: number | null, capital: number | undefined): number | null {
  if (pnl === null || pnl === undefined || !capital || capital <= 0) return null;
  return pnl / capital;
}
