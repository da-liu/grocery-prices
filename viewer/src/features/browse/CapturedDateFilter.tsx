import { useState } from "react";
import { CapturedDateRangeChart } from "./CapturedDateRangeChart";
import {
  DATE_PRESETS,
  buildCapturedDateHistogram,
  datePresetRange,
  getDateExtents,
  matchDatePreset,
  photoTimesByImage,
  type DatePresetId,
} from "./browseQuery";
import type { Product } from "@/shared/types/types";
import "./CapturedDateFilter.css";

interface CapturedDateFilterProps {
  products: Product[];
  capturedAfter: string | null;
  capturedBefore: string | null;
  onChange: (next: { capturedAfter: string | null; capturedBefore: string | null }) => void;
}

function dateInputValue(bound: string | null): string {
  if (!bound) return "";
  const day = bound.slice(0, 10);
  return /^\d{4}-\d{2}-\d{2}$/.test(day) ? day : "";
}

export function CapturedDateFilter({
  products,
  capturedAfter,
  capturedBefore,
  onChange,
}: CapturedDateFilterProps) {
  const chartAfter = dateInputValue(capturedAfter) || null;
  const chartBefore = dateInputValue(capturedBefore) || null;
  const [customOpen, setCustomOpen] = useState(
    () =>
      matchDatePreset(capturedAfter, capturedBefore) === null &&
      Boolean(capturedAfter || capturedBefore),
  );

  const timeByImage = photoTimesByImage(products);
  const bins = buildCapturedDateHistogram(timeByImage);
  const extents = getDateExtents(timeByImage);
  const activePreset = matchDatePreset(chartAfter, chartBefore);

  function applyPreset(id: DatePresetId) {
    onChange(datePresetRange(id));
    setCustomOpen(false);
  }

  return (
    <fieldset className="browse-filter-group">
      <legend>Photo date</legend>

      <div className="browse-date-presets">
        {DATE_PRESETS.map((preset) => (
          <button
            key={preset.id}
            type="button"
            className={`browse-date-preset${activePreset === preset.id ? " active" : ""}`}
            aria-pressed={activePreset === preset.id}
            onClick={() => applyPreset(preset.id)}
          >
            {preset.label}
          </button>
        ))}
      </div>

      {extents ? (
        <CapturedDateRangeChart
          bins={bins}
          extents={extents}
          capturedAfter={chartAfter}
          capturedBefore={chartBefore}
          onChange={(next) => {
            onChange(next);
            if (matchDatePreset(next.capturedAfter, next.capturedBefore) === null) {
              setCustomOpen(true);
            }
          }}
        />
      ) : (
        <p className="price-range-empty">No dated photos in current selection.</p>
      )}

      <details
        className="browse-date-custom"
        open={customOpen}
        onToggle={(event) => setCustomOpen(event.currentTarget.open)}
      >
        <summary>Custom range</summary>
        <div className="browse-date-inputs">
          <label>
            From
            <input
              type="date"
              name="browse-captured-after"
              value={dateInputValue(capturedAfter)}
              onChange={(e) =>
                onChange({
                  capturedAfter: e.target.value || null,
                  capturedBefore: dateInputValue(capturedBefore) || null,
                })
              }
            />
          </label>
          <label>
            To
            <input
              type="date"
              name="browse-captured-before"
              value={dateInputValue(capturedBefore)}
              onChange={(e) =>
                onChange({
                  capturedAfter: dateInputValue(capturedAfter) || null,
                  capturedBefore: e.target.value || null,
                })
              }
            />
          </label>
        </div>
      </details>
    </fieldset>
  );
}
