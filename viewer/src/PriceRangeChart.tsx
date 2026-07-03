import { useCallback, useId, useRef, useState } from "react";
import type { PriceBin, PriceExtents } from "./browseQuery";
import { clampPrice, roundPrice } from "./browseQuery";

function formatAxisPrice(value: number) {
  return new Intl.NumberFormat("en-CA", {
    style: "currency",
    currency: "CAD",
    maximumFractionDigits: 2,
  }).format(value);
}

interface PriceRangeChartProps {
  bins: PriceBin[];
  extents: PriceExtents;
  priceMin: number | null;
  priceMax: number | null;
  onChange: (next: { priceMin: number | null; priceMax: number | null }) => void;
}

const THUMB_R = 10;
const CHART_WIDTH = 320;
const CHART_HEIGHT = 88;
const PAD_X = 14;
const PAD_Y = 8;
const TRACK_LEFT = PAD_X + THUMB_R;
const TRACK_RIGHT = CHART_WIDTH - PAD_X - THUMB_R;

export function PriceRangeChart({
  bins,
  extents,
  priceMin,
  priceMax,
  onChange,
}: PriceRangeChartProps) {
  const labelId = useId();
  const trackRef = useRef<SVGSVGElement>(null);
  const [dragging, setDragging] = useState<"min" | "max" | null>(null);

  const { min, max } = extents;
  const span = max - min || 1;
  const effectiveMin = priceMin ?? min;
  const effectiveMax = priceMax ?? max;

  const maxCount = Math.max(1, ...bins.map((b) => b.count));
  const innerW = TRACK_RIGHT - TRACK_LEFT;
  const innerH = CHART_HEIGHT - PAD_Y * 2;

  const priceToX = useCallback(
    (price: number) => TRACK_LEFT + ((price - min) / span) * innerW,
    [innerW, min, span],
  );

  const xToPrice = useCallback(
    (x: number) => {
      const ratio = (x - TRACK_LEFT) / innerW;
      return clampPrice(min + ratio * span, min, max);
    },
    [innerW, min, max, span],
  );

  const minX = priceToX(effectiveMin);
  const maxX = priceToX(effectiveMax);

  function pointerPrice(clientX: number) {
    const svg = trackRef.current;
    if (!svg) return effectiveMin;
    const rect = svg.getBoundingClientRect();
    const x = ((clientX - rect.left) / rect.width) * CHART_WIDTH;
    return roundPrice(xToPrice(x), 0.01);
  }

  function onPointerDown(handle: "min" | "max") {
    return (e: React.PointerEvent) => {
      e.preventDefault();
      setDragging(handle);
      (e.target as Element).setPointerCapture(e.pointerId);
    };
  }

  function onPointerMove(e: React.PointerEvent) {
    if (!dragging) return;
    const price = pointerPrice(e.clientX);
    if (dragging === "min") {
      const nextMin = Math.min(price, effectiveMax);
      onChange({
        priceMin: nextMin <= min ? null : nextMin,
        priceMax,
      });
    } else {
      const nextMax = Math.max(price, effectiveMin);
      onChange({
        priceMin,
        priceMax: nextMax >= max ? null : nextMax,
      });
    }
  }

  function onPointerUp() {
    setDragging(null);
  }

  function onKeyDown(handle: "min" | "max") {
    return (e: React.KeyboardEvent) => {
      const step = e.shiftKey ? 1 : 0.25;
      let delta = 0;
      if (e.key === "ArrowLeft" || e.key === "ArrowDown") delta = -step;
      if (e.key === "ArrowRight" || e.key === "ArrowUp") delta = step;
      if (!delta) return;
      e.preventDefault();
      if (handle === "min") {
        const base = effectiveMin + delta;
        const nextMin = clampPrice(base, min, effectiveMax);
        onChange({
          priceMin: nextMin <= min ? null : roundPrice(nextMin),
          priceMax,
        });
      } else {
        const base = effectiveMax + delta;
        const nextMax = clampPrice(base, effectiveMin, max);
        onChange({
          priceMin,
          priceMax: nextMax >= max ? null : roundPrice(nextMax),
        });
      }
    };
  }

  if (extents.pricedCount === 0) {
    return <p className="price-range-empty">No priced products in current selection.</p>;
  }

  const barW = bins.length > 0 ? innerW / bins.length : innerW;

  return (
    <div className="price-range-chart">
      <p className="price-range-meta" id={labelId}>
        {extents.totalCount} products · {extents.pricedCount} with price
      </p>
      <svg
        ref={trackRef}
        className="price-range-svg"
        viewBox={`0 0 ${CHART_WIDTH} ${CHART_HEIGHT}`}
        role="img"
        aria-labelledby={labelId}
        onPointerMove={onPointerMove}
        onPointerUp={onPointerUp}
        onPointerCancel={onPointerUp}
      >
        {bins.map((bin, i) => {
          const barH = (bin.count / maxCount) * innerH;
          const x = TRACK_LEFT + i * barW;
          const y = PAD_Y + innerH - barH;
          const inRange = bin.to >= effectiveMin && bin.from <= effectiveMax;
          return (
            <rect
              key={`${bin.from}-${bin.to}`}
              x={x + 1}
              y={y}
              width={Math.max(1, barW - 2)}
              height={barH}
              className={inRange ? "price-range-bar price-range-bar--in" : "price-range-bar"}
              rx={1}
            />
          );
        })}
        <rect
          x={minX}
          y={PAD_Y}
          width={Math.max(0, maxX - minX)}
          height={innerH}
          className="price-range-selection"
          pointerEvents="none"
        />
        <circle
          cx={minX}
          cy={CHART_HEIGHT / 2}
          r={THUMB_R}
          className="price-range-thumb"
          tabIndex={0}
          role="slider"
          aria-label="Minimum price"
          aria-valuemin={min}
          aria-valuemax={effectiveMax}
          aria-valuenow={effectiveMin}
          onPointerDown={onPointerDown("min")}
          onKeyDown={onKeyDown("min")}
        />
        <circle
          cx={maxX}
          cy={CHART_HEIGHT / 2}
          r={THUMB_R}
          className="price-range-thumb"
          tabIndex={0}
          role="slider"
          aria-label="Maximum price"
          aria-valuemin={effectiveMin}
          aria-valuemax={max}
          aria-valuenow={effectiveMax}
          onPointerDown={onPointerDown("max")}
          onKeyDown={onKeyDown("max")}
        />
      </svg>
      <div className="price-range-axis">
        <span>{formatAxisPrice(effectiveMin)}</span>
        <span>{formatAxisPrice(effectiveMax)}</span>
      </div>
    </div>
  );
}
