'use client';

import { useCallback, useEffect, useRef, useState } from 'react';
import { useTheme } from 'next-themes';
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

/**
 * Phase 6a — palette is read from CSS variables on the document root so
 * a theme change never has to rebuild the chart. ``readPalette()`` runs
 * inside a ``useEffect`` keyed on the resolved theme and pushes the new
 * options through ``applyOptions`` (chart instance + series instances).
 *
 * Falls back to hard-coded light tokens when running outside the browser
 * (SSR pass) so ``baseOptions()`` stays pure-function for unit tests.
 */
type ChartPalette = {
  background: string;
  text: string;
  grid: string;
  border: string;
  candleUp: string;
  candleDown: string;
  ma50: string;
  ma150: string;
  ma200: string;
  areaTop: string;
  areaBottom: string;
  baselineTopLine: string;
  baselineTopFill1: string;
  baselineTopFill2: string;
  baselineBottomLine: string;
  baselineBottomFill1: string;
  baselineBottomFill2: string;
};

const FALLBACK_PALETTE: ChartPalette = {
  background: '#fbfcfd',
  text: '#334155',
  grid: '#eef2f7',
  border: '#d5dee8',
  candleUp: '#047857',
  candleDown: '#b91c1c',
  ma50: '#2454a6',
  ma150: '#7c3aed',
  ma200: '#475569',
  areaTop: 'rgba(36, 84, 166, 0.28)',
  areaBottom: 'rgba(36, 84, 166, 0.02)',
  baselineTopLine: '#047857',
  baselineTopFill1: 'rgba(4, 120, 87, 0.18)',
  baselineTopFill2: 'rgba(4, 120, 87, 0.02)',
  baselineBottomLine: '#b91c1c',
  baselineBottomFill1: 'rgba(185, 28, 28, 0.18)',
  baselineBottomFill2: 'rgba(185, 28, 28, 0.02)',
};

function readPalette(): ChartPalette {
  if (typeof window === 'undefined' || typeof document === 'undefined') return FALLBACK_PALETTE;
  const root = document.documentElement;
  const get = (name: string, fallback: string) => {
    const value = getComputedStyle(root).getPropertyValue(name).trim();
    return value || fallback;
  };
  return {
    background: get('--chart-bg', FALLBACK_PALETTE.background),
    text: get('--chart-text', FALLBACK_PALETTE.text),
    grid: get('--chart-grid', FALLBACK_PALETTE.grid),
    border: get('--chart-border', FALLBACK_PALETTE.border),
    candleUp: get('--chart-line-up', FALLBACK_PALETTE.candleUp),
    candleDown: get('--chart-line-down', FALLBACK_PALETTE.candleDown),
    ma50: get('--chart-ma-50', FALLBACK_PALETTE.ma50),
    ma150: get('--chart-ma-150', FALLBACK_PALETTE.ma150),
    ma200: get('--chart-ma-200', FALLBACK_PALETTE.ma200),
    areaTop: get('--chart-area-top', FALLBACK_PALETTE.areaTop),
    areaBottom: get('--chart-area-bottom', FALLBACK_PALETTE.areaBottom),
    baselineTopLine: get('--chart-baseline-top-line', FALLBACK_PALETTE.baselineTopLine),
    baselineTopFill1: get('--chart-baseline-top-fill1', FALLBACK_PALETTE.baselineTopFill1),
    baselineTopFill2: get('--chart-baseline-top-fill2', FALLBACK_PALETTE.baselineTopFill2),
    baselineBottomLine: get('--chart-baseline-bottom-line', FALLBACK_PALETTE.baselineBottomLine),
    baselineBottomFill1: get('--chart-baseline-bottom-fill1', FALLBACK_PALETTE.baselineBottomFill1),
    baselineBottomFill2: get('--chart-baseline-bottom-fill2', FALLBACK_PALETTE.baselineBottomFill2),
  };
}

/**
 * Phase 7 — currency-aware price formatter. KRW & JPY render with 0 decimals,
 * USD / GBP / EUR with 2, anything else with 2 by default. The chart applies
 * this through ``localization.priceFormatter`` and the legacy ko-KR locale
 * stays the integer rendering for KRW so existing screenshots match.
 */
function priceFormatterFor(currency: string | undefined) {
  const code = (currency ?? 'KRW').toUpperCase();
  const decimals = code === 'KRW' || code === 'JPY' ? 0 : 2;
  const locale = code === 'KRW' ? 'ko-KR' : 'en-US';
  return (price: number) =>
    new Intl.NumberFormat(locale, {
      minimumFractionDigits: decimals,
      maximumFractionDigits: decimals,
    }).format(price);
}

function chartOptionsFromPalette(palette: ChartPalette, currency?: string) {
  return {
    layout: {
      background: { type: ColorType.Solid, color: palette.background },
      textColor: palette.text,
      fontFamily: '"Pretendard Variable", Pretendard, -apple-system, BlinkMacSystemFont, system-ui, sans-serif',
    },
    grid: {
      vertLines: { color: palette.grid },
      horzLines: { color: palette.grid },
    },
    rightPriceScale: {
      borderColor: palette.border,
      minimumWidth: 92,
    },
    timeScale: {
      borderColor: palette.border,
      timeVisible: false,
    },
    crosshair: { mode: 1 },
    localization: {
      priceFormatter: priceFormatterFor(currency),
    },
  };
}

const RANGE_PRESETS: { id: string; label: string; bars: number | null }[] = [
  { id: '1M', label: '1M', bars: 21 },
  { id: '3M', label: '3M', bars: 63 },
  { id: '6M', label: '6M', bars: 126 },
  { id: '1Y', label: '1Y', bars: 252 },
  { id: 'ALL', label: 'ALL', bars: null },
];

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
  const chartRef = useRef<IChartApi | null>(null);
  const candlesRef = useRef<ISeriesApi<'Candlestick'> | null>(null);
  const lineSeriesRef = useRef<{ ma50?: ISeriesApi<'Line'>; ma150?: ISeriesApi<'Line'>; ma200?: ISeriesApi<'Line'> }>({});
  const { resolvedTheme } = useTheme();
  const [activeRange, setActiveRange] = useState<string>('6M');

  // Phase 7 — read display currency from the per-symbol payload so KRW
  // renders without decimals and USD/EUR/etc keep two-decimal precision.
  const currency = data?.meta?.display_currency;
  const priceDecimals = currency && /^(usd|eur|gbp)$/i.test(currency) ? 2 : 0;

  const applyRange = useCallback((id: string) => {
    setActiveRange(id);
    const chart = chartRef.current;
    if (!chart || !data) return;
    const preset = RANGE_PRESETS.find((p) => p.id === id) ?? RANGE_PRESETS[2];
    const length = data.ohlc.length;
    if (preset.bars === null || length <= preset.bars) {
      chart.timeScale().fitContent();
      return;
    }
    chart.timeScale().setVisibleLogicalRange({
      from: Math.max(0, length - preset.bars),
      to: length + 5,
    });
  }, [data]);

  // Chart life-cycle effect — runs only when data / runId changes.
  // CRITICAL Phase 6a AC #2: a theme flip MUST NOT recreate the chart;
  // ``resolvedTheme`` is intentionally NOT in the dep array.
  useEffect(() => {
    if (!ref.current || !data || data.ohlc.length === 0) return;
    ref.current.innerHTML = '';
    ref.current.style.position = 'relative';
    const palette = readPalette();
    const chart = createChart(ref.current, { ...chartOptionsFromPalette(palette, currency), height: 360 });
    chartRef.current = chart;
    const candles = chart.addSeries(CandlestickSeries, {
      upColor: palette.candleUp,
      downColor: palette.candleDown,
      borderVisible: false,
      wickUpColor: palette.candleUp,
      wickDownColor: palette.candleDown,
      priceFormat: { type: 'price', precision: priceDecimals, minMove: priceDecimals === 0 ? 1 : 0.01 },
    });
    candlesRef.current = candles;
    candles.setData(data.ohlc);
    lineSeriesRef.current.ma50 = addLine(chart, data.ma50, palette.ma50, 2, priceDecimals);
    lineSeriesRef.current.ma150 = addLine(chart, data.ma150, palette.ma150, 1, priceDecimals);
    lineSeriesRef.current.ma200 = addLine(chart, data.ma200, palette.ma200, 1, priceDecimals);
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
      color: String(marker.color ?? palette.text),
      shape: marker.shape as 'circle' | 'square' | 'arrowUp' | 'arrowDown',
      text: String(marker.text ?? ''),
    }));
    if (markers.length) createSeriesMarkers(candles, markers);
    const tooltip = document.createElement('div');
    tooltip.className = 'chart-tooltip';
    tooltip.style.display = 'none';
    ref.current.appendChild(tooltip);
    const closeByTime = new Map(data.ohlc.map((item) => [item.time, item.close]));
    const reports = data.report_markers
      .map((marker) => ({
        time: String(marker.time ?? ''),
        price: Number(marker.publication_price ?? marker.target_price ?? 0),
      }))
      .filter((marker) => marker.time && Number.isFinite(marker.price) && marker.price > 0)
      .sort((a, b) => a.time.localeCompare(b.time));
    chart.subscribeCrosshairMove((param) => {
      const time = typeof param.time === 'string' ? param.time : '';
      const point = param.point;
      if (!time || !point || point.x < 0 || point.y < 0) {
        tooltip.style.display = 'none';
        return;
      }
      const close = closeByTime.get(time);
      if (!close) {
        tooltip.style.display = 'none';
        return;
      }
      const matchingReports = reports.filter((report) => report.time <= time);
      const baseReport = matchingReports.length ? matchingReports[matchingReports.length - 1] : undefined;
      const reportReturn = baseReport ? close / baseReport.price - 1 : null;
      tooltip.innerHTML = `<b>${time}</b><span>${Math.round(close).toLocaleString('ko-KR')}</span><span>발간후 ${formatTooltipPct(reportReturn)}</span>`;
      tooltip.style.display = 'grid';
      tooltip.style.left = `${Math.min(point.x + 14, ref.current!.clientWidth - 158)}px`;
      tooltip.style.top = `${Math.max(8, point.y - 48)}px`;
    });
    focusRecentBars(chart, data.ohlc.length, 150);
    const cleanupResize = attachResize(chart, ref.current, () => focusRecentBars(chart, data.ohlc.length, 150));
    return () => {
      cleanupResize();
      chart.remove();
      chartRef.current = null;
      candlesRef.current = null;
      lineSeriesRef.current = {};
    };
  }, [data, runId]);

  // Theme application effect — runs on every theme flip without
  // touching the chart instance pointer (AC #2).
  useEffect(() => {
    const chart = chartRef.current;
    if (!chart) return;
    const palette = readPalette();
    chart.applyOptions(chartOptionsFromPalette(palette, currency));
    candlesRef.current?.applyOptions({
      upColor: palette.candleUp,
      downColor: palette.candleDown,
      wickUpColor: palette.candleUp,
      wickDownColor: palette.candleDown,
    });
    lineSeriesRef.current.ma50?.applyOptions({ color: palette.ma50 });
    lineSeriesRef.current.ma150?.applyOptions({ color: palette.ma150 });
    lineSeriesRef.current.ma200?.applyOptions({ color: palette.ma200 });
  }, [resolvedTheme, currency]);

  return (
    <div className="stock-chart-shell">
      <div className="chart-toolbar" role="toolbar" aria-label="기간 프리셋">
        {RANGE_PRESETS.map((preset) => (
          <button
            key={preset.id}
            type="button"
            className={preset.id === activeRange ? 'range-button active' : 'range-button'}
            onClick={() => applyRange(preset.id)}
          >
            {preset.label}
          </button>
        ))}
        {currency ? <span className="chart-currency">{currency.toUpperCase()}</span> : null}
      </div>
      <div ref={ref} className="chart-surface" aria-label="종목 가격 차트" />
    </div>
  );
}

export function EquityChart({ rows }: { rows: EquityRow[] }) {
  return <SingleSeriesChart rows={rows.map((row) => ({ time: row.date, value: row.equity }))} mode="area" />;
}

export function DrawdownChart({ rows }: { rows: EquityRow[] }) {
  let peak = 1;
  const drawdown = rows.map((row) => {
    peak = Math.max(peak, row.equity || 1);
    return { time: row.date, value: row.equity / peak - 1 };
  });
  return <SingleSeriesChart rows={drawdown} mode="baseline" />;
}

function SingleSeriesChart({ rows, mode }: { rows: SeriesPoint[]; mode: 'area' | 'baseline' }) {
  const ref = useRef<HTMLDivElement | null>(null);
  const chartRef = useRef<IChartApi | null>(null);
  const seriesRef = useRef<ISeriesApi<'Area'> | ISeriesApi<'Baseline'> | null>(null);
  const { resolvedTheme } = useTheme();

  useEffect(() => {
    if (!ref.current || rows.length === 0) return;
    ref.current.innerHTML = '';
    const palette = readPalette();
    const chart = createChart(ref.current, { ...chartOptionsFromPalette(palette), height: 250 });
    chartRef.current = chart;
    let series: ISeriesApi<'Area'> | ISeriesApi<'Baseline'>;
    if (mode === 'area') {
      series = chart.addSeries(AreaSeries, {
        lineColor: palette.ma50,
        topColor: palette.areaTop,
        bottomColor: palette.areaBottom,
      });
    } else {
      series = chart.addSeries(BaselineSeries, {
        baseValue: { type: 'price', price: 0 },
        topLineColor: palette.baselineTopLine,
        topFillColor1: palette.baselineTopFill1,
        topFillColor2: palette.baselineTopFill2,
        bottomLineColor: palette.baselineBottomLine,
        bottomFillColor1: palette.baselineBottomFill1,
        bottomFillColor2: palette.baselineBottomFill2,
      });
    }
    seriesRef.current = series;
    series.setData(rows);
    chart.timeScale().fitContent();
    const cleanupResize = attachResize(chart, ref.current);
    return () => {
      cleanupResize();
      chart.remove();
      chartRef.current = null;
      seriesRef.current = null;
    };
  }, [rows, mode]);

  useEffect(() => {
    const chart = chartRef.current;
    if (!chart) return;
    const palette = readPalette();
    chart.applyOptions(chartOptionsFromPalette(palette));
    if (mode === 'area' && seriesRef.current) {
      (seriesRef.current as ISeriesApi<'Area'>).applyOptions({
        lineColor: palette.ma50,
        topColor: palette.areaTop,
        bottomColor: palette.areaBottom,
      });
    } else if (mode === 'baseline' && seriesRef.current) {
      (seriesRef.current as ISeriesApi<'Baseline'>).applyOptions({
        topLineColor: palette.baselineTopLine,
        topFillColor1: palette.baselineTopFill1,
        topFillColor2: palette.baselineTopFill2,
        bottomLineColor: palette.baselineBottomLine,
        bottomFillColor1: palette.baselineBottomFill1,
        bottomFillColor2: palette.baselineBottomFill2,
      });
    }
  }, [resolvedTheme, mode]);

  return <div ref={ref} className="chart-surface compact" />;
}

function addLine(
  chart: IChartApi,
  rows: SeriesPoint[],
  color: string,
  lineWidth: 1 | 2,
  precision: number = 0,
): ISeriesApi<'Line'> | undefined {
  if (!rows.length) return undefined;
  const series = chart.addSeries(LineSeries, {
    color,
    lineWidth,
    priceFormat: { type: 'price', precision, minMove: precision === 0 ? 1 : 0.01 },
  });
  series.setData(rows);
  return series;
}

function formatTooltipPct(value: number | null) {
  if (value === null || Number.isNaN(value)) return '-';
  return `${(value * 100).toFixed(1)}%`;
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
