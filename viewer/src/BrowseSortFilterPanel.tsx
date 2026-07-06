import { useEffect, useId } from "react";
import {
  EMPTY_BROWSE_QUERY,
  GRID_COLUMN_OPTIONS,
  SORT_OPTIONS,
  buildPriceHistogram,
  getPriceExtents,
  productsForPriceHistogram,
  productsForDateHistogram,
  toggleListValue,
  type BrowseQueryState,
} from "./browseQuery";
import { CapturedDateFilter } from "./CapturedDateFilter";
import { PriceRangeChart } from "./PriceRangeChart";
import type { Product } from "./types";

interface BrowseStats {
  shown: number;
  total: number;
  avgPriceLabel: string;
}

interface BrowseSortFilterPanelProps {
  open: boolean;
  query: BrowseQueryState;
  onChange: (query: BrowseQueryState) => void;
  onClose: () => void;
  products: Product[];
  search: string;
  stores: string[];
  categories: string[];
  stats: BrowseStats;
  selectionMode: boolean;
  onEnterSelection: () => void;
  onExitSelection: () => void;
  onDeleteAllProducts?: () => void;
  deletingAll?: boolean;
}

function TriState({
  label,
  value,
  onChange,
}: {
  label: string;
  value: boolean | null;
  onChange: (value: boolean | null) => void;
}) {
  return (
    <fieldset className="browse-filter-group">
      <legend>{label}</legend>
      <div className="browse-tristate">
        {([null, true, false] as const).map((v) => (
          <button
            key={String(v)}
            type="button"
            className={`browse-tristate-btn${value === v ? " active" : ""}`}
            aria-pressed={value === v}
            onClick={() => onChange(v)}
          >
            {v === null ? "Any" : v ? "Yes" : "No"}
          </button>
        ))}
      </div>
    </fieldset>
  );
}

function CheckboxList({
  label,
  options,
  selected,
  onChange,
}: {
  label: string;
  options: string[];
  selected: string[];
  onChange: (values: string[]) => void;
}) {
  if (options.length === 0) {
    return (
      <fieldset className="browse-filter-group">
        <legend>{label}</legend>
        <p className="browse-filter-empty">None in catalog</p>
      </fieldset>
    );
  }

  return (
    <fieldset className="browse-filter-group">
      <legend>{label}</legend>
      <div className="browse-checkbox-grid">
        {options.map((opt) => (
          <label key={opt} className="browse-checkbox-label">
            <input
              type="checkbox"
              checked={selected.includes(opt)}
              onChange={() => onChange(toggleListValue(selected, opt))}
            />
            {opt}
          </label>
        ))}
      </div>
    </fieldset>
  );
}

function formatInputPrice(value: number | null) {
  return value == null ? "" : String(value);
}

export function BrowseSortFilterPanel({
  open,
  query,
  onChange,
  onClose,
  products,
  search,
  stores,
  categories,
  stats,
  selectionMode,
  onEnterSelection,
  onExitSelection,
  onDeleteAllProducts,
  deletingAll = false,
}: BrowseSortFilterPanelProps) {
  const titleId = useId();

  useEffect(() => {
    if (!open) return;
    function onKeyDown(e: KeyboardEvent) {
      if (e.key === "Escape") onClose();
    }
    document.addEventListener("keydown", onKeyDown);
    return () => document.removeEventListener("keydown", onKeyDown);
  }, [open, onClose]);

  if (!open) return null;

  const histogramProducts = productsForPriceHistogram(products, query, search);
  const dateHistogramProducts = productsForDateHistogram(products, query, search);
  const priceExtents = getPriceExtents(histogramProducts);
  const bins = buildPriceHistogram(histogramProducts);

  function update<K extends keyof BrowseQueryState>(key: K, value: BrowseQueryState[K]) {
    onChange({ ...query, [key]: value });
  }

  function resetAll() {
    onChange(EMPTY_BROWSE_QUERY);
  }

  return (
    <div className="browse-filter-backdrop" onClick={onClose}>
      <div
        className="browse-filter-panel"
        role="dialog"
        aria-modal="true"
        aria-labelledby={titleId}
        onClick={(e) => e.stopPropagation()}
      >
        <header className="browse-filter-header">
          <h2 id={titleId}>Sort &amp; filter</h2>
          <button type="button" className="browse-filter-close" onClick={onClose} aria-label="Close">
            ×
          </button>
        </header>

        <div className="browse-filter-body">
          <fieldset className="browse-filter-group">
            <legend>View</legend>
            <div className="browse-tristate">
              <button
                type="button"
                className={`browse-tristate-btn${query.viewMode === "products" ? " active" : ""}`}
                aria-pressed={query.viewMode === "products"}
                onClick={() => update("viewMode", "products")}
              >
                By product
              </button>
              <button
                type="button"
                className={`browse-tristate-btn${query.viewMode === "photos" ? " active" : ""}`}
                aria-pressed={query.viewMode === "photos"}
                onClick={() => update("viewMode", "photos")}
              >
                By photo
              </button>
            </div>
          </fieldset>

          <fieldset className="browse-filter-group">
            <legend>Card size</legend>
            <p className="browse-filter-hint">
              Fits as many cards as your screen allows. Larger settings show fewer, bigger cards.
            </p>
            <div className="browse-tristate browse-grid-cols">
              {GRID_COLUMN_OPTIONS.map((opt) => (
                <button
                  key={opt.value}
                  type="button"
                  className={`browse-tristate-btn${query.gridColumns === opt.value ? " active" : ""}`}
                  aria-pressed={query.gridColumns === opt.value}
                  onClick={() => update("gridColumns", opt.value)}
                >
                  {opt.label}
                </button>
              ))}
            </div>
          </fieldset>

          <fieldset className="browse-filter-group">
            <legend>Sort</legend>
            <div className="browse-sort-list">
              {SORT_OPTIONS.map((opt) => (
                <label key={opt.value} className="browse-sort-option">
                  <input
                    type="radio"
                    name="browse-sort"
                    checked={query.sort === opt.value}
                    onChange={() => update("sort", opt.value)}
                  />
                  {opt.label}
                </label>
              ))}
            </div>
          </fieldset>

          <CheckboxList
            label="Store"
            options={stores}
            selected={query.stores}
            onChange={(stores) => update("stores", stores)}
          />

          <CheckboxList
            label="Category"
            options={categories}
            selected={query.categories}
            onChange={(categories) => update("categories", categories)}
          />

          <fieldset className="browse-filter-group">
            <legend>Price range</legend>
            <PriceRangeChart
              bins={bins}
              extents={priceExtents}
              priceMin={query.priceMin}
              priceMax={query.priceMax}
              onChange={({ priceMin, priceMax }) =>
                onChange({ ...query, priceMin, priceMax })
              }
            />
            <div className="browse-price-inputs">
              <label>
                Min
                <input
                  type="number"
                  min={0}
                  step={0.01}
                  placeholder={priceExtents.pricedCount ? String(priceExtents.min) : "—"}
                  value={formatInputPrice(query.priceMin)}
                  onChange={(e) => {
                    const raw = e.target.value;
                    update("priceMin", raw === "" ? null : Number(raw));
                  }}
                />
              </label>
              <span className="browse-price-sep">to</span>
              <label>
                Max
                <input
                  type="number"
                  min={0}
                  step={0.01}
                  placeholder={priceExtents.pricedCount ? String(priceExtents.max) : "—"}
                  value={formatInputPrice(query.priceMax)}
                  onChange={(e) => {
                    const raw = e.target.value;
                    update("priceMax", raw === "" ? null : Number(raw));
                  }}
                />
              </label>
            </div>
          </fieldset>

          <TriState label="On sale" value={query.onSale} onChange={(v) => update("onSale", v)} />
          <TriState
            label="Has price"
            value={query.hasPrice}
            onChange={(v) => update("hasPrice", v)}
          />
          <TriState
            label="Store labeled"
            value={query.storeLabeled}
            onChange={(v) => update("storeLabeled", v)}
          />

          <CapturedDateFilter
            products={dateHistogramProducts}
            capturedAfter={query.capturedAfter}
            capturedBefore={query.capturedBefore}
            onChange={({ capturedAfter, capturedBefore }) =>
              onChange({ ...query, capturedAfter, capturedBefore })
            }
          />

          {onDeleteAllProducts && (
            <div className="browse-filter-danger">
              <button
                type="button"
                className="danger-outline"
                disabled={deletingAll}
                onClick={() => onDeleteAllProducts()}
              >
                {deletingAll ? "Deleting…" : "Delete all products"}
              </button>
            </div>
          )}
        </div>

        <footer className="browse-filter-footer">
          <p className="browse-filter-stats">
            Showing {stats.shown} of {stats.total}
            {stats.avgPriceLabel !== "—" && <> · avg {stats.avgPriceLabel}</>}
          </p>
          <div className="browse-filter-actions browse-filter-actions--secondary">
            {selectionMode ? (
              <button type="button" className="ghost" onClick={onExitSelection}>
                Cancel selection
              </button>
            ) : (
              <button
                type="button"
                className="ghost"
                disabled={stats.shown === 0}
                onClick={() => {
                  onEnterSelection();
                  onClose();
                }}
              >
                Select items
              </button>
            )}
            <button type="button" className="ghost" onClick={resetAll}>
              Reset filters
            </button>
          </div>
          <div className="browse-filter-actions browse-filter-actions--primary">
            <button type="button" className="browse-filter-done" onClick={onClose}>
              Done
            </button>
          </div>
        </footer>
      </div>
    </div>
  );
}
