import { useCallback, useId, useRef, useState } from "react";
import { formatPrice } from "@/shared/lib/formatPrice";
import type { PriceBin, PriceExtents } from "./browseQuery";
import { clampPrice, roundPrice } from "./browseQuery";
import "./PriceRangeChart.css";

interface PriceRangeChartProps {
  bins: PriceBin[];
  extents: PriceExtents;
  priceMin: number | null;
  priceMax: number | null;
  onChange: (next: { priceMin: number | null; priceMax: number | null }) => void;
}

type PriceDraft = { priceMin: number; priceMax: number };

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
  const draggingRef = useRef<"min" | "max" | null>(null);
  const draftRef = useRef<PriceDraft | null>(null);
  const [draft, setDraft] = useState<PriceDraft | null>(null);
  const [dragThumbX, setDragThumbX] = useState<{ handle: "min" | "max"; x: number } | null>(
    null,
  );

  const { min, max } = extents;
  const span = max - min || 1;
  const activeMin = draft !== null ? draft.priceMin : priceMin;
  const activeMax = draft !== null ? draft.priceMax : priceMax;
  const effectiveMin = activeMin ?? min;
  const effectiveMax = activeMax ?? max;

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

  const filterMinX = priceToX(effectiveMin);
  const filterMaxX = priceToX(effectiveMax);
  const minX = dragThumbX?.handle === "min" ? dragThumbX.x : filterMinX;
  const maxX = dragThumbX?.handle === "max" ? dragThumbX.x : filterMaxX;

  function pointerX(clientX: number) {
    const svg = trackRef.current;
    if (!svg) return TRACK_LEFT;
    const rect = svg.getBoundingClientRect();
    return ((clientX - rect.left) / rect.width) * CHART_WIDTH;
  }

  function onPointerDown(handle: "min" | "max") {
    return (e: React.PointerEvent) => {
      e.preventDefault();
      draggingRef.current = handle;
      const initial = { priceMin: priceMin ?? min, priceMax: priceMax ?? max };
      draftRef.current = initial;
      setDraft(initial);
      trackRef.current?.setPointerCapture(e.pointerId);
    };
  }

  function onPointerMove(e: React.PointerEvent) {
    if (!draggingRef.current) return;
    const handle = draggingRef.current;
    const rawX = pointerX(e.clientX);
    const clampedX = Math.max(TRACK_LEFT, Math.min(TRACK_RIGHT, rawX));
    const price = roundPrice(xToPrice(clampedX), 0.01);

    const base = draftRef.current ?? { priceMin: priceMin ?? min, priceMax: priceMax ?? max };
    const baseMin = base.priceMin;
    const baseMax = base.priceMax;

    let next: PriceDraft;
    let thumbX: number;
    if (handle === "min") {
      const nextMin = Math.min(price, baseMax);
      next = {
        priceMin: nextMin <= min ? min : nextMin,
        priceMax: base.priceMax,
      };
      thumbX = Math.min(clampedX, priceToX(baseMax));
    } else {
      const nextMax = Math.max(price, baseMin);
      next = {
        priceMin: base.priceMin,
        priceMax: nextMax >= max ? max : nextMax,
      };
      thumbX = Math.max(clampedX, priceToX(baseMin));
    }

    draftRef.current = next;
    setDraft(next);
    setDragThumbX({ handle, x: thumbX });
  }

  function onPointerUp() {
    if (draggingRef.current && draftRef.current) {
      const { priceMin: draftMin, priceMax: draftMax } = draftRef.current;
      onChange({
        priceMin: draftMin <= min ? null : roundPrice(draftMin),
        priceMax: draftMax >= max ? null : roundPrice(draftMax),
      });
    }
    draggingRef.current = null;
    draftRef.current = null;
    setDraft(null);
    setDragThumbX(null);
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
          priceMax: activeMax,
        });
      } else {
        const base = effectiveMax + delta;
        const nextMax = clampPrice(base, effectiveMin, max);
        onChange({
          priceMin: activeMin,
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
          x={filterMinX}
          y={PAD_Y}
          width={Math.max(0, filterMaxX - filterMinX)}
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
        <span>{formatPrice(effectiveMin)}</span>
        <span>{formatPrice(effectiveMax)}</span>
      </div>
    </div>
  );
}
