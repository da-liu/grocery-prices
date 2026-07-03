import { useCallback, useId, useRef, useState } from "react";
import {
  clampDateISO,
  dateToMs,
  msToISODate,
  type DateBin,
  type DateExtents,
} from "./browseQuery";

function formatAxisDate(iso: string) {
  const [year, month, day] = iso.split("-").map(Number);
  const date = new Date(year, month - 1, day);
  return date.toLocaleDateString("en-CA", { month: "short", day: "numeric" });
}

interface CapturedDateRangeChartProps {
  bins: DateBin[];
  extents: DateExtents;
  capturedAfter: string | null;
  capturedBefore: string | null;
  onChange: (next: { capturedAfter: string | null; capturedBefore: string | null }) => void;
}

const THUMB_R = 10;
const CHART_WIDTH = 320;
const CHART_HEIGHT = 88;
const PAD_X = 14;
const PAD_Y = 8;
const TRACK_LEFT = PAD_X + THUMB_R;
const TRACK_RIGHT = CHART_WIDTH - PAD_X - THUMB_R;

const MS_PER_DAY = 86400000;

export function CapturedDateRangeChart({
  bins,
  extents,
  capturedAfter,
  capturedBefore,
  onChange,
}: CapturedDateRangeChartProps) {
  const labelId = useId();
  const trackRef = useRef<SVGSVGElement>(null);
  const draggingRef = useRef<"min" | "max" | null>(null);
  const [, setDragging] = useState<"min" | "max" | null>(null);

  const { min, max } = extents;
  const singleDay = min === max;
  const span = Math.max(dateToMs(max) - dateToMs(min), MS_PER_DAY);
  const effectiveAfter = capturedAfter ?? min;
  const effectiveBefore = capturedBefore ?? max;
  const thumbAfter = clampDateISO(effectiveAfter, min, max);
  const thumbBefore = clampDateISO(effectiveBefore, min, max);

  const maxCount = Math.max(1, ...bins.map((bin) => bin.count));
  const innerW = TRACK_RIGHT - TRACK_LEFT;
  const innerH = CHART_HEIGHT - PAD_Y * 2;
  const calendarDays = singleDay ? 1 : Math.floor(span / MS_PER_DAY) + 1;
  const dayWidth = innerW / calendarDays;

  const dateToX = useCallback(
    (iso: string) => {
      if (singleDay) return TRACK_LEFT;
      return TRACK_LEFT + ((dateToMs(iso) - dateToMs(min)) / span) * innerW;
    },
    [innerW, min, singleDay, span],
  );

  const xToDate = useCallback(
    (x: number) => {
      if (singleDay) return min;
      const ratio = (x - TRACK_LEFT) / innerW;
      const ms = dateToMs(min) + ratio * span;
      return msToISODate(ms);
    },
    [innerW, min, singleDay, span],
  );

  const minX = singleDay ? TRACK_LEFT : dateToX(thumbAfter);
  const maxX = singleDay ? TRACK_RIGHT : dateToX(thumbBefore);

  function pointerDate(clientX: number) {
    const svg = trackRef.current;
    if (!svg) return effectiveAfter;
    const rect = svg.getBoundingClientRect();
    const x = ((clientX - rect.left) / rect.width) * CHART_WIDTH;
    return clampDateISO(xToDate(x), min, max);
  }

  function onPointerDown(handle: "min" | "max") {
    return (e: React.PointerEvent) => {
      e.preventDefault();
      draggingRef.current = handle;
      setDragging(handle);
      (e.currentTarget as Element).setPointerCapture(e.pointerId);
    };
  }

  function commitAfter(next: string) {
    if (dateToMs(next) <= dateToMs(min)) return null;
    if (dateToMs(next) > dateToMs(max)) return max;
    return next;
  }

  function commitBefore(next: string) {
    if (dateToMs(next) >= dateToMs(max)) return null;
    if (dateToMs(next) < dateToMs(min)) return null;
    return next;
  }

  function onPointerMove(e: React.PointerEvent) {
    const dragging = draggingRef.current;
    if (!dragging) return;
    const date = pointerDate(e.clientX);
    if (dragging === "min") {
      const nextAfter = date <= effectiveBefore ? date : effectiveBefore;
      onChange({
        capturedAfter: commitAfter(nextAfter),
        capturedBefore,
      });
    } else {
      const nextBefore = date >= effectiveAfter ? date : effectiveAfter;
      onChange({
        capturedAfter,
        capturedBefore: commitBefore(nextBefore),
      });
    }
  }

  function onPointerUp() {
    draggingRef.current = null;
    setDragging(null);
  }

  function shiftDate(iso: string, days: number): string {
    const date = new Date(dateToMs(iso));
    date.setDate(date.getDate() + days);
    return msToISODate(date.getTime());
  }

  function onKeyDown(handle: "min" | "max") {
    return (e: React.KeyboardEvent) => {
      const stepDays = e.shiftKey ? 7 : 1;
      let delta = 0;
      if (e.key === "ArrowLeft" || e.key === "ArrowDown") delta = -stepDays;
      if (e.key === "ArrowRight" || e.key === "ArrowUp") delta = stepDays;
      if (!delta) return;
      e.preventDefault();
      if (handle === "min") {
        const nextAfter = clampDateISO(
          shiftDate(effectiveAfter, delta),
          min,
          effectiveBefore,
        );
        onChange({
          capturedAfter: commitAfter(nextAfter),
          capturedBefore,
        });
      } else {
        const nextBefore = clampDateISO(
          shiftDate(effectiveBefore, delta),
          effectiveAfter,
          max,
        );
        onChange({
          capturedAfter,
          capturedBefore: commitBefore(nextBefore),
        });
      }
    };
  }

  const barSlotWidth = (bin: DateBin) => {
    if (bin.from === bin.to) return dayWidth;
    const spanDays = Math.floor((dateToMs(bin.to) - dateToMs(bin.from)) / MS_PER_DAY) + 1;
    return spanDays * dayWidth;
  };

  return (
    <div className="price-range-chart">
      <p className="price-range-meta" id={labelId}>
        {extents.datedPhotoCount} photos with dates · drag handles to filter
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
        {bins.map((bin) => {
          const barH = (bin.count / maxCount) * innerH;
          const slotW = barSlotWidth(bin);
          const x = singleDay ? TRACK_LEFT : dateToX(bin.from);
          const y = PAD_Y + innerH - barH;
          const inRange = bin.to >= effectiveAfter && bin.from <= effectiveBefore;
          return (
            <rect
              key={`${bin.from}-${bin.to}`}
              x={x + 1}
              y={y}
              width={Math.max(1, slotW - 2)}
              height={barH}
              className={inRange ? "price-range-bar price-range-bar--in" : "price-range-bar"}
              rx={1}
            >
              <title>
                {bin.from === bin.to ? bin.from : `${bin.from} – ${bin.to}`}: {bin.count} photo
                {bin.count === 1 ? "" : "s"}
              </title>
            </rect>
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
          aria-label="Earliest photo date"
          aria-valuemin={dateToMs(min)}
          aria-valuemax={dateToMs(effectiveBefore)}
          aria-valuenow={dateToMs(thumbAfter)}
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
          aria-label="Latest photo date"
          aria-valuemin={dateToMs(effectiveAfter)}
          aria-valuemax={dateToMs(max)}
          aria-valuenow={dateToMs(thumbBefore)}
          onPointerDown={onPointerDown("max")}
          onKeyDown={onKeyDown("max")}
        />
      </svg>
      <div className="price-range-axis">
        <span>{formatAxisDate(effectiveAfter)}</span>
        <span>{formatAxisDate(effectiveBefore)}</span>
      </div>
    </div>
  );
}
