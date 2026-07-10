import { Trash2 } from "lucide-react";
import { useEffect, useState } from "react";
import { productImageUrl } from "@/shared/api/api";
import {
  photoGroupNeedsStoreLabel,
  photoGroupTitle,
  type PhotoGroup,
} from "./browseQuery";
import { formatCapturedAgo, formatCapturedAt } from "@/shared/lib/formatCapturedAgo";
import { formatPrice } from "@/shared/lib/formatPrice";
import { LocationLabelButton } from "./LocationLabelButton";
import { PhotoLightbox } from "./PhotoLightbox";
import type { Product } from "@/shared/types/types";
import "./PhotoGroupCard.css";

export function PhotoGroupCard({
  group,
  onNavigateToProduct,
  onLabelLocation,
  onDeletePhoto,
  deleting,
  highlightProductId,
  highlighted,
}: {
  group: PhotoGroup;
  onNavigateToProduct?: (productId: string) => void;
  onLabelLocation?: (product: Product) => void;
  onDeletePhoto?: (imageId: string) => void;
  deleting?: boolean;
  highlightProductId?: string | null;
  highlighted?: boolean;
}) {
  const [expanded, setExpanded] = useState(false);
  const [lightboxOpen, setLightboxOpen] = useState(false);
  const [confirmingDelete, setConfirmingDelete] = useState(false);

  useEffect(() => {
    if (highlightProductId && group.products.some((product) => product.id === highlightProductId)) {
      setExpanded(true);
    }
  }, [highlightProductId, group.products]);

  const title = photoGroupTitle(group);
  const needsLabel = photoGroupNeedsStoreLabel(group);
  const imageUrl = productImageUrl(group.imageId);
  const preview = group.products.filter((product) => !product.extraction_empty);
  const visible = expanded ? preview : preview.slice(0, 2);
  const hiddenCount = Math.max(0, preview.length - visible.length);
  const deleteLabel =
    preview.length > 0
      ? `Delete photo and ${preview.length} product${preview.length === 1 ? "" : "s"}`
      : "Delete photo";

  function handleDeleteClick(e: React.MouseEvent) {
    e.stopPropagation();
    e.preventDefault();
    if (!onDeletePhoto || deleting) return;
    if (!confirmingDelete) {
      setConfirmingDelete(true);
      return;
    }
    onDeletePhoto(group.imageId);
    setConfirmingDelete(false);
  }

  return (
    <article
      id={`photo-${group.imageId}`}
      className={`photo-group-card${highlighted ? " photo-group-card--highlight" : ""}`}
    >
      <div className="photo-group-card-hero">
        <button
          type="button"
          className="photo-group-card-image-btn"
          aria-label={`View full photo: ${title}`}
          onClick={() => setLightboxOpen(true)}
        >
          <img src={imageUrl} alt="" className="photo-group-card-image" />
        </button>
        <div className="photo-group-card-info">
          <div className="photo-group-card-title-row">
            <button
              type="button"
              className="photo-group-card-title-btn"
              onClick={() => setExpanded((open) => !open)}
              aria-expanded={expanded}
            >
              <strong title={group.imageId}>{title}</strong>
              {group.photoType === "receipt" && (
                <span className="photo-group-badge">Receipt</span>
              )}
            </button>
            {onDeletePhoto && (
              <div className="card-delete-wrap">
                {confirmingDelete ? (
                  <>
                    <button
                      type="button"
                      className="card-delete-confirm"
                      disabled={deleting}
                      onClick={handleDeleteClick}
                    >
                      {deleting ? "…" : "Delete"}
                    </button>
                    <button
                      type="button"
                      className="card-delete-cancel"
                      disabled={deleting}
                      onClick={(e) => {
                        e.stopPropagation();
                        setConfirmingDelete(false);
                      }}
                    >
                      Cancel
                    </button>
                  </>
                ) : (
                  <button
                    type="button"
                    className="card-icon-btn card-icon-btn--delete"
                    aria-label={deleteLabel}
                    title="Delete"
                    disabled={deleting}
                    onClick={handleDeleteClick}
                  >
                    <Trash2 size={14} aria-hidden />
                  </button>
                )}
              </div>
            )}
          </div>
          <div
            role="button"
            tabIndex={0}
            className="photo-group-card-copy"
            onClick={() => setExpanded((open) => !open)}
            onKeyDown={(e) => {
              if (e.key === "Enter" || e.key === " ") {
                e.preventDefault();
                setExpanded((open) => !open);
              }
            }}
            aria-expanded={expanded}
          >
            <span className="photo-group-store-row">
              <span>{group.location.store}</span>
              {needsLabel && onLabelLocation && (
                <LocationLabelButton
                  needsLabel
                  onClick={() => onLabelLocation(group.products[0])}
                />
              )}
            </span>
            {group.capturedAt && (
              <span title={formatCapturedAt(group.capturedAt) ?? undefined}>
                {formatCapturedAgo(group.capturedAt)}
              </span>
            )}
            <span>
              {preview.length} product{preview.length === 1 ? "" : "s"}
            </span>
          </div>
        </div>
      </div>

      {lightboxOpen && (
        <PhotoLightbox
          src={imageUrl}
          alt={title}
          onClose={() => setLightboxOpen(false)}
        />
      )}

      <ul className="photo-group-products">
        {visible.map((product) => (
          <li key={product.id}>
            <button
              type="button"
              className={`photo-group-product-row${highlightProductId === product.id ? " photo-group-product-row--highlight" : ""}`}
              data-onboarding-target="photo-product-row"
              data-product-id={product.id}
              data-image-id={group.imageId}
              onClick={() => onNavigateToProduct?.(product.id)}
            >
              <span>{product.product_name}</span>
              <span>{formatPrice(product.price)}</span>
            </button>
          </li>
        ))}
        {!expanded && hiddenCount > 0 && (
          <li>
            <button
              type="button"
              className="photo-group-product-row photo-group-product-row--more"
              onClick={() => setExpanded(true)}
            >
              +{hiddenCount} more
            </button>
          </li>
        )}
      </ul>
    </article>
  );
}
