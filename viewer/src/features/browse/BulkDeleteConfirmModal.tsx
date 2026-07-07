import { useRef } from "react";
import { createPortal } from "react-dom";
import type { BulkDeleteImpact } from "./bulkDelete";
import { useModalDialog } from "@/shared/hooks/useModalDialog";
import "./BulkDeleteConfirmModal.css";
import "@/shared/styles/modal.css";

interface BulkDeleteConfirmModalProps {
  impact: BulkDeleteImpact;
  deleting: boolean;
  onConfirm: () => void;
  onCancel: () => void;
}

export function BulkDeleteConfirmModal({
  impact,
  deleting,
  onConfirm,
  onCancel,
}: BulkDeleteConfirmModalProps) {
  const dialogRef = useRef<HTMLDivElement>(null);
  const confirmRef = useRef<HTMLButtonElement>(null);
  const { titleId, descriptionId } = useModalDialog({
    onClose: onCancel,
    closeDisabled: deleting,
    dialogRef,
    initialFocusRef: confirmRef,
  });

  const productCount = impact.validIds.length;
  if (productCount <= 0) return null;

  const itemLabel = productCount === 1 ? "1 item" : `${productCount} items`;
  const photoNote =
    impact.photosRemoved > 0
      ? `This will also remove ${impact.photosRemoved} photo${impact.photosRemoved === 1 ? "" : "s"} where these are the only items.`
      : null;

  const dialog = (
    <div
      className="modal-backdrop"
      role="presentation"
      onClick={deleting ? undefined : onCancel}
    >
      <div
        ref={dialogRef}
        className="modal bulk-delete-modal"
        role="dialog"
        aria-modal="true"
        aria-labelledby={titleId}
        aria-describedby={descriptionId}
        onClick={(event) => event.stopPropagation()}
      >
        <header className="modal-header">
          <h2 id={titleId}>Delete {itemLabel}?</h2>
          <div id={descriptionId}>
            {photoNote && <p className="subtitle">{photoNote}</p>}
            <p className="subtitle">This cannot be undone.</p>
          </div>
        </header>
        <div className="bulk-delete-actions">
          <button type="button" className="ghost" disabled={deleting} onClick={onCancel}>
            Cancel
          </button>
          <button
            ref={confirmRef}
            type="button"
            className="danger-outline"
            disabled={deleting}
            onClick={onConfirm}
          >
            {deleting ? "Deleting…" : `Delete ${itemLabel}`}
          </button>
        </div>
      </div>
    </div>
  );

  return createPortal(dialog, document.body);
}
