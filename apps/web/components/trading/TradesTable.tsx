'use client';

import Link from 'next/link';
import { useMemo, useState } from 'react';
import type { PositionEpisodeRow, TradeRow } from '@/lib/artifacts';
import { formatDays, formatKrw, formatPercent } from '@/lib/format';

type Props = {
  trades: TradeRow[];
  episodes: PositionEpisodeRow[];
  personaLabels: Record<string, string>;
  capitalByPersona: Record<string, number>;
};

export function TradesTable({ trades, episodes, personaLabels, capitalByPersona = {} }: Props) {
  const personas = useMemo(() => ['all', ...Array.from(new Set(trades.map((trade) => trade.persona))).sort()], [trades]);
  const [persona, setPersona] = useState('all');
  const [query, setQuery] = useState('');
  const [side, setSide] = useState('all');

  const filteredTrades = trades.filter((trade) => {
    if (persona !== 'all' && trade.persona !== persona) return false;
    if (side !== 'all' && trade.side !== side) return false;
    const haystack = `${trade.symbol} ${trade.reason} ${trade.reportId ?? ''}`.toLowerCase();
    return haystack.includes(query.toLowerCase());
  });
  const filteredEpisodes = episodes.filter((episode) => {
    if (persona !== 'all' && episode.persona !== persona) return false;
    const haystack = `${episode.symbol} ${episode.company} ${episode.exitReasons}`.toLowerCase();
    return haystack.includes(query.toLowerCase());
  });

  return (
    <div className="grid" style={{ gap: '1rem' }}>
      <section className="panel report-table-panel">
        <div className="table-toolbar" aria-label="매매 필터">
          <label>
            <span>전략</span>
            <select value={persona} onChange={(event) => setPersona(event.target.value)}>
              {personas.map((item) => <option key={item} value={item}>{item === 'all' ? '전체' : personaLabels[item] ?? item}</option>)}
            </select>
          </label>
          <label>
            <span>매수/매도</span>
            <select value={side} onChange={(event) => setSide(event.target.value)}>
              <option value="all">전체</option>
              <option value="buy">매수</option>
              <option value="sell">매도</option>
            </select>
          </label>
          <label>
            <span>검색</span>
            <input value={query} onChange={(event) => setQuery(event.target.value)} placeholder="심볼, 사유, 리포트 ID" />
          </label>
          <button type="button" onClick={() => downloadTrades(filteredTrades)}>CSV 다운로드</button>
        </div>
      </section>

      <section className="panel">
        <h2>포지션 단위 매수·매도 요약</h2>
        <p className="muted">언제 열었고, 언제 닫았고, 어떤 사유로 청산됐는지 확인하는 핵심 테이블입니다.</p>
        <div className="table-wrap inset">
          <table>
            <thead><tr><th>전략</th><th>종목</th><th>매수 시작</th><th>매도/상태</th><th>보유일</th><th>평균 진입</th><th>평균 청산/최근</th><th>종목 수익률</th><th>자본 기여</th><th>매도 기준</th></tr></thead>
            <tbody>
              {filteredEpisodes.slice(0, 300).map((episode) => {
                const pnl = episode.status === 'closed' ? episode.realizedPnlKrw : episode.unrealizedPnlKrw;
                const stockReturn = positionReturn(episode);
                const contribution = capitalContribution(pnl, capitalByPersona[episode.persona]);
                return (
                  <tr key={`${episode.persona}-${episode.symbol}-${episode.openDate}-${episode.closeDate ?? 'open'}`}>
                    <td>{personaLabels[episode.persona] ?? episode.persona}</td>
                    <td><strong>{episode.company || episode.symbol}</strong><div className="muted">{episode.symbol}</div></td>
                    <td>{episode.openDate}<div className="muted">{episode.buyFills ?? 0}회 매수</div></td>
                    <td>{episode.closeDate ?? <span className="pill good">보유중</span>}<div className="muted">{episode.status}</div></td>
                    <td>{formatDays(episode.holdingDays)}</td>
                    <td>{formatKrw(episode.avgEntryPriceKrw)}</td>
                    <td>{formatKrw(episode.avgExitPriceKrw ?? episode.lastCloseKrw)}<div className="muted">손익 {formatKrw(pnl)}</div></td>
                    <td className={(stockReturn ?? 0) >= 0 ? 'good' : 'bad'}>{formatPercent(stockReturn)}</td>
                    <td className={(contribution ?? 0) >= 0 ? 'good' : 'bad'}>{formatPercent(contribution)}</td>
                    <td>{humanReason(episode.exitReasons)}</td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      </section>

      <section className="panel">
        <h2>체결 원장</h2>
        <p className="muted">실제 buy/sell fill 단위 원장입니다. 리포트 ID가 있는 행은 원문 근거로 이동합니다.</p>
        <div className="table-wrap inset">
          <table>
            <thead><tr><th>일자</th><th>전략</th><th>구분</th><th>심볼</th><th>수량</th><th>체결가</th><th>체결금액</th><th>현금잔고</th><th>사유</th><th>근거</th></tr></thead>
            <tbody>
              {filteredTrades.slice(0, 500).map((trade, index) => (
                <tr key={`${trade.persona}-${trade.date}-${trade.symbol}-${trade.side}-${index}`}>
                  <td>{trade.date}</td>
                  <td>{personaLabels[trade.persona] ?? trade.persona}</td>
                  <td><span className={`pill ${trade.side === 'buy' ? 'good' : 'warn'}`}>{trade.side === 'buy' ? '매수' : '매도'}</span></td>
                  <td>{trade.symbol}</td>
                  <td>{trade.qty?.toLocaleString('ko-KR') ?? '—'}</td>
                  <td>{formatKrw(trade.fillPriceKrw)}</td>
                  <td>{formatKrw(trade.grossKrw)}</td>
                  <td>{formatKrw(trade.cashAfterKrw)}</td>
                  <td>{humanReason(trade.reason)}</td>
                  <td>{trade.reportId ? <Link href={`/reports/${trade.reportId}`}>리포트</Link> : '—'}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </section>
    </div>
  );
}

function humanReason(reason: string): string {
  if (reason.includes('target_hit')) return '목표가 도달';
  if (reason.includes('stop')) return '손절/리스크 제한';
  if (reason.includes('rebalance_buy')) return '리밸런싱 매수';
  if (reason.includes('rebalance_sell')) return '리밸런싱 매도';
  if (reason.includes('time')) return '시간 손절';
  return reason.replace(/[()']/g, '') || '—';
}

function downloadTrades(rows: TradeRow[]) {
  const headers = ['date', 'persona', 'side', 'symbol', 'qty', 'fill_price_krw', 'gross_krw', 'cash_after_krw', 'reason', 'report_id'];
  const csv = [headers.join(','), ...rows.map((row) => [row.date, row.persona, row.side, row.symbol, row.qty ?? '', row.fillPriceKrw ?? '', row.grossKrw ?? '', row.cashAfterKrw ?? '', row.reason, row.reportId ?? ''].map(csvEscape).join(','))].join('\n');
  const blob = new Blob([`\ufeff${csv}`], { type: 'text/csv;charset=utf-8;' });
  const url = URL.createObjectURL(blob);
  const a = document.createElement('a');
  a.href = url;
  a.download = 'snusmic-trades-filtered.csv';
  document.body.appendChild(a);
  a.click();
  document.body.removeChild(a);
  URL.revokeObjectURL(url);
}

function csvEscape(value: unknown): string {
  const text = String(value ?? '');
  return /[",\n]/.test(text) ? `"${text.replaceAll('"', '""')}"` : text;
}

function positionReturn(episode: PositionEpisodeRow): number | null {
  const exitOrLast = episode.avgExitPriceKrw ?? episode.lastCloseKrw;
  if (!episode.avgEntryPriceKrw || !exitOrLast || episode.avgEntryPriceKrw <= 0) return null;
  return exitOrLast / episode.avgEntryPriceKrw - 1;
}

function capitalContribution(pnl: number | null, capital: number | undefined): number | null {
  if (pnl === null || pnl === undefined || !capital || capital <= 0) return null;
  return pnl / capital;
}
