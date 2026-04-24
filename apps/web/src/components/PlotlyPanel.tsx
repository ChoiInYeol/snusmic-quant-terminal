'use client';

import dynamic from 'next/dynamic';
import type { StrategyRun } from '../lib/data';

const Plot = dynamic(() => import('react-plotly.js'), { ssr: false });

export function StrategyScatter({ strategies, selectedRunId }: { strategies: StrategyRun[]; selectedRunId: string }) {
  const points = strategies.filter((item) => Number.isFinite(item.annualized_volatility) && Number.isFinite(item.total_return));
  const frontier = [...points]
    .sort((a, b) => (a.annualized_volatility ?? 0) - (b.annualized_volatility ?? 0))
    .reduce<StrategyRun[]>((acc, item) => {
      const bestReturn = acc.length ? acc[acc.length - 1].total_return : -Infinity;
      if (item.total_return > bestReturn) acc.push(item);
      return acc;
    }, []);

  return (
    <Plot
      data={[
        {
          type: 'scatter',
          mode: 'lines+markers',
          x: frontier.map((item) => item.annualized_volatility),
          y: frontier.map((item) => item.total_return),
          text: frontier.map((item) => item.strategy_name),
          line: { color: '#0f766e', width: 2.5 },
          marker: { size: 7, color: '#0f766e' },
          hovertemplate: '효율적 경계<br>%{text}<br>수익 %{y:.1%}<br>변동성 %{x:.1%}<extra></extra>',
          name: 'Efficient frontier',
        },
        {
          type: 'scatter',
          mode: 'markers',
          x: points.map((item) => item.annualized_volatility),
          y: points.map((item) => item.total_return),
          text: points.map((item) => item.strategy_name),
          customdata: points.map((item) => [item.max_drawdown, item.weighting, item.lookback_days]),
          marker: {
            size: points.map((item) => (item.run_id === selectedRunId ? 18 : 11)),
            color: points.map((item) => (item.run_id === selectedRunId ? '#2454a6' : '#94a3b8')),
            line: { color: '#ffffff', width: 1 },
          },
          hovertemplate: '%{text}<br>수익 %{y:.1%}<br>변동성 %{x:.1%}<br>MDD %{customdata[0]:.1%}<br>%{customdata[1]} · %{customdata[2]}일<extra></extra>',
          name: 'Strategies',
        },
      ]}
      layout={{
        autosize: true,
        margin: { l: 54, r: 18, t: 10, b: 44 },
        paper_bgcolor: '#fbfcfd',
        plot_bgcolor: '#fbfcfd',
        font: { color: '#334155', family: '"Pretendard Variable", Pretendard, system-ui, sans-serif' },
        xaxis: { title: { text: '연환산 변동성' }, tickformat: '.0%', gridcolor: '#eef2f7' },
        yaxis: { title: { text: '총수익' }, tickformat: '.0%', gridcolor: '#eef2f7' },
        legend: { orientation: 'h', x: 0, y: -0.22 },
        showlegend: true,
      }}
      config={{ displayModeBar: false, responsive: true }}
      className="plotly-fit"
      useResizeHandler
      style={{ width: '100%', height: '320px' }}
    />
  );
}
