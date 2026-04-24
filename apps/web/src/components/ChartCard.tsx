'use client';

import { useEffect, useRef } from 'react';
import {
  AreaSeries,
  BaselineSeries,
  CandlestickSeries,
  ColorType,
  createChart,
  createSeriesMarkers,
  LineSeries,
  LineStyle,
  type IChartApi,
  type ISeriesApi,
  type Time,
} from 'lightweight-charts';
import type { EquityRow, StockChartData } from '../lib/data';

type SeriesPoint = { time: string; value: number };

function baseOptions() {
  return {
    layout: {
      background: { type: ColorType.Solid, color: '#fbfcfd' },
      textColor: '#334155',
      fontFamily: '"Pretendard Variable", Pretendard, -apple-system, BlinkMacSystemFont, system-ui, sans-serif',
    },
    grid: {
      vertLines: { color: '#eef2f7' },
      horzLines: { color: '#eef2f7' },
    },
    rightPriceScale: {
      borderColor: '#d5dee8',
    },
    timeScale: {
      borderColor: '#d5dee8',
      timeVisible: false,
    },
    crosshair: {
      mode: 1,
    },
  };
}

function attachResize(chart: IChartApi, element: HTMLDivElement, afterResize?: () => void) {
  const observer = new ResizeObserver(([entry]) => {
    const width = Math.max(320, Math.floor(entry.contentRect.width));
    chart.applyOptions({ width });
    if (afterResize) afterResize();
    else chart.timeScale().fitContent();
  });
  observer.observe(element);
  return () => observer.disconnect();
}

export function StockChart({ data, runId }: { data: StockChartData | null; runId: string }) {
  const ref = useRef<HTMLDivElement | null>(null);

  useEffect(() => {
    if (!ref.current || !data || data.ohlc.length === 0) return;
    ref.current.innerHTML = '';
    const chart = createChart(ref.current, { ...baseOptions(), height: 360 });
    const candles = chart.addSeries(CandlestickSeries, {
      upColor: '#047857',
      downColor: '#b91c1c',
      borderVisible: false,
      wickUpColor: '#047857',
      wickDownColor: '#b91c1c',
    });
    candles.setData(data.ohlc);
    addLine(chart, data.ma50, '#2454a6', 2);
    addLine(chart, data.ma150, '#7c3aed', 1);
    addLine(chart, data.ma200, '#475569', 1);
    for (const line of data.price_lines) {
      candles.createPriceLine({
        price: line.price,
        color: line.color,
        lineWidth: 1,
        lineStyle: LineStyle.Dashed,
        axisLabelVisible: true,
        title: line.title,
      });
    }
    const markers = [
      ...data.report_markers,
      ...data.trade_markers.filter((marker) => !marker.run_id || marker.run_id === runId),
    ].map((marker) => ({
      time: marker.time as Time,
      position: marker.position as 'aboveBar' | 'belowBar' | 'inBar',
      color: String(marker.color ?? '#334155'),
      shape: marker.shape as 'circle' | 'square' | 'arrowUp' | 'arrowDown',
      text: String(marker.text ?? ''),
    }));
    if (markers.length) createSeriesMarkers(candles, markers);
    focusRecentBars(chart, data.ohlc.length, 150);
    const cleanupResize = attachResize(chart, ref.current, () => focusRecentBars(chart, data.ohlc.length, 150));
    return () => {
      cleanupResize();
      chart.remove();
    };
  }, [data, runId]);

  return <div ref={ref} className="chart-surface" aria-label="종목 가격 차트" />;
}

export function EquityChart({ rows }: { rows: EquityRow[] }) {
  return <SingleSeriesChart rows={rows.map((row) => ({ time: row.date, value: row.equity }))} color="#2454a6" mode="area" />;
}

export function DrawdownChart({ rows }: { rows: EquityRow[] }) {
  let peak = 1;
  const drawdown = rows.map((row) => {
    peak = Math.max(peak, row.equity || 1);
    return { time: row.date, value: row.equity / peak - 1 };
  });
  return <SingleSeriesChart rows={drawdown} color="#b91c1c" mode="baseline" />;
}

function SingleSeriesChart({ rows, color, mode }: { rows: SeriesPoint[]; color: string; mode: 'area' | 'baseline' }) {
  const ref = useRef<HTMLDivElement | null>(null);
  useEffect(() => {
    if (!ref.current || rows.length === 0) return;
    ref.current.innerHTML = '';
    const chart = createChart(ref.current, { ...baseOptions(), height: 250 });
    let series: ISeriesApi<'Area'> | ISeriesApi<'Baseline'>;
    if (mode === 'area') {
      series = chart.addSeries(AreaSeries, {
        lineColor: color,
        topColor: 'rgba(36, 84, 166, 0.28)',
        bottomColor: 'rgba(36, 84, 166, 0.02)',
      });
    } else {
      series = chart.addSeries(BaselineSeries, {
        baseValue: { type: 'price', price: 0 },
        topLineColor: '#047857',
        topFillColor1: 'rgba(4, 120, 87, 0.18)',
        topFillColor2: 'rgba(4, 120, 87, 0.02)',
        bottomLineColor: color,
        bottomFillColor1: 'rgba(185, 28, 28, 0.18)',
        bottomFillColor2: 'rgba(185, 28, 28, 0.02)',
      });
    }
    series.setData(rows);
    chart.timeScale().fitContent();
    const cleanupResize = attachResize(chart, ref.current);
    return () => {
      cleanupResize();
      chart.remove();
    };
  }, [rows, color, mode]);

  return <div ref={ref} className="chart-surface compact" />;
}

function addLine(chart: IChartApi, rows: SeriesPoint[], color: string, lineWidth: 1 | 2) {
  if (!rows.length) return;
  const series = chart.addSeries(LineSeries, { color, lineWidth });
  series.setData(rows);
}

function focusRecentBars(chart: IChartApi, length: number, visibleBars: number) {
  if (length <= visibleBars) {
    chart.timeScale().fitContent();
    return;
  }
  chart.timeScale().setVisibleLogicalRange({
    from: Math.max(0, length - visibleBars),
    to: length + 5,
  });
}
