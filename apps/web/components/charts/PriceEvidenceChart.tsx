'use client';

import {
  ColorType,
  CrosshairMode,
  LineSeries,
  LineStyle,
  createChart,
  createSeriesMarkers,
  type IChartApi,
  type ISeriesApi,
  type MouseEventParams,
  type SeriesMarker,
  type Time,
} from 'lightweight-charts';
import { useEffect, useRef, useState } from 'react';
import { formatKrw, formatPercent } from '@/lib/format';

type PricePoint = { time: string; value: number };

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
  close: number;
  targetPrice: number | null;
  targetGapPct: number | null;
};

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

  useEffect(() => {
    if (!ref.current || priceSeries.length === 0) return;
    const container = ref.current;
    const chart: IChartApi = createChart(container, {
      autoSize: true,
      height: 420,
      layout: {
        background: { type: ColorType.Solid, color: '#0f172a' },
        textColor: '#cbd5e1',
        attributionLogo: false,
      },
      grid: { vertLines: { color: '#1f2937' }, horzLines: { color: '#1f2937' } },
      crosshair: { mode: CrosshairMode.Normal },
      rightPriceScale: { borderColor: '#334155' },
      timeScale: { borderColor: '#334155', timeVisible: true },
    });
    const closeSeries: ISeriesApi<'Line'> = chart.addSeries(LineSeries, {
      color: '#60a5fa',
      lineWidth: 2,
      priceLineVisible: false,
      lastValueVisible: true,
      title: '종가',
    });
    closeSeries.setData(priceSeries.map((point) => ({ time: point.time as Time, value: point.value })));

    if (targetPrice && Number.isFinite(targetPrice)) {
      closeSeries.createPriceLine({
        price: targetPrice,
        color: '#f87171',
        lineWidth: 2,
        lineStyle: LineStyle.Dashed,
        axisLabelVisible: true,
        title: '목표가',
      });
    }

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
    createSeriesMarkers(closeSeries, [...markerByKey.values()].sort((a, b) => String(a.time).localeCompare(String(b.time))));

    const priceByTime = new Map(priceSeries.map((point) => [point.time, point.value]));
    const handleCrosshairMove = (params: MouseEventParams<Time>) => {
      if (!params.point || !params.time || params.point.x < 0 || params.point.y < 0) {
        setTooltip(null);
        return;
      }
      const time = String(params.time);
      const seriesData = params.seriesData.get(closeSeries);
      const close = typeof seriesData === 'object' && seriesData && 'value' in seriesData
        ? Number(seriesData.value)
        : priceByTime.get(time);
      if (close === undefined || !Number.isFinite(close)) {
        setTooltip(null);
        return;
      }
      const targetGapPct = targetPrice && Number.isFinite(targetPrice) ? (targetPrice - close) / close : null;
      setTooltip({
        x: Math.min(params.point.x + 16, Math.max(16, container.clientWidth - 190)),
        y: Math.max(12, params.point.y - 86),
        time,
        close,
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
  }, [evidenceMarkers, priceSeries, publicationDate, targetHitDate, targetPrice]);

  if (priceSeries.length === 0) {
    return <div className="panel chart-box">이 리포트 종목의 가격 경로를 찾을 수 없습니다.</div>;
  }
  return (
    <div className="chart-shell">
      <div ref={ref} className="chart-box" aria-label="목표가 기준선과 발간·목표도달·고점·저점 마커가 포함된 종가 경로" />
      {tooltip ? (
        <div className="chart-tooltip" style={{ left: tooltip.x, top: tooltip.y }}>
          <div className="tooltip-date">{tooltip.time}</div>
          <div>종가 {formatKrw(tooltip.close)}</div>
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
