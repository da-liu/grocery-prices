import {
  Check,
  Hash,
  Pencil,
  Plus,
  SquareCheck,
  Trash2,
  Undo2,
  X,
} from "lucide-react";
import { useState } from "react";
import { formatCapturedAgo, formatCapturedAt } from "@/shared/lib/formatCapturedAgo";
import { formatPrice } from "@/shared/lib/formatPrice";
import type { ManualProductInput, ProductUpdateInput } from "@/shared/api/api";
import { PhotoLightbox } from "./PhotoLightbox";
import { LocationLabelButton } from "./LocationLabelButton";
import { StoreLink } from "@/features/stores/StoreLink";
import { photoGroupLinkLabel, resolveRelatedProducts } from "./browseQuery";
import { useCatalog } from "./CatalogContext";
import { ExtractionProgressBar } from "@/features/upload/ExtractionProgressBar";
import type { ExtractBackend } from "@/shared/api/api";
import type { Product } from "@/shared/types/types";
import "./ProductCard.css";

type OtherValue = string | number | boolean | null;
type OtherValueType = "string" | "number" | "boolean";
type OtherRow = {
  id: string;
  key: string;
  valueText: string;
  typeOverride: "auto" | OtherValueType;
  removed?: boolean;
};

function formatOtherKey(key: string) {
  return key
    .replace(/_/g, " ")
    .replace(/\b\w/g, (char) => char.toUpperCase());
}

function formatOtherValue(value: string | number | boolean | null) {
  if (typeof value === "boolean") {
    return value ? "Yes" : "No";
  }
  if (typeof value === "number") {
    return String(value);
  }
  return String(value);
}

function otherEntries(other: Product["other"]) {
  return Object.entries(other ?? {}).filter(
    ([key, value]) => key !== "is_special" && value != null && value !== "",
  );
}

function otherFlag(product: Product, key: string) {
  return product.other?.[key] === true;
}

function otherNumber(product: Product, key: string) {
  const value = product.other?.[key];
  return typeof value === "number" ? value : null;
}

function otherString(product: Product, key: string) {
  const value = product.other?.[key];
  return value == null ? "" : String(value);
}

function safeParseNumber(text: string): { ok: true; value: number } | { ok: false } {
  const trimmed = text.trim();
  if (!trimmed) return { ok: false };
  const num = Number(trimmed);
  return Number.isFinite(num) ? { ok: true, value: num } : { ok: false };
}

function safeParseBoolean(text: string): { ok: true; value: boolean } | { ok: false } {
  const trimmed = text.trim().toLowerCase();
  if (trimmed === "true") return { ok: true, value: true };
  if (trimmed === "false") return { ok: true, value: false };
  return { ok: false };
}

function inferOtherValueType(valueText: string): OtherValueType {
  const trimmed = valueText.trim();
  if (!trimmed) return "string";
  if (safeParseBoolean(trimmed).ok) return "boolean";
  if (safeParseNumber(trimmed).ok) return "number";
  return "string";
}

function effectiveOtherType(row: OtherRow): OtherValueType {
  return row.typeOverride === "auto" ? inferOtherValueType(row.valueText) : row.typeOverride;
}

function nextTypeOverride(current: OtherRow["typeOverride"]): OtherRow["typeOverride"] {
  const sequence: OtherRow["typeOverride"][] = ["auto", "string", "number", "boolean"];
  const idx = sequence.indexOf(current);
  return sequence[(idx + 1) % sequence.length];
}

function typeLabel(type: OtherValueType) {
  if (type === "string") return "String";
  if (type === "number") return "Number";
  return "Boolean";
}

function toOtherRow(key: string, value: OtherValue, id: string): OtherRow {
  const valueText = value == null ? "" : String(value);
  return { id, key, valueText, typeOverride: "auto" };
}

function normalizeOtherKey(raw: string) {
  return raw.trim();
}

function buildOtherPatchFromRows(rows: OtherRow[]): { patch: Record<string, OtherValue>; hasErrors: boolean } {
  const patch: Record<string, OtherValue> = {};
  let hasErrors = false;
  const seenKeys = new Set<string>();

  for (const row of rows) {
    const key = normalizeOtherKey(row.key);
    if (!key) {
      hasErrors = true;
      continue;
    }
    if (seenKeys.has(key)) {
      hasErrors = true;
      continue;
    }
    seenKeys.add(key);
    if (row.removed) {
      patch[key] = null;
      continue;
    }

    const text = row.valueText;
    if (!text.trim()) {
      patch[key] = null;
      continue;
    }

    const type = effectiveOtherType(row);
    if (type === "boolean") {
      const parsed = safeParseBoolean(text);
      if (!parsed.ok) {
        hasErrors = true;
        continue;
      }
      patch[key] = parsed.value;
      continue;
    }

    if (type === "number") {
      const parsed = safeParseNumber(text);
      if (!parsed.ok) {
        hasErrors = true;
        continue;
      }
      patch[key] = parsed.value;
      continue;
    }

    patch[key] = text.trim();
  }

  return { patch, hasErrors };
}

interface ProductEditFormProps {
  product: Product;
  saving: boolean;
  formId: string;
  onSave: (updates: ProductUpdateInput) => void;
  onCancel: () => void;
}

function ProductEditForm({ product, saving, formId, onSave, onCancel }: ProductEditFormProps) {
  const reservedOtherKeys = new Set(["barcode", "is_special", "regular_price"]);
  const [name, setName] = useState(product.product_name);
  const [price, setPrice] = useState(product.price?.toString() ?? "");
  const [unit, setUnit] = useState(product.unit ?? "");
  const [unitPrice, setUnitPrice] = useState(product.unit_price?.toString() ?? "");
  const [barcode, setBarcode] = useState(otherString(product, "barcode"));
  const [category, setCategory] = useState(product.category ?? "");
  const [isSpecial, setIsSpecial] = useState(otherFlag(product, "is_special"));
  const [regularPrice, setRegularPrice] = useState(
    otherNumber(product, "regular_price")?.toString() ?? "",
  );
  const [otherRows, setOtherRows] = useState<OtherRow[]>(() => {
    const entries = Object.entries(product.other ?? {}).filter(([key]) => !reservedOtherKeys.has(key));
    return entries.map(([key, value], idx) => toOtherRow(key, value as OtherValue, `seed-${idx}`));
  });

  const priceInvalid = price.trim() !== "" && !safeParseNumber(price).ok;
  const unitPriceInvalid = unitPrice.trim() !== "" && !safeParseNumber(unitPrice).ok;
  const regularPriceInvalid = regularPrice.trim() !== "" && !safeParseNumber(regularPrice).ok;
  const otherPatch = buildOtherPatchFromRows(otherRows);

  const hasNumberErrors =
    priceInvalid || unitPriceInvalid || regularPriceInvalid || otherPatch.hasErrors;
  const saveDisabled = saving || !name.trim() || hasNumberErrors;

  const seenKeys = new Set<string>();
  const duplicateKeys = new Set<string>();
  otherRows.forEach((row) => {
    if (row.removed) return;
    const key = normalizeOtherKey(row.key);
    if (!key) return;
    if (seenKeys.has(key)) {
      duplicateKeys.add(key);
    } else {
      seenKeys.add(key);
    }
  });

  return (
    <form
      id={formId}
      className="product-edit-form"
      onSubmit={(event) => {
        event.preventDefault();
        if (hasNumberErrors) return;

        const nextOther: Record<string, OtherValue> = {
          ...(product.other ?? {}),
          ...otherPatch.patch,
          barcode: barcode.trim() ? barcode.trim() : null,
          is_special: isSpecial,
          regular_price: regularPrice.trim() ? Number(regularPrice.trim()) : null,
        };

        onSave({
          product_name: name.trim(),
          price: price.trim() ? Number(price.trim()) : null,
          unit: unit.trim() ? unit.trim() : null,
          unit_price: unitPrice.trim() ? Number(unitPrice.trim()) : null,
          category: category.trim() ? category.trim() : null,
          other: nextOther,
        });
      }}
    >
      <label>
        Name
        <input value={name} onChange={(e) => setName(e.target.value)} required />
      </label>
      <label>
        Price
        <input
          className={priceInvalid ? "input--invalid" : ""}
          value={price}
          onChange={(e) => setPrice(e.target.value)}
          inputMode="decimal"
        />
      </label>
      <label>
        Unit
        <input value={unit} onChange={(e) => setUnit(e.target.value)} placeholder="EA, lb, 100g" />
      </label>
      <label>
        Unit price
        <input
          className={unitPriceInvalid ? "input--invalid" : ""}
          value={unitPrice}
          onChange={(e) => setUnitPrice(e.target.value)}
          inputMode="decimal"
        />
      </label>
      <label>
        Category
        <input value={category} onChange={(e) => setCategory(e.target.value)} placeholder="Produce, Snacks, ..." />
      </label>
      <label className="product-edit-checkbox">
        <span>Special</span>
        <input type="checkbox" checked={isSpecial} onChange={(e) => setIsSpecial(e.target.checked)} />
      </label>
      <label>
        Regular price
        <input
          className={regularPriceInvalid ? "input--invalid" : ""}
          value={regularPrice}
          onChange={(e) => setRegularPrice(e.target.value)}
          inputMode="decimal"
          placeholder="Used when Special is on"
        />
      </label>
      <label>
        Barcode
        <input value={barcode} onChange={(e) => setBarcode(e.target.value)} placeholder="Leave blank to clear" />
      </label>

      <fieldset className="product-edit-other">
        <legend>Other fields</legend>
        <div className="other-editor">
          {otherRows.map((row) => {
            const rowType = effectiveOtherType(row);
            const typeSuffixTitle =
              row.typeOverride === "auto"
                ? `${typeLabel(rowType)} (inferred, click to override)`
                : `${typeLabel(rowType)} (override, click to change)`;

            const keyInvalid = (!row.key.trim() && row.valueText.trim() !== "") || duplicateKeys.has(normalizeOtherKey(row.key));
            const valueInvalid =
              row.valueText.trim() !== "" &&
              ((rowType === "number" && !safeParseNumber(row.valueText).ok) ||
                (rowType === "boolean" && !safeParseBoolean(row.valueText).ok));
            const rowInvalid = keyInvalid || valueInvalid;

            return (
            <div key={row.id} className={`other-row${row.removed ? " other-row--removed" : ""}`}>
              <div className={`other-kv-composite${rowInvalid && !row.removed ? " other-kv-composite--invalid" : ""}`}>
                <input
                  className="other-key"
                  value={row.key}
                  onChange={(e) =>
                    setOtherRows((rows) => rows.map((r) => (r.id === row.id ? { ...r, key: e.target.value } : r)))
                  }
                  placeholder="key"
                  disabled={row.removed}
                  aria-label="Key"
                />
                <span className="other-kv-divider" aria-hidden="true" />
                <input
                  className="other-value"
                  value={row.valueText}
                  onChange={(e) =>
                    setOtherRows((rows) =>
                      rows.map((r) => (r.id === row.id ? { ...r, valueText: e.target.value } : r)),
                    )
                  }
                  placeholder={
                    rowType === "number"
                      ? "123.45"
                      : rowType === "boolean"
                        ? "true / false"
                        : "value"
                  }
                  inputMode={rowType === "number" ? "decimal" : undefined}
                  disabled={row.removed}
                  aria-label="Value"
                />
                <button
                  type="button"
                  className={`other-type-suffix ${row.typeOverride === "auto" ? "other-type-suffix--auto" : "other-type-suffix--override"}`}
                  onClick={() =>
                    setOtherRows((rows) =>
                      rows.map((r) =>
                        r.id === row.id ? { ...r, typeOverride: nextTypeOverride(r.typeOverride) } : r,
                      ),
                    )
                  }
                  disabled={row.removed}
                  title={typeSuffixTitle}
                  aria-label={typeSuffixTitle}
                >
                  <OtherTypeIcon type={rowType} />
                </button>
              </div>
              <button
                type="button"
                className="other-remove-btn"
                onClick={() =>
                  setOtherRows((rows) =>
                    rows.map((r) => (r.id === row.id ? { ...r, removed: !r.removed } : r)),
                  )
                }
                aria-label={row.removed ? "Undo remove" : "Remove field"}
                title={row.removed ? "Undo" : "Remove"}
              >
                {row.removed ? <Undo2 size={11} aria-hidden /> : <X size={11} aria-hidden />}
              </button>
            </div>
            );
          })}
          <button
            type="button"
            className="other-add"
            onClick={() =>
              setOtherRows((rows) =>
                rows.concat({
                  id: `new-${rows.length}-${Date.now()}`,
                  key: "",
                  valueText: "",
                  typeOverride: "auto",
                }),
              )
            }
          >
            <Plus size={12} aria-hidden />
            <span>Add field</span>
          </button>
        </div>
      </fieldset>

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
          className="product-form-btn product-form-btn--primary"
          disabled={saveDisabled}
        >
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

function OtherTypeIcon({ type }: { type: OtherValueType }) {
  if (type === "number") return <Hash size={14} aria-hidden />;
  if (type === "boolean") return <SquareCheck size={14} aria-hidden />;
  return (
    <span className="other-type-label" aria-hidden>
      Az
    </span>
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
  reextractStartedAt,
  extractBackend,
  saving,
  compact: compactProp,
  selectionMode,
  selected,
  onToggleSelect,
  onNavigateToPhotoGroup,
  photoGroupProductCount,
  highlighted,
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
  reextractStartedAt?: number;
  extractBackend?: ExtractBackend;
  saving?: boolean;
  compact?: boolean;
  selectionMode?: boolean;
  selected?: boolean;
  onToggleSelect?: (productId: string) => void;
  onNavigateToPhotoGroup?: (imageId: string, productId: string) => void;
  photoGroupProductCount?: number;
  highlighted?: boolean;
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
  const catalog = useCatalog();
  const relatedProducts = resolveRelatedProducts(product, catalog.productsById);
  const editFormId = `product-edit-form-${product.id}`;

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
      id={`product-${product.id}`}
      className={`card${isEmpty ? " card--empty" : ""}${compact ? " card--compact" : ""}${selected ? " card--selected" : ""}${highlighted ? " card--highlight" : ""}`}
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
        {otherFlag(product, "is_special") && <span className="badge special">Special</span>}
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
                {formatPrice(product.price)}
                {product.unit ? ` / ${product.unit}` : ""}
              </p>
            )}
            <p className="card-compact-store">{store}</p>
          </>
        ) : (
          <>
        <div className="card-title-row">
          <h2>{isEmpty ? "No products extracted" : product.product_name}</h2>
          {(onDelete || (!isEmpty && onEdit)) && (
            <div className="card-actions">
              {!isEmpty && onEdit && !confirming && (
                <>
                  {editing ? (
                    <>
                      <button
                        type="button"
                        className="card-icon-btn card-icon-btn--edit"
                        aria-label={`Cancel editing ${product.product_name}`}
                        title="Cancel"
                        onClick={(e) => {
                          e.stopPropagation();
                          e.preventDefault();
                          setEditing(false);
                        }}
                        disabled={!!saving}
                      >
                        <X size={14} aria-hidden />
                      </button>
                      <button
                        type="submit"
                        form={editFormId}
                        className="card-icon-btn card-icon-btn--edit"
                        aria-label={`Save ${product.product_name}`}
                        title="Save"
                        onClick={(e) => {
                          e.stopPropagation();
                        }}
                        disabled={!!saving}
                      >
                        <Check size={14} aria-hidden />
                      </button>
                    </>
                  ) : (
                    <button
                      type="button"
                      className="card-icon-btn card-icon-btn--edit"
                      aria-label={`Edit ${product.product_name}`}
                      title="Edit"
                      onClick={handleEditClick}
                    >
                      <Pencil size={14} aria-hidden />
                    </button>
                  )}
                </>
              )}
              {onDelete && !editing && (
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
                      <Trash2 size={14} aria-hidden />
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
                  {reextracting ? "Reading prices…" : "Try again"}
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
            {reextracting && reextractStartedAt != null && (
              <ExtractionProgressBar
                startedAt={reextractStartedAt}
                backend={extractBackend}
              />
            )}
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
            {editing && onEdit ? (
              <ProductEditForm
                product={product}
                saving={!!saving}
                formId={editFormId}
                onCancel={() => setEditing(false)}
                onSave={async (updates) => {
                  await onEdit(product.id, updates);
                  setEditing(false);
                }}
              />
            ) : (
              <>
                <div className="price-row">
                  <span className="price">{formatPrice(product.price)}</span>
                  {product.unit && <span className="unit">/ {product.unit}</span>}
                  {otherNumber(product, "regular_price") != null && otherFlag(product, "is_special") && (
                    <span className="was">
                      was {formatPrice(otherNumber(product, "regular_price"))}
                    </span>
                  )}
                </div>
              </>
            )}
          </>
        )}

        <dl className="meta">
          {!isEmpty &&
            otherEntries(product.other).flatMap(([key, value]) => [
              <dt key={`${key}-label`}>{formatOtherKey(key)}</dt>,
              <dd key={`${key}-value`}>{formatOtherValue(value)}</dd>,
            ])}
          {!isEmpty && product.unit_price != null && (
            <>
              <dt>Unit price</dt>
              <dd>
                {formatPrice(product.unit_price)}/{product.unit ?? "unit"}
              </dd>
            </>
          )}
          <dt>Store</dt>
          <dd className="store-meta-row">
            <span className="store-meta-name">
              <StoreLink location={product.location} />
            </span>
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
          {onNavigateToPhotoGroup && (
            <>
              <dt>Photo</dt>
              <dd>
                <button
                  type="button"
                  className="meta-link"
                  onClick={(e) => {
                    e.stopPropagation();
                    onNavigateToPhotoGroup(product.image_id, product.id);
                  }}
                >
                  {photoGroupLinkLabel(photoGroupProductCount ?? 1)}
                </button>
              </dd>
            </>
          )}
        </dl>
        {relatedProducts.length > 0 && (
          <section className="related-products-section">
            <h3 className="related-products-heading">Related products</h3>
            <ul className="related-products-list">
              {relatedProducts.map(({ product: related, score }) => (
                <li key={related.id}>
                  <button
                    type="button"
                    className="related-product-item"
                    onClick={(e) => {
                      e.stopPropagation();
                      catalog.navigateToProduct(related.id);
                    }}
                  >
                    <span className="related-product-main">
                      <span className="related-product-name">{related.product_name}</span>
                      {related.price != null && (
                        <span className="related-product-price">{formatPrice(related.price)}</span>
                      )}
                    </span>
                    <span className="related-product-meta">
                      {related.location.store}
                      {related.captured_at ? ` · ${formatCapturedAgo(related.captured_at)}` : ""}
                      {` · ${Math.round(score * 100)}% match`}
                    </span>
                  </button>
                </li>
              ))}
            </ul>
          </section>
        )}
          </>
        )}
      </div>
    </article>
  );
}
