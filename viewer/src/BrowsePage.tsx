import { ProductCard } from "./ProductCard";
import { PhotoGroupCard } from "./PhotoGroupCard";
import { productImageUrl, type ExtractBackend } from "./api";
import type { ManualProductInput, ProductUpdateInput } from "./api";
import type { Product } from "./types";

import { groupProductsByImageId, type GridColumns, type ViewMode } from "./browseQuery";

export function BrowsePage({
  products,
  catalogEmpty,
  viewMode,
  onStartUpload,
  onDeleteProduct,
  deletingId,
  onLabelLocation,
  onEditProduct,
  onReextractPhoto,
  onAddManualProduct,
  reextractingId,
  reextractStartedAt,
  extractBackend,
  savingId,
  selectionMode,
  selectedIds,
  onToggleSelect,
  gridColumns,
  onNavigateToProduct,
  onNavigateToPhotoGroup,
  photoGroupSizes,
  highlightProductId,
  highlightPhotoGroupId,
}: {
  products: Product[];
  catalogEmpty: boolean;
  viewMode: ViewMode;
  onStartUpload?: () => void;
  onDeleteProduct?: (productId: string) => void;
  deletingId?: string | null;
  onLabelLocation?: (product: Product) => void;
  onEditProduct?: (productId: string, updates: ProductUpdateInput) => Promise<void>;
  onReextractPhoto?: (imageId: string) => Promise<void>;
  onAddManualProduct?: (imageId: string, product: ManualProductInput) => Promise<void>;
  reextractingId?: string | null;
  reextractStartedAt?: number | null;
  extractBackend?: ExtractBackend;
  savingId?: string | null;
  selectionMode?: boolean;
  selectedIds?: ReadonlySet<string>;
  onToggleSelect?: (productId: string) => void;
  gridColumns: GridColumns;
  onNavigateToProduct?: (productId: string) => void;
  onNavigateToPhotoGroup?: (imageId: string, productId: string) => void;
  photoGroupSizes?: ReadonlyMap<string, number>;
  highlightProductId?: string | null;
  highlightPhotoGroupId?: string | null;
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

  const compact = selectionMode || gridColumns >= 3;
  const gridClass = `grid grid--cols-${gridColumns}${compact ? " grid--compact" : ""}`;

  if (viewMode === "photos" && !selectionMode) {
    const groups = groupProductsByImageId(products);
    return (
      <main className="grid grid--photo-groups">
        {groups.map((group) => (
          <PhotoGroupCard
            key={group.imageId}
            group={group}
            onNavigateToProduct={onNavigateToProduct}
            highlightProductId={highlightProductId}
            highlighted={highlightPhotoGroupId === group.imageId}
          />
        ))}
      </main>
    );
  }

  return (
    <main className={gridClass}>
      {products.map((product) => (
        <ProductCard
          key={product.id}
          product={product}
          imgSrc={productImageUrl(product.image_id)}
          highlighted={highlightProductId === product.id}
          onDelete={selectionMode ? undefined : onDeleteProduct}
          deleting={deletingId === product.id}
          onLabelLocation={selectionMode ? undefined : onLabelLocation}
          onEdit={selectionMode ? undefined : onEditProduct}
          onReextract={selectionMode ? undefined : onReextractPhoto}
          onAddManual={selectionMode ? undefined : onAddManualProduct}
          onNavigateToPhotoGroup={onNavigateToPhotoGroup}
          photoGroupProductCount={photoGroupSizes?.get(product.image_id) ?? 1}
          reextracting={reextractingId === product.image_id}
          reextractStartedAt={
            reextractingId === product.image_id ? reextractStartedAt ?? undefined : undefined
          }
          extractBackend={extractBackend}
          saving={savingId === product.id}
          compact={compact}
          selectionMode={selectionMode}
          selected={selectedIds?.has(product.id)}
          onToggleSelect={onToggleSelect}
        />
      ))}
    </main>
  );
}
