import { useState } from "react";
import { formatCapturedAgo, formatCapturedAt } from "./formatCapturedAgo";
import type { ManualProductInput, ProductUpdateInput } from "./api";
import { PhotoLightbox } from "./PhotoLightbox";
import { LocationLabelButton } from "./LocationLabelButton";
import { StoreLink } from "./StoreLink";
import type { PriceInsight, Product } from "./types";

function formatPrice(price: number | null | undefined, currency = "CAD") {
  if (price == null) return "—";
  return new Intl.NumberFormat("en-CA", {
    style: "currency",
    currency,
  }).format(price);
}

function formatDelta(delta: number | null | undefined) {
  if (delta == null || delta === 0) return null;
  const sign = delta > 0 ? "+" : "";
  return `${sign}${formatPrice(delta)}`;
}

function insightLabel(insight: PriceInsight) {
  if (insight.insight_type === "other_store") {
    return insight.store ? `At ${insight.store}` : "At another store";
  }
  if (insight.insight_type === "same_store_history") {
    return "Previously at this store";
  }
  return "Earlier sighting";
}

interface ProductEditFormProps {
  product: Product;
  saving: boolean;
  onSave: (updates: ProductUpdateInput) => void;
  onCancel: () => void;
}

function ProductEditForm({ product, saving, onSave, onCancel }: ProductEditFormProps) {
  const [name, setName] = useState(product.product_name);
  const [price, setPrice] = useState(product.price?.toString() ?? "");
  const [unit, setUnit] = useState(product.unit ?? "");
  const [unitPrice, setUnitPrice] = useState(product.unit_price?.toString() ?? "");
  const [barcode, setBarcode] = useState(product.barcode ?? "");

  return (
    <form
      className="product-edit-form"
      onSubmit={(event) => {
        event.preventDefault();
        onSave({
          product_name: name.trim(),
          price: price.trim() ? Number(price) : null,
          unit: unit.trim() || undefined,
          unit_price: unitPrice.trim() ? Number(unitPrice) : null,
          barcode: barcode.trim() || undefined,
        });
      }}
    >
      <label>
        Name
        <input value={name} onChange={(e) => setName(e.target.value)} required />
      </label>
      <label>
        Price
        <input value={price} onChange={(e) => setPrice(e.target.value)} inputMode="decimal" />
      </label>
      <label>
        Unit
        <input value={unit} onChange={(e) => setUnit(e.target.value)} placeholder="EA, lb, 100g" />
      </label>
      <label>
        Unit price
        <input value={unitPrice} onChange={(e) => setUnitPrice(e.target.value)} inputMode="decimal" />
      </label>
      <label>
        Barcode
        <input value={barcode} onChange={(e) => setBarcode(e.target.value)} />
      </label>
      <div className="product-edit-actions">
        <button
          type="button"
          className="product-form-btn product-form-btn--secondary"
          onClick={onCancel}
          disabled={saving}
        >
          Cancel
        </button>
        <button type="submit" className="product-form-btn product-form-btn--primary" disabled={saving}>
          {saving ? "Saving…" : "Save"}
        </button>
      </div>
    </form>
  );
}

interface ManualProductFormProps {
  saving: boolean;
  onSave: (product: ManualProductInput) => void;
  onCancel: () => void;
}

function ManualProductForm({ saving, onSave, onCancel }: ManualProductFormProps) {
  const [name, setName] = useState("");
  const [price, setPrice] = useState("");
  const [unit, setUnit] = useState("");

  return (
    <form
      className="product-edit-form"
      onSubmit={(event) => {
        event.preventDefault();
        onSave({
          product_name: name.trim(),
          price: price.trim() ? Number(price) : null,
          unit: unit.trim() || undefined,
        });
      }}
    >
      <label>
        Product name
        <input value={name} onChange={(e) => setName(e.target.value)} required />
      </label>
      <label>
        Price
        <input value={price} onChange={(e) => setPrice(e.target.value)} inputMode="decimal" />
      </label>
      <label>
        Unit
        <input value={unit} onChange={(e) => setUnit(e.target.value)} />
      </label>
      <div className="product-edit-actions">
        <button
          type="button"
          className="product-form-btn product-form-btn--secondary"
          onClick={onCancel}
          disabled={saving}
        >
          Cancel
        </button>
        <button
          type="submit"
          className="product-form-btn product-form-btn--secondary"
          disabled={saving || !name.trim()}
        >
          {saving ? "Saving…" : "Add"}
        </button>
      </div>
    </form>
  );
}

function PriceInsights({ insights }: { insights: PriceInsight[] }) {
  if (!insights.length) return null;
  return (
    <div className="price-insights">
      <h3>Price history</h3>
      <ul>
        {insights.map((insight) => (
          <li key={`${insight.product_id}-${insight.captured_at ?? insight.price}`}>
            <span className="price-insights-label">{insightLabel(insight)}</span>
            <span className="price-insights-value">{formatPrice(insight.price)}</span>
            {insight.store && <span className="price-insights-store">{insight.store}</span>}
            {insight.captured_at && (
              <span className="price-insights-when" title={formatCapturedAt(insight.captured_at) ?? undefined}>
                {formatCapturedAgo(insight.captured_at)}
              </span>
            )}
            {formatDelta(insight.price_delta) && (
              <span className="price-insights-delta">{formatDelta(insight.price_delta)}</span>
            )}
          </li>
        ))}
      </ul>
    </div>
  );
}

function EditIcon() {
  return (
    <svg viewBox="0 0 24 24" width="14" height="14" aria-hidden="true">
      <path
        fill="none"
        stroke="currentColor"
        strokeWidth="1.8"
        strokeLinecap="round"
        strokeLinejoin="round"
        d="M12 20h9"
      />
      <path
        fill="none"
        stroke="currentColor"
        strokeWidth="1.8"
        strokeLinecap="round"
        strokeLinejoin="round"
        d="M16.5 3.5a2.1 2.1 0 1 1 3 3L7 19l-4 1 1-4L16.5 3.5Z"
      />
    </svg>
  );
}

function CloseIcon() {
  return (
    <svg viewBox="0 0 24 24" width="14" height="14" aria-hidden="true">
      <path
        fill="none"
        stroke="currentColor"
        strokeWidth="2"
        strokeLinecap="round"
        d="M7 7l10 10M17 7 7 17"
      />
    </svg>
  );
}

export function ProductCard({
  product,
  imgSrc,
  onDelete,
  deleting,
  onLabelLocation,
  onEdit,
  onReextract,
  onAddManual,
  reextracting,
  saving,
  compact: compactProp,
  selectionMode,
  selected,
  onToggleSelect,
}: {
  product: Product;
  imgSrc: string;
  onDelete?: (productId: string) => void;
  deleting?: boolean;
  onLabelLocation?: (product: Product) => void;
  onEdit?: (productId: string, updates: ProductUpdateInput) => Promise<void>;
  onReextract?: (imageId: string) => Promise<void>;
  onAddManual?: (imageId: string, product: ManualProductInput) => Promise<void>;
  reextracting?: boolean;
  saving?: boolean;
  compact?: boolean;
  selectionMode?: boolean;
  selected?: boolean;
  onToggleSelect?: (productId: string) => void;
}) {
  const isEmpty = product.extraction_empty === true;
  const { store } = product.location;
  const needsLabel = store === "Unknown store" || !product.location.store_location_id;
  const [lightboxOpen, setLightboxOpen] = useState(false);
  const [confirming, setConfirming] = useState(false);
  const [editing, setEditing] = useState(false);
  const [addingManual, setAddingManual] = useState(false);
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

  function handleToggleSelect(e?: React.MouseEvent) {
    e?.stopPropagation();
    e?.preventDefault();
    onToggleSelect?.(product.id);
  }

  function handleEditClick(e: React.MouseEvent) {
    e.stopPropagation();
    e.preventDefault();
    setEditing(true);
  }

  const compact = compactProp === true;
  const selecting = selectionMode === true;
  const displayName = isEmpty ? "No products extracted" : product.product_name;

  return (
    <article
      className={`card${isEmpty ? " card--empty" : ""}${compact ? " card--compact" : ""}${selected ? " card--selected" : ""}`}
      onClick={selecting ? () => handleToggleSelect() : undefined}
    >
      {selecting && onToggleSelect && (
        <label className="card-select" onClick={(e) => e.stopPropagation()}>
          <input
            type="checkbox"
            checked={!!selected}
            onChange={() => handleToggleSelect()}
            aria-label={`Select ${displayName}`}
          />
        </label>
      )}
      <button
        type="button"
        className="card-image-wrap"
        aria-label={
          selecting
            ? `Toggle selection for ${displayName}`
            : isEmpty
              ? "View photo with no extracted products"
              : `View full photo of ${product.product_name}`
        }
        onClick={(e) => {
          if (selecting) {
            handleToggleSelect(e);
            return;
          }
          setLightboxOpen(true);
        }}
      >
        <img src={imgSrc} alt={product.product_name} loading="lazy" />
        {product.is_special && <span className="badge special">Special</span>}
        {isEmpty && <span className="badge empty">No products</span>}
      </button>
      {!selecting && lightboxOpen && (
        <PhotoLightbox
          src={imgSrc}
          alt={product.product_name}
          onClose={() => setLightboxOpen(false)}
        />
      )}
      <div className="card-body">
        {compact ? (
          <>
            <h2 className="card-compact-title">{displayName}</h2>
            {!isEmpty && (
              <p className="card-compact-price">
                {formatPrice(product.price, product.price_currency)}
                {product.unit ? ` / ${product.unit}` : ""}
              </p>
            )}
            <p className="card-compact-store">{store}</p>
          </>
        ) : (
          <>
        <div className="card-title-row">
          <h2>{isEmpty ? "No products extracted" : product.product_name}</h2>
          {(onDelete || (!isEmpty && onEdit && !editing)) && (
            <div className="card-actions">
              {!isEmpty && onEdit && !editing && !confirming && (
                <button
                  type="button"
                  className="card-icon-btn card-icon-btn--edit"
                  aria-label={`Edit ${product.product_name}`}
                  title="Edit"
                  onClick={handleEditClick}
                >
                  <EditIcon />
                </button>
              )}
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
                      className="card-icon-btn card-icon-btn--delete"
                      aria-label={isEmpty ? "Delete photo" : `Delete ${product.product_name}`}
                      title="Delete"
                      disabled={deleting}
                      onClick={handleDeleteClick}
                    >
                      <CloseIcon />
                    </button>
                  )}
                </div>
              )}
            </div>
          )}
        </div>

        {isEmpty ? (
          <div className="empty-extraction-actions">
            <p className="subtitle">
              No priced products found in this photo. Retry or add one manually.
            </p>
            <div className="empty-extraction-buttons">
              {onReextract && (
                <button
                  type="button"
                  className="empty-extraction-btn empty-extraction-btn--secondary"
                  disabled={reextracting}
                  onClick={() => void onReextract(product.image_id)}
                >
                  {reextracting ? "Trying again…" : "Try again"}
                </button>
              )}
              {onAddManual && !addingManual && (
                <button
                  type="button"
                  className="empty-extraction-btn empty-extraction-btn--secondary"
                  onClick={() => setAddingManual(true)}
                >
                  Add manually
                </button>
              )}
            </div>
            {addingManual && onAddManual && (
              <ManualProductForm
                saving={!!saving}
                onCancel={() => setAddingManual(false)}
                onSave={async (manualProduct) => {
                  await onAddManual(product.image_id, manualProduct);
                  setAddingManual(false);
                }}
              />
            )}
          </div>
        ) : (
          <>
            {product.product_name_zh && <p className="zh">{product.product_name_zh}</p>}
            {editing && onEdit ? (
              <ProductEditForm
                product={product}
                saving={!!saving}
                onCancel={() => setEditing(false)}
                onSave={async (updates) => {
                  await onEdit(product.id, updates);
                  setEditing(false);
                }}
              />
            ) : (
              <>
                <div className="price-row">
                  <span className="price">{formatPrice(product.price, product.price_currency)}</span>
                  {product.unit && <span className="unit">/ {product.unit}</span>}
                  {product.regular_price != null && product.is_special && (
                    <span className="was">was {formatPrice(product.regular_price)}</span>
                  )}
                </div>
                {product.promo && <p className="promo">{product.promo}</p>}
                {product.price_insights && product.price_insights.length > 0 && (
                  <PriceInsights insights={product.price_insights} />
                )}
              </>
            )}
          </>
        )}

        <dl className="meta">
          {!isEmpty && product.brand && (
            <>
              <dt>Brand</dt>
              <dd>{product.brand}</dd>
            </>
          )}
          {!isEmpty && product.size && (
            <>
              <dt>Size</dt>
              <dd>{product.size}</dd>
            </>
          )}
          {!isEmpty && product.unit_price != null && (
            <>
              <dt>Unit price</dt>
              <dd>
                {formatPrice(product.unit_price)}/{product.unit ?? "unit"}
              </dd>
            </>
          )}
          {!isEmpty && product.barcode && (
            <>
              <dt>Barcode</dt>
              <dd className="mono">{product.barcode}</dd>
            </>
          )}
          {!isEmpty && product.packed_on && (
            <>
              <dt>Packed on</dt>
              <dd>{product.packed_on}</dd>
            </>
          )}
          <dt>Store</dt>
          <dd className="store-meta-row">
            <StoreLink location={product.location} />
            {onLabelLocation && (
              <LocationLabelButton
                needsLabel={needsLabel}
                onClick={() => onLabelLocation(product)}
              />
            )}
          </dd>
          {!isEmpty && (
            <>
              <dt>Category</dt>
              <dd>{product.category}</dd>
            </>
          )}
          {capturedAgo && (
            <>
              <dt>Taken</dt>
              <dd title={capturedLabel ?? undefined}>{capturedAgo}</dd>
            </>
          )}
        </dl>
          </>
        )}
      </div>
    </article>
  );
}
