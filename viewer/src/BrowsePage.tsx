import { ProductCard } from "./ProductCard";
import { productImageUrl } from "./api";
import type { ManualProductInput, ProductUpdateInput } from "./api";
import type { Product } from "./types";

import type { GridColumns } from "./browseQuery";

export function BrowsePage({
  products,
  catalogEmpty,
  onStartUpload,
  onDeleteProduct,
  deletingId,
  onLabelLocation,
  onEditProduct,
  onReextractPhoto,
  onAddManualProduct,
  reextractingId,
  savingId,
  selectionMode,
  selectedIds,
  onToggleSelect,
  gridColumns,
}: {
  products: Product[];
  catalogEmpty: boolean;
  onStartUpload?: () => void;
  onDeleteProduct?: (productId: string) => void;
  deletingId?: string | null;
  onLabelLocation?: (product: Product) => void;
  onEditProduct?: (productId: string, updates: ProductUpdateInput) => Promise<void>;
  onReextractPhoto?: (imageId: string) => Promise<void>;
  onAddManualProduct?: (imageId: string, product: ManualProductInput) => Promise<void>;
  reextractingId?: string | null;
  savingId?: string | null;
  selectionMode?: boolean;
  selectedIds?: ReadonlySet<string>;
  onToggleSelect?: (productId: string) => void;
  gridColumns: GridColumns;
}) {
  if (catalogEmpty) {
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

  const compact = selectionMode || gridColumns > 1;
  const gridClass = `grid grid--cols-${gridColumns}${compact ? " grid--compact" : ""}`;

  return (
    <>
      <main className={gridClass}>
        {products.map((product) => (
          <ProductCard
            key={product.id}
            product={product}
            imgSrc={productImageUrl(product.image_id)}
            onDelete={selectionMode ? undefined : onDeleteProduct}
            deleting={deletingId === product.id}
            onLabelLocation={selectionMode ? undefined : onLabelLocation}
            onEdit={selectionMode ? undefined : onEditProduct}
            onReextract={selectionMode ? undefined : onReextractPhoto}
            onAddManual={selectionMode ? undefined : onAddManualProduct}
            reextracting={reextractingId === product.image_id}
            saving={savingId === product.id}
            compact={compact}
            selectionMode={selectionMode}
            selected={selectedIds?.has(product.id)}
            onToggleSelect={onToggleSelect}
          />
        ))}
      </main>

      {products.length === 0 && <p className="status">No products match your filters.</p>}
    </>
  );
}
