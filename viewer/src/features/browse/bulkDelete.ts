import type { Product } from "@/shared/types/types";

export function computeBulkDeleteImpact(
  catalog: Product[],
  selectedIds: ReadonlySet<string>,
): { productCount: number; photosRemoved: number } {
  const byImage = new Map<string, Product[]>();
  for (const product of catalog) {
    const list = byImage.get(product.image_id) ?? [];
    list.push(product);
    byImage.set(product.image_id, list);
  }

  let photosRemoved = 0;
  for (const allOnPhoto of byImage.values()) {
    const selectedOnPhoto = allOnPhoto.filter((product) => selectedIds.has(product.id));
    if (selectedOnPhoto.length > 0 && selectedOnPhoto.length === allOnPhoto.length) {
      photosRemoved += 1;
    }
  }

  return { productCount: selectedIds.size, photosRemoved };
}
