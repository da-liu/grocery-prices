import { useState } from "react";
import { CapturedDateRangeChart } from "./CapturedDateRangeChart";
import {
  DATE_PRESETS,
  buildCapturedDateHistogram,
  countDatedPhotos,
  datePresetRange,
  getDateExtents,
  matchDatePreset,
  type DatePresetId,
} from "./browseQuery";
import type { Product } from "./types";

interface CapturedDateFilterProps {
  products: Product[];
  capturedAfter: string | null;
  capturedBefore: string | null;
  onChange: (next: { capturedAfter: string | null; capturedBefore: string | null }) => void;
}

export function CapturedDateFilter({
  products,
  capturedAfter,
  capturedBefore,
  onChange,
}: CapturedDateFilterProps) {
  const [customOpen, setCustomOpen] = useState(
    () =>
      matchDatePreset(capturedAfter, capturedBefore) === null &&
      Boolean(capturedAfter || capturedBefore),
  );

  const bins = buildCapturedDateHistogram(products);
  const extents = getDateExtents(bins, countDatedPhotos(products));
  const activePreset = matchDatePreset(capturedAfter, capturedBefore);

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
          capturedAfter={capturedAfter}
          capturedBefore={capturedBefore}
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
              value={capturedAfter ?? ""}
              onChange={(e) =>
                onChange({
                  capturedAfter: e.target.value || null,
                  capturedBefore,
                })
              }
            />
          </label>
          <label>
            To
            <input
              type="date"
              value={capturedBefore ?? ""}
              onChange={(e) =>
                onChange({
                  capturedAfter,
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
