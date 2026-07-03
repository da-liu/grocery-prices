interface BulkDeleteConfirmModalProps {
  productCount: number;
  photosRemoved: number;
  deleting: boolean;
  onConfirm: () => void;
  onCancel: () => void;
}

export function BulkDeleteConfirmModal({
  productCount,
  photosRemoved,
  deleting,
  onConfirm,
  onCancel,
}: BulkDeleteConfirmModalProps) {
  const itemLabel = productCount === 1 ? "1 item" : `${productCount} items`;
  const photoNote =
    photosRemoved > 0
      ? `This will also remove ${photosRemoved} photo${photosRemoved === 1 ? "" : "s"} where these are the only items.`
      : null;

  return (
    <div className="modal-backdrop" role="presentation" onClick={onCancel}>
      <div
        className="modal bulk-delete-modal"
        role="dialog"
        aria-labelledby="bulk-delete-title"
        onClick={(e) => e.stopPropagation()}
      >
        <header className="modal-header">
          <h2 id="bulk-delete-title">Delete {itemLabel}?</h2>
          {photoNote && <p className="subtitle">{photoNote}</p>}
          <p className="subtitle">This cannot be undone.</p>
        </header>
        <div className="bulk-delete-actions">
          <button type="button" className="ghost" disabled={deleting} onClick={onCancel}>
            Cancel
          </button>
          <button type="button" className="danger-outline" disabled={deleting} onClick={onConfirm}>
            {deleting ? "Deleting…" : `Delete ${itemLabel}`}
          </button>
        </div>
      </div>
    </div>
  );
}
