'use client';

import { ColorType, createChart, LineSeries, LineStyle, type IChartApi, type Time } from 'lightweight-charts';
import { useEffect, useRef } from 'react';
import type { PricePoint } from '@/lib/types';

type Props = {
  priceSeries: PricePoint[];
  targetPriceKrw: number | null;
  publicationDate: string;
  targetHitDate: string | null;
};

export function PriceEvidenceChart({ priceSeries, targetPriceKrw, publicationDate, targetHitDate }: Props) {
  const ref = useRef<HTMLDivElement | null>(null);

  useEffect(() => {
    if (!ref.current || priceSeries.length === 0) return;
    const chart: IChartApi = createChart(ref.current, {
      autoSize: true,
      height: 420,
      layout: { background: { type: ColorType.Solid, color: '#0f172a' }, textColor: '#dbeafe' },
      grid: { vertLines: { color: '#1f2937' }, horzLines: { color: '#1f2937' } },
      rightPriceScale: { borderColor: '#334155' },
      timeScale: { borderColor: '#334155' },
    });
    const closes = priceSeries
      .filter((point) => point.close_krw !== null)
      .map((point) => ({ time: point.date as Time, value: point.close_krw as number }));
    const closeSeries = chart.addSeries(LineSeries, { color: '#60a5fa', lineWidth: 2 });
    closeSeries.setData(closes);
    if (targetPriceKrw !== null && closes.length > 0) {
      const targetSeries = chart.addSeries(LineSeries, { color: '#fb7185', lineWidth: 1, lineStyle: LineStyle.Dashed });
      targetSeries.setData(closes.map((point) => ({ time: point.time, value: targetPriceKrw })));
    }
    chart.timeScale().fitContent();
    return () => chart.remove();
  }, [priceSeries, publicationDate, targetHitDate, targetPriceKrw]);

  if (priceSeries.length === 0) return <div className="empty chart-box">가격 데이터가 없어 차트를 만들 수 없습니다.</div>;
  return <div ref={ref} className="chart-box" aria-label="가격 경로와 목표가 라인" />;
}
