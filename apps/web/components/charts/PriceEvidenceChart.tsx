'use client';

import { createChart, createSeriesMarkers, ColorType, LineSeries, LineStyle, type IChartApi, type ISeriesApi, type LineData, type Time } from 'lightweight-charts';
import { useEffect, useRef } from 'react';

type Props = {
  priceSeries: { time: string; value: number }[];
  targetPrice: number | null;
  publicationDate: string;
  targetHitDate: string | null;
};

export function PriceEvidenceChart({ priceSeries, targetPrice, publicationDate, targetHitDate }: Props) {
  const ref = useRef<HTMLDivElement | null>(null);

  useEffect(() => {
    if (!ref.current) return;
    const chart: IChartApi = createChart(ref.current, {
      autoSize: true,
      height: 420,
      layout: { background: { type: ColorType.Solid, color: '#0f172a' }, textColor: '#cbd5e1' },
      grid: { vertLines: { color: '#1f2937' }, horzLines: { color: '#1f2937' } },
      rightPriceScale: { borderColor: '#334155' },
      timeScale: { borderColor: '#334155' },
    });
    const closeSeries: ISeriesApi<'Line'> = chart.addSeries(LineSeries, { color: '#60a5fa', lineWidth: 2 });
    closeSeries.setData(priceSeries.map((point) => ({ time: point.time as Time, value: point.value })));
    createSeriesMarkers(closeSeries, [
      { time: publicationDate as Time, position: 'belowBar', color: '#fbbf24', shape: 'arrowUp', text: 'published' },
      ...(targetHitDate ? [{ time: targetHitDate as Time, position: 'aboveBar' as const, color: '#34d399', shape: 'circle' as const, text: 'target hit' }] : []),
    ]);
    if (targetPrice && priceSeries.length > 0) {
      const targetData: LineData[] = priceSeries.map((point) => ({ time: point.time as Time, value: targetPrice }));
      const targetSeries = chart.addSeries(LineSeries, { color: '#f87171', lineWidth: 1, lineStyle: LineStyle.Dashed });
      targetSeries.setData(targetData);
    }
    chart.timeScale().fitContent();
    return () => chart.remove();
  }, [priceSeries, publicationDate, targetHitDate, targetPrice]);

  if (priceSeries.length === 0) {
    return <div className="panel chart-box">No price path is available for this report symbol.</div>;
  }
  return <div ref={ref} className="chart-box" aria-label="Close price path with target line and report markers" />;
}
