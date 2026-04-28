'use client';

import {
  CandlestickSeries,
  ColorType,
  CrosshairMode,
  HistogramSeries,
  LineStyle,
  createChart,
  createSeriesMarkers,
  type IChartApi,
  type ISeriesApi,
  type MouseEventParams,
  type SeriesMarker,
  type Time,
} from 'lightweight-charts';
import { useEffect, useMemo, useRef, useState } from 'react';
import { formatKrw, formatPercent } from '@/lib/format';

type PricePoint = {
  time: string;
  value: number;
  open?: number;
  high?: number;
  low?: number;
  close?: number;
  volume?: number | null;
};

type EvidenceMarker = {
  time: string;
  kind: 'publication' | 'target-hit' | 'peak' | 'trough';
  label: string;
  value?: number | null;
};

type TooltipState = {
  x: number;
  y: number;
  time: string;
  open: number;
  high: number;
  low: number;
  close: number;
  volume: number | null;
  targetPrice: number | null;
  targetGapPct: number | null;
};

type CandlePoint = { time: Time; open: number; high: number; low: number; close: number };
type VolumePoint = { time: Time; value: number; color: string };

type Props = {
  priceSeries: PricePoint[];
  targetPrice: number | null;
  publicationDate: string;
  targetHitDate: string | null;
  evidenceMarkers?: EvidenceMarker[];
};

export function PriceEvidenceChart({
  priceSeries,
  targetPrice,
  publicationDate,
  targetHitDate,
  evidenceMarkers = [],
}: Props) {
  const ref = useRef<HTMLDivElement | null>(null);
  const [tooltip, setTooltip] = useState<TooltipState | null>(null);
  const candleData = useMemo(() => priceSeries.map(toCandlePoint), [priceSeries]);
  const volumeData = useMemo(() => priceSeries.map(toVolumePoint), [priceSeries]);
  const priceByTime = useMemo(() => new Map(priceSeries.map((point) => [point.time, point])), [priceSeries]);
  const chartMarkers = useMemo(
    () => buildMarkers(publicationDate, targetHitDate, evidenceMarkers),
    [evidenceMarkers, publicationDate, targetHitDate],
  );

  useEffect(() => {
    if (!ref.current || priceSeries.length === 0) return;
    const container = ref.current;
    const chart: IChartApi = createChart(container, {
      autoSize: true,
      height: 420,
      layout: {
        background: { type: ColorType.Solid, color: '#0f172a' },
        textColor: '#cbd5e1',
        attributionLogo: true,
      },
      grid: { vertLines: { color: '#1f2937' }, horzLines: { color: '#1f2937' } },
      crosshair: { mode: CrosshairMode.Normal },
      rightPriceScale: { borderColor: '#334155', autoScale: true, scaleMargins: { top: 0.10, bottom: 0.22 } },
      timeScale: { borderColor: '#334155', timeVisible: true, secondsVisible: false },
    });

    const candleSeries: ISeriesApi<'Candlestick'> = chart.addSeries(CandlestickSeries, {
      upColor: '#35f2c2',
      downColor: '#ff6f91',
      borderUpColor: '#35f2c2',
      borderDownColor: '#ff6f91',
      wickUpColor: '#35f2c2',
      wickDownColor: '#ff6f91',
      priceLineVisible: false,
      lastValueVisible: true,
      title: 'OHLC',
    });

    candleSeries.setData(candleData);

    const volumeSeries = chart.addSeries(HistogramSeries, {
      color: 'rgba(138, 180, 255, 0.36)',
      priceFormat: { type: 'volume' },
      priceScaleId: 'volume',
      lastValueVisible: false,
      priceLineVisible: false,
      title: '거래량',
    });
    chart.priceScale('volume').applyOptions({ scaleMargins: { top: 0.82, bottom: 0 } });
    volumeSeries.setData(volumeData);

    if (targetPrice && Number.isFinite(targetPrice)) {
      candleSeries.createPriceLine({
        price: targetPrice,
        color: '#f87171',
        lineWidth: 2,
        lineStyle: LineStyle.Dashed,
        axisLabelVisible: true,
        title: '목표가',
      });
    }

    createSeriesMarkers(candleSeries, chartMarkers);

    const handleCrosshairMove = (params: MouseEventParams<Time>) => {
      if (!params.point || !params.time || params.point.x < 0 || params.point.y < 0) {
        setTooltip(null);
        return;
      }
      const time = String(params.time);
      const seriesData = params.seriesData.get(candleSeries);
      const fallback = priceByTime.get(time);
      const hoveredCandle = readCrosshairCandle(seriesData, fallback);
      if (!hoveredCandle) {
        setTooltip(null);
        return;
      }
      const { open, high, low, close } = hoveredCandle;
      const targetGapPct = targetPrice && Number.isFinite(targetPrice) ? (targetPrice - close) / close : null;
      setTooltip({
        x: Math.min(params.point.x + 16, Math.max(16, container.clientWidth - 240)),
        y: Math.max(12, params.point.y - 108),
        time,
        open,
        high,
        low,
        close,
        volume: fallback?.volume ?? null,
        targetPrice,
        targetGapPct,
      });
    };
    chart.subscribeCrosshairMove(handleCrosshairMove);
    chart.timeScale().fitContent();
    return () => {
      chart.unsubscribeCrosshairMove(handleCrosshairMove);
      chart.remove();
    };
  }, [candleData, chartMarkers, priceByTime, priceSeries.length, targetPrice, volumeData]);

  if (priceSeries.length === 0) {
    return <div className="panel chart-box">이 리포트 종목의 가격 경로를 찾을 수 없습니다.</div>;
  }
  return (
    <div className="chart-shell">
      <div ref={ref} className="chart-box chart-box-fixed" aria-label="목표가 기준선, OHLC 캔들, 거래량, 발간·목표도달·고점·저점 마커가 포함된 가격 경로" />
      {tooltip ? (
        <div className="chart-tooltip" style={{ left: tooltip.x, top: tooltip.y }}>
          <div className="tooltip-date">{tooltip.time}</div>
          <div>시가 {formatKrw(tooltip.open)} · 고가 {formatKrw(tooltip.high)}</div>
          <div>저가 {formatKrw(tooltip.low)} · 종가 {formatKrw(tooltip.close)}</div>
          <div>거래량 {formatVolume(tooltip.volume)}</div>
          <div>목표가 {formatKrw(tooltip.targetPrice)}</div>
          <div className={tooltip.targetGapPct !== null && tooltip.targetGapPct <= 0 ? 'good' : 'warn'}>
            목표까지 {formatPercent(tooltip.targetGapPct)}
          </div>
        </div>
      ) : null}
    </div>
  );
}

type MarkerStyle = { color: string; position: 'aboveBar' | 'belowBar'; shape: 'arrowUp' | 'arrowDown' | 'circle' };

function toCandlePoint(point: PricePoint): CandlePoint {
  const close = point.close ?? point.value;
  return {
    time: point.time as Time,
    open: point.open ?? close,
    high: point.high ?? close,
    low: point.low ?? close,
    close,
  };
}

function toVolumePoint(point: PricePoint): VolumePoint {
  const close = point.close ?? point.value;
  const open = point.open ?? close;
  return {
    time: point.time as Time,
    value: Math.max(0, point.volume ?? 0),
    color: close >= open ? 'rgba(53, 242, 194, 0.34)' : 'rgba(255, 111, 145, 0.32)',
  };
}

function buildMarkers(publicationDate: string, targetHitDate: string | null, evidenceMarkers: EvidenceMarker[]): SeriesMarker<Time>[] {
  const markerByKey = new Map<string, SeriesMarker<Time>>();
  const addMarker = (marker: SeriesMarker<Time>) => markerByKey.set(`${String(marker.time)}-${marker.text}`, marker);
  addMarker({ time: publicationDate as Time, position: 'belowBar', color: '#fbbf24', shape: 'arrowUp', text: '발간' });
  if (targetHitDate) {
    addMarker({ time: targetHitDate as Time, position: 'aboveBar', color: '#34d399', shape: 'circle', text: '목표 도달' });
  }
  for (const marker of evidenceMarkers) {
    const markerConfig = markerStyle(marker);
    addMarker({
      time: marker.time as Time,
      position: markerConfig.position,
      color: markerConfig.color,
      shape: markerConfig.shape,
      text: marker.label,
    });
  }
  return [...markerByKey.values()].sort((a, b) => String(a.time).localeCompare(String(b.time)));
}

function readCrosshairCandle(seriesData: unknown, fallback: PricePoint | undefined): Omit<CandlePoint, 'time'> | null {
  const closeRaw = isObjectWithNumber(seriesData, 'close') ? Number(seriesData.close) : (fallback?.close ?? fallback?.value);
  const openRaw = isObjectWithNumber(seriesData, 'open') ? Number(seriesData.open) : (fallback?.open ?? closeRaw);
  const highRaw = isObjectWithNumber(seriesData, 'high') ? Number(seriesData.high) : (fallback?.high ?? closeRaw);
  const lowRaw = isObjectWithNumber(seriesData, 'low') ? Number(seriesData.low) : (fallback?.low ?? closeRaw);
  if (closeRaw === undefined || openRaw === undefined || highRaw === undefined || lowRaw === undefined) return null;
  if (!Number.isFinite(closeRaw) || !Number.isFinite(openRaw) || !Number.isFinite(highRaw) || !Number.isFinite(lowRaw)) return null;
  return { open: openRaw, high: highRaw, low: lowRaw, close: closeRaw };
}

function isObjectWithNumber(value: unknown, key: 'open' | 'high' | 'low' | 'close'): value is Record<typeof key, number> {
  return typeof value === 'object' && value !== null && key in value && Number.isFinite(Number((value as Record<typeof key, unknown>)[key]));
}

function markerStyle(marker: EvidenceMarker): MarkerStyle {
  switch (marker.kind) {
    case 'target-hit':
      return { color: '#34d399', position: 'aboveBar', shape: 'circle' };
    case 'peak':
      return { color: '#22d3ee', position: 'aboveBar', shape: 'arrowDown' };
    case 'trough':
      return { color: '#fb7185', position: 'belowBar', shape: 'arrowUp' };
    case 'publication':
    default:
      return { color: '#fbbf24', position: 'belowBar', shape: 'arrowUp' };
  }
}

function formatVolume(value: number | null): string {
  if (value === null || !Number.isFinite(value)) return '—';
  return value.toLocaleString('ko-KR', { maximumFractionDigits: 0 });
}
