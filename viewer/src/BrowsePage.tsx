import { useState } from "react";
import { formatCapturedAgo, formatCapturedAt } from "./formatCapturedAgo";
import { productImageUrl } from "./api";
import { LocationLabelButton } from "./LocationLabelButton";
import { PhotoLightbox } from "./PhotoLightbox";
import { StoreLink } from "./StoreLink";
import { hasValidCoords } from "./maps";
import type { Product } from "./types";

function formatPrice(price: number | null | undefined, currency = "CAD") {
  if (price == null) return "—";
  return new Intl.NumberFormat("en-CA", {
    style: "currency",
    currency,
  }).format(price);
}

function ProductCard({
  product,
  onDelete,
  deleting,
  onLabelLocation,
}: {
  product: Product;
  onDelete?: (productId: string) => void;
  deleting?: boolean;
  onLabelLocation?: (product: Product) => void;
}) {
  const imgSrc = productImageUrl(product.image_id);
  const { latitude, longitude, store } = product.location;
  const hasCoords = hasValidCoords(latitude, longitude);
  const needsLabel = store === "Unknown store" || !product.location.store_location_id;
  const [lightboxOpen, setLightboxOpen] = useState(false);
  const [confirming, setConfirming] = useState(false);
  const capturedAgo = formatCapturedAgo(product.captured_at);
  const capturedLabel = formatCapturedAt(product.captured_at);

  function handleDeleteClick(e: React.MouseEvent) {
    e.stopPropagation();
    e.preventDefault();
    if (!onDelete || deleting) return;
    if (!confirming) {
      setConfirming(true);
      return;
    }
    onDelete(product.id);
    setConfirming(false);
  }

  return (
    <article className="card">
      <button
        type="button"
        className="card-image-wrap"
        aria-label={`View full photo of ${product.product_name}`}
        onClick={() => setLightboxOpen(true)}
      >
        <img src={imgSrc} alt={product.product_name} loading="lazy" />
        {product.is_special && <span className="badge special">Special</span>}
      </button>
      {lightboxOpen && (
        <PhotoLightbox
          src={imgSrc}
          alt={product.product_name}
          onClose={() => setLightboxOpen(false)}
        />
      )}
      <div className="card-body">
        <div className="card-title-row">
          <h2>{product.product_name}</h2>
          {onDelete && (
            <div className="card-delete-wrap">
              {confirming ? (
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
                      setConfirming(false);
                    }}
                  >
                    Cancel
                  </button>
                </>
              ) : (
                <button
                  type="button"
                  className="card-delete"
                  aria-label={`Delete ${product.product_name}`}
                  disabled={deleting}
                  onClick={handleDeleteClick}
                >
                  <svg viewBox="0 0 24 24" width="14" height="14" aria-hidden="true">
                    <path
                      fill="none"
                      stroke="currentColor"
                      strokeWidth="2"
                      strokeLinecap="round"
                      d="M7 7l10 10M17 7 7 17"
                    />
                  </svg>
                </button>
              )}
            </div>
          )}
        </div>
        {product.product_name_zh && (
          <p className="zh">{product.product_name_zh}</p>
        )}
        <div className="price-row">
          <span className="price">{formatPrice(product.price, product.price_currency)}</span>
          {product.unit && <span className="unit">/ {product.unit}</span>}
          {product.regular_price != null && product.is_special && (
            <span className="was">was {formatPrice(product.regular_price)}</span>
          )}
        </div>
        {product.promo && <p className="promo">{product.promo}</p>}
        <dl className="meta">
          {product.brand && (
            <>
              <dt>Brand</dt>
              <dd>{product.brand}</dd>
            </>
          )}
          {product.size && (
            <>
              <dt>Size</dt>
              <dd>{product.size}</dd>
            </>
          )}
          {product.unit_price != null && (
            <>
              <dt>Unit price</dt>
              <dd>{formatPrice(product.unit_price)}/{product.unit ?? "unit"}</dd>
            </>
          )}
          {product.barcode && (
            <>
              <dt>Barcode</dt>
              <dd className="mono">{product.barcode}</dd>
            </>
          )}
          {product.packed_on && (
            <>
              <dt>Packed on</dt>
              <dd>{product.packed_on}</dd>
            </>
          )}
          <dt>Store</dt>
          <dd className="store-meta-row">
            <StoreLink location={product.location} />
            {hasCoords && onLabelLocation && (
              <LocationLabelButton
                needsLabel={needsLabel}
                onClick={() => onLabelLocation(product)}
              />
            )}
          </dd>
          <dt>Category</dt>
          <dd>{product.category}</dd>
          {capturedAgo && (
            <>
              <dt>Taken</dt>
              <dd title={capturedLabel ?? undefined}>{capturedAgo}</dd>
            </>
          )}
        </dl>
      </div>
    </article>
  );
}

export function BrowsePage({
  products,
  search,
  store,
  onStartUpload,
  onDeleteProduct,
  deletingId,
  onLabelLocation,
}: {
  products: Product[];
  search: string;
  store: string;
  onStartUpload?: () => void;
  onDeleteProduct?: (productId: string) => void;
  deletingId?: string | null;
  onLabelLocation?: (product: Product) => void;
}) {
  const filtered = (() => {
    const q = search.trim().toLowerCase();
    const rows = products.filter((p) => {
      if (store !== "all" && p.location.store !== store) return false;
      if (!q) return true;
      const hay = [
        p.product_name,
        p.product_name_zh,
        p.brand,
        p.location.store,
        p.category,
        p.barcode,
      ]
        .filter(Boolean)
        .join(" ")
        .toLowerCase();
      return hay.includes(q);
    });
    return rows.sort((a, b) => {
      const ta = a.captured_at ? new Date(a.captured_at).getTime() : 0;
      const tb = b.captured_at ? new Date(b.captured_at).getTime() : 0;
      return tb - ta;
    });
  })();

  if (products.length === 0) {
    return (
      <section className="panel empty-state">
        <h1>Your catalog is empty</h1>
        <p className="subtitle">Upload a shelf photo to extract your first products.</p>
        {onStartUpload && (
          <button type="button" onClick={onStartUpload}>
            Upload first photo
          </button>
        )}
      </section>
    );
  }

  return (
    <>
      <main className="grid">
        {filtered.map((p) => (
          <ProductCard
            key={p.id}
            product={p}
            onDelete={onDeleteProduct}
            deleting={deletingId === p.id}
            onLabelLocation={onLabelLocation}
          />
        ))}
      </main>

      {filtered.length === 0 && (
        <p className="status">No products match your filters.</p>
      )}
    </>
  );
}
