import { useState } from "react";
import { productImageUrl } from "./api";
import { formatCapturedAgo, formatCapturedAt } from "./formatCapturedAgo";
import { PhotoLightbox } from "./PhotoLightbox";
import type { PhotoGroup } from "./browseQuery";

function formatPrice(price: number | null | undefined) {
  if (price == null) return "—";
  return new Intl.NumberFormat("en-CA", {
    style: "currency",
    currency: "CAD",
  }).format(price);
}

export function PhotoGroupCard({
  group,
  onNavigateToProduct,
}: {
  group: PhotoGroup;
  onNavigateToProduct?: (productId: string) => void;
}) {
  const [expanded, setExpanded] = useState(false);
  const [lightboxOpen, setLightboxOpen] = useState(false);
  const imageUrl = productImageUrl(group.imageId);
  const preview = group.products.filter((product) => !product.extraction_empty);
  const visible = expanded ? preview : preview.slice(0, 2);
  const hiddenCount = Math.max(0, preview.length - visible.length);

  return (
    <article className="photo-group-card">
      <div className="photo-group-card-hero">
        <button
          type="button"
          className="photo-group-card-image-btn"
          aria-label={`View full photo ${group.imageId}`}
          onClick={() => setLightboxOpen(true)}
        >
          <img src={imageUrl} alt="" className="photo-group-card-image" />
        </button>
        <button
          type="button"
          className="photo-group-card-copy"
          onClick={() => setExpanded((open) => !open)}
          aria-expanded={expanded}
        >
          <div className="photo-group-card-title-row">
            <strong>{group.imageId}</strong>
            {group.photoType === "receipt" && <span className="photo-group-badge">Receipt</span>}
          </div>
          <span>{group.store}</span>
          {group.capturedAt && (
            <span title={formatCapturedAt(group.capturedAt) ?? undefined}>
              {formatCapturedAgo(group.capturedAt)}
            </span>
          )}
          <span>
            {preview.length} product{preview.length === 1 ? "" : "s"}
          </span>
        </button>
      </div>

      {lightboxOpen && (
        <PhotoLightbox
          src={imageUrl}
          alt={group.imageId}
          onClose={() => setLightboxOpen(false)}
        />
      )}

      <ul className="photo-group-products">
        {visible.map((product) => (
          <li key={product.id}>
            <button
              type="button"
              className="photo-group-product-row"
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
