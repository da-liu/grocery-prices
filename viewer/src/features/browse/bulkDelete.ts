import type { Product } from "@/shared/types/types";

export interface BulkDeleteImpact {
  photosRemoved: number;
  validIds: string[];
}

export function computeBulkDeleteImpact(
  catalog: Product[],
  selectedIds: ReadonlySet<string>,
): BulkDeleteImpact {
  const catalogIds = new Set(catalog.map((product) => product.id));
  const validIds = [...selectedIds].filter((id) => catalogIds.has(id));
  const validIdSet = new Set(validIds);

  const byImage = new Map<string, Product[]>();
  for (const product of catalog) {
    const list = byImage.get(product.image_id) ?? [];
    list.push(product);
    byImage.set(product.image_id, list);
  }

  let photosRemoved = 0;
  for (const allOnPhoto of byImage.values()) {
    if (allOnPhoto.length > 0 && allOnPhoto.every((product) => validIdSet.has(product.id))) {
      photosRemoved += 1;
    }
  }

  return { photosRemoved, validIds };
}
