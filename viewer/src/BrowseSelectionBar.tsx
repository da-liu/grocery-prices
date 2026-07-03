interface BrowseSelectionBarProps {
  selectedCount: number;
  shownCount: number;
  allShownSelected: boolean;
  deleting: boolean;
  onSelectAllShown: () => void;
  onDeleteSelected: () => void;
  onCancel: () => void;
}

export function BrowseSelectionBar({
  selectedCount,
  shownCount,
  allShownSelected,
  deleting,
  onSelectAllShown,
  onDeleteSelected,
  onCancel,
}: BrowseSelectionBarProps) {
  const deleteClass = selectedCount > 0 ? "danger" : "danger-outline";

  return (
    <section
      className="browse-selection-bar browse-query-chips"
      aria-live="polite"
      aria-label="Selection mode"
    >
      <div className="browse-selection-status">
        <span className="browse-selection-label">Selecting items</span>
        <span className="browse-selection-count">
          {selectedCount} of {shownCount} selected
        </span>
        {!allShownSelected && shownCount > 0 && (
          <button
            type="button"
            className="browse-selection-select-all"
            onClick={onSelectAllShown}
            disabled={deleting}
          >
            Select all shown
          </button>
        )}
      </div>
      <div className="browse-selection-actions">
        <button type="button" className="ghost" onClick={onCancel} disabled={deleting}>
          Cancel
        </button>
        <button
          type="button"
          className={deleteClass}
          disabled={selectedCount === 0 || deleting}
          onClick={onDeleteSelected}
        >
          {deleting ? "Deleting…" : `Delete selected (${selectedCount})`}
        </button>
      </div>
    </section>
  );
}
