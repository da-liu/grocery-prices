import { useCallback, useId, useMemo, useRef, useState } from "react";
import {
  clampDateISO,
  dateToMs,
  msToISODate,
  type DateBin,
  type DateExtents,
} from "./browseQuery";
import "./PriceRangeChart.css";

function formatAxisDate(iso: string) {
  const [year, month, day] = iso.split("-").map(Number);
  const date = new Date(year, month - 1, day);
  return date.toLocaleDateString(undefined, { month: "short", day: "numeric" });
}

function formatBinLabel(bin: DateBin): string {
  const day = bin.from.slice(0, 10);
  const [year, month, dayNum] = day.split("-").map(Number);
  const date = new Date(year, month - 1, dayNum);
  return date.toLocaleDateString(undefined, { month: "short", day: "numeric", year: "numeric" });
}

function binOverlapsDateRange(bin: DateBin, after: string, before: string): boolean {
  const binDayFrom = bin.from.slice(0, 10);
  const binDayTo = msToISODate(dateToMs(bin.to.slice(0, 10)) - 1);
  return binDayTo >= after && binDayFrom <= before;
}

const MS_PER_DAY = 86400000;

function chartDaysBetween(minMs: number, maxMs: number): string[] {
  const days: string[] = [];
  for (let ms = minMs; ms < maxMs; ms += MS_PER_DAY) {
    days.push(msToISODate(ms));
  }
  return days;
}

function dateFromMinThumbX(
  x: number,
  days: string[],
  midpointX: (day: string) => number,
): string {
  for (const day of days) {
    if (x < midpointX(day)) return day;
  }
  return days[days.length - 1];
}

function dateFromMaxThumbX(
  x: number,
  days: string[],
  midpointX: (day: string) => number,
): string {
  for (let i = days.length - 1; i >= 0; i--) {
    if (x > midpointX(days[i])) return days[i];
  }
  return days[0];
}

interface CapturedDateRangeChartProps {
  bins: DateBin[];
  extents: DateExtents;
  capturedAfter: string | null;
  capturedBefore: string | null;
  onChange: (next: { capturedAfter: string | null; capturedBefore: string | null }) => void;
}

type DateDraft = { capturedAfter: string; capturedBefore: string };

const THUMB_R = 10;
const CHART_WIDTH = 320;
const CHART_HEIGHT = 88;
const PAD_X = 14;
const PAD_Y = 8;
const TRACK_LEFT = PAD_X + THUMB_R;
const TRACK_RIGHT = CHART_WIDTH - PAD_X - THUMB_R;

export function CapturedDateRangeChart({
  bins,
  extents,
  capturedAfter,
  capturedBefore,
  onChange,
}: CapturedDateRangeChartProps) {
  const labelId = useId();
  const chartBodyRef = useRef<HTMLDivElement>(null);
  const trackRef = useRef<SVGSVGElement>(null);
  const draggingRef = useRef<"min" | "max" | null>(null);
  const draftRef = useRef<DateDraft | null>(null);
  const [draft, setDraft] = useState<DateDraft | null>(null);
  const [dragThumbX, setDragThumbX] = useState<{ handle: "min" | "max"; x: number } | null>(
    null,
  );
  const [tooltip, setTooltip] = useState<{ text: string; x: number; y: number } | null>(null);

  const { min, max } = extents;
  const sameCalendarDay = min === max;
  const daySpanMinMs = dateToMs(min);
  const daySpanMaxMs = dateToMs(max) + MS_PER_DAY;
  const span = Math.max(daySpanMaxMs - daySpanMinMs, MS_PER_DAY);
  const activeAfter = draft !== null ? draft.capturedAfter : capturedAfter;
  const activeBefore = draft !== null ? draft.capturedBefore : capturedBefore;
  const effectiveAfter = activeAfter ?? min;
  const effectiveBefore = activeBefore ?? max;
  const thumbAfter = clampDateISO(effectiveAfter, min, max);
  const thumbBefore = clampDateISO(effectiveBefore, min, max);

  const maxCount = Math.max(1, ...bins.map((bin) => bin.count));
  const innerW = TRACK_RIGHT - TRACK_LEFT;
  const innerH = CHART_HEIGHT - PAD_Y * 2;

  const timeToX = useCallback(
    (ms: number) => TRACK_LEFT + ((ms - daySpanMinMs) / span) * innerW,
    [daySpanMinMs, innerW, span],
  );

  const dayStartMs = useCallback((iso: string) => dateToMs(iso.slice(0, 10)), []);
  const dayEndMs = useCallback(
    (iso: string) => Math.min(dayStartMs(iso) + MS_PER_DAY, daySpanMaxMs),
    [daySpanMaxMs, dayStartMs],
  );

  const dateStartToX = useCallback((iso: string) => timeToX(dayStartMs(iso)), [dayStartMs, timeToX]);
  const dateEndToX = useCallback((iso: string) => timeToX(dayEndMs(iso)), [dayEndMs, timeToX]);

  const chartDays = useMemo(
    () => chartDaysBetween(daySpanMinMs, daySpanMaxMs),
    [daySpanMinMs, daySpanMaxMs],
  );

  const dayMidpointX = useCallback(
    (day: string) => (dateStartToX(day) + dateEndToX(day)) / 2,
    [dateEndToX, dateStartToX],
  );

  const filterMinX = sameCalendarDay ? TRACK_LEFT : dateStartToX(thumbAfter);
  const filterMaxX = sameCalendarDay ? TRACK_RIGHT : dateEndToX(thumbBefore);
  const minX = dragThumbX?.handle === "min" ? dragThumbX.x : filterMinX;
  const maxX = dragThumbX?.handle === "max" ? dragThumbX.x : filterMaxX;

  function pointerX(clientX: number) {
    const svg = trackRef.current;
    if (!svg) return TRACK_LEFT;
    const rect = svg.getBoundingClientRect();
    return ((clientX - rect.left) / rect.width) * CHART_WIDTH;
  }

  function pointerDateFromX(x: number, handle: "min" | "max") {
    const clampedX = Math.max(TRACK_LEFT, Math.min(TRACK_RIGHT, x));
    const date =
      handle === "min"
        ? dateFromMinThumbX(clampedX, chartDays, dayMidpointX)
        : dateFromMaxThumbX(clampedX, chartDays, dayMidpointX);
    return clampDateISO(date, min, max);
  }

  function showBarTooltip(e: React.PointerEvent, bin: DateBin) {
    if (draggingRef.current) return;
    const host = chartBodyRef.current;
    if (!host) return;
    const hostRect = host.getBoundingClientRect();
    const barRect = (e.currentTarget as SVGRectElement).getBoundingClientRect();
    setTooltip({
      text: `${formatBinLabel(bin)}: ${bin.count} photo${bin.count === 1 ? "" : "s"}`,
      x: barRect.left + barRect.width / 2 - hostRect.left,
      y: barRect.top - hostRect.top,
    });
  }

  function hideBarTooltip() {
    setTooltip(null);
  }

  function onPointerDown(handle: "min" | "max") {
    return (e: React.PointerEvent) => {
      e.preventDefault();
      hideBarTooltip();
      draggingRef.current = handle;
      const initial = {
        capturedAfter: capturedAfter ?? min,
        capturedBefore: capturedBefore ?? max,
      };
      draftRef.current = initial;
      setDraft(initial);
      trackRef.current?.setPointerCapture(e.pointerId);
    };
  }

  function draftAfter(next: string) {
    if (dateToMs(next) <= dateToMs(min)) return min;
    if (dateToMs(next) > dateToMs(max)) return max;
    return next;
  }

  function draftBefore(next: string) {
    if (dateToMs(next) >= dateToMs(max)) return max;
    if (dateToMs(next) < dateToMs(min)) return min;
    return next;
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
    if (!draggingRef.current) return;
    const handle = draggingRef.current;
    const rawX = pointerX(e.clientX);
    const clampedX = Math.max(TRACK_LEFT, Math.min(TRACK_RIGHT, rawX));
    const date = pointerDateFromX(clampedX, handle);

    const base = draftRef.current ?? {
      capturedAfter: capturedAfter ?? min,
      capturedBefore: capturedBefore ?? max,
    };
    const baseAfter = base.capturedAfter;
    const baseBefore = base.capturedBefore;

    let next: DateDraft;
    let thumbX: number;
    if (handle === "min") {
      const nextAfter = date <= baseBefore ? date : baseBefore;
      next = {
        capturedAfter: draftAfter(nextAfter),
        capturedBefore: base.capturedBefore,
      };
      thumbX = Math.min(clampedX, dateEndToX(baseBefore));
    } else {
      const nextBefore = date >= baseAfter ? date : baseAfter;
      next = {
        capturedAfter: base.capturedAfter,
        capturedBefore: draftBefore(nextBefore),
      };
      thumbX = Math.max(clampedX, dateStartToX(baseAfter));
    }

    draftRef.current = next;
    setDraft(next);
    setDragThumbX({ handle, x: thumbX });
  }

  function onPointerUp() {
    if (draggingRef.current && draftRef.current) {
      const { capturedAfter: draftAfterVal, capturedBefore: draftBeforeVal } = draftRef.current;
      onChange({
        capturedAfter: commitAfter(draftAfterVal),
        capturedBefore: commitBefore(draftBeforeVal),
      });
    }
    draggingRef.current = null;
    draftRef.current = null;
    setDraft(null);
    setDragThumbX(null);
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
          capturedBefore: activeBefore,
        });
      } else {
        const nextBefore = clampDateISO(
          shiftDate(effectiveBefore, delta),
          effectiveAfter,
          max,
        );
        onChange({
          capturedAfter: activeAfter,
          capturedBefore: commitBefore(nextBefore),
        });
      }
    };
  }

  const barX = (bin: DateBin) => dateStartToX(bin.from);
  const barWidth = (bin: DateBin) => Math.max(1, dateEndToX(bin.from) - dateStartToX(bin.from));

  return (
    <div className="price-range-chart">
      <p className="price-range-meta" id={labelId}>
        {extents.datedPhotoCount} photos with dates · drag handles to filter
      </p>
      <div className="price-range-chart-body" ref={chartBodyRef}>
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
            const x = barX(bin);
            const w = barWidth(bin);
            const y = PAD_Y + innerH - barH;
            const inRange = binOverlapsDateRange(bin, effectiveAfter, effectiveBefore);
            return (
              <rect
                key={`${bin.from}-${bin.to}`}
                x={x + 1}
                y={y}
                width={Math.max(1, w - 2)}
                height={barH}
                className={inRange ? "price-range-bar price-range-bar--in" : "price-range-bar"}
                rx={1}
                onPointerEnter={(e) => showBarTooltip(e, bin)}
                onPointerMove={(e) => showBarTooltip(e, bin)}
                onPointerLeave={hideBarTooltip}
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
        {tooltip ? (
          <div
            className="price-range-tooltip"
            style={{ left: tooltip.x, top: tooltip.y }}
            role="tooltip"
          >
            {tooltip.text}
          </div>
        ) : null}
      </div>
      <div className="price-range-axis">
        <span>{formatAxisDate(effectiveAfter)}</span>
        <span>{formatAxisDate(effectiveBefore)}</span>
      </div>
    </div>
  );
}
