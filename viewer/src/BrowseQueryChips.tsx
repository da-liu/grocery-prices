import type { BrowseChip, BrowseQueryState, PriceExtents } from "./browseQuery";
import {
  EMPTY_BROWSE_QUERY,
  buildActiveChips,
  countActiveChips,
  removeChip,
} from "./browseQuery";

interface BrowseQueryChipsProps {
  query: BrowseQueryState;
  extents: PriceExtents | null;
  onChange: (query: BrowseQueryState) => void;
}

export function BrowseQueryChips({ query, extents, onChange }: BrowseQueryChipsProps) {
  const chips = buildActiveChips(query, extents);
  if (chips.length === 0) return null;

  const activeCount = countActiveChips(query, extents);

  function handleRemove(chip: BrowseChip) {
    onChange(removeChip(query, chip.id));
  }

  function clearAll() {
    onChange(EMPTY_BROWSE_QUERY);
  }

  return (
    <div className="browse-query-chips" role="region" aria-label="Active sort and filters">
      <span className="browse-query-chips-count">
        {activeCount} active
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
            ×
          </button>
        </span>
      ))}
      <button type="button" className="browse-query-clear" onClick={clearAll}>
        Clear all
      </button>
    </div>
  );
}
