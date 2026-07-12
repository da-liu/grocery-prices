import { X } from "lucide-react";
import type { BrowseChip, BrowseQueryState, PriceExtents } from "./browseQuery";
import {
  EMPTY_BROWSE_QUERY,
  buildActiveChips,
  removeChip,
} from "./browseQuery";
import type { Product } from "@/shared/types/types";
import "./BrowseQueryChips.css";

interface BrowseQueryChipsProps {
  query: BrowseQueryState;
  extents: PriceExtents | null;
  products: Product[];
  onChange: (query: BrowseQueryState) => void;
}

export function BrowseQueryChips({ query, extents, products, onChange }: BrowseQueryChipsProps) {
  const chips = buildActiveChips(query, extents, products);
  if (chips.length === 0) return null;

  function handleRemove(chip: BrowseChip) {
    onChange(removeChip(query, chip.id));
  }

  function clearAll() {
    onChange(EMPTY_BROWSE_QUERY);
  }

  return (
    <div className="browse-query-chips" role="region" aria-label="Active sort and filters">
      <span className="browse-query-chips-count">
        {chips.length} active
      </span>
      {chips.map((chip) => (
        <span key={chip.id} className="browse-query-chip">
          {chip.label}
          <button
            type="button"
            className="browse-query-chip-remove"
            aria-label={`Remove ${chip.label}`}
            onClick={() => handleRemove(chip)}
          >
            <X size={14} aria-hidden />
          </button>
        </span>
      ))}
      <button type="button" className="browse-query-clear" onClick={clearAll}>
        Clear all
      </button>
    </div>
  );
}
