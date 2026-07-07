import { describe, expect, it } from "vitest";
import { computeBulkDeleteImpact } from "./bulkDelete";
import type { Product } from "@/shared/types/types";

function makeProduct(overrides: Partial<Product> & Pick<Product, "id" | "image_id">): Product {
  return {
    image_path: "/x.jpg",
    product_name: "Item",
    price: 5,
    category: "grocery",
    location: { store: "Longos" },
    ...overrides,
  };
}

describe("computeBulkDeleteImpact", () => {
  it("counts photos removed when all products on a photo are selected", () => {
    const catalog: Product[] = [
      makeProduct({ id: "a", image_id: "img-1", product_name: "A" }),
      makeProduct({ id: "b", image_id: "img-1", product_name: "B" }),
      makeProduct({ id: "c", image_id: "img-2", product_name: "C" }),
    ];

    const impact = computeBulkDeleteImpact(catalog, new Set(["a", "b"]));

    expect(impact.validIds).toHaveLength(2);
    expect(impact.photosRemoved).toBe(1);
    expect(impact.validIds).toEqual(["a", "b"]);
  });

  it("does not count a photo when only a subset of its products are selected", () => {
    const catalog: Product[] = [
      makeProduct({ id: "a", image_id: "img-1", product_name: "A" }),
      makeProduct({ id: "b", image_id: "img-1", product_name: "B" }),
    ];

    const impact = computeBulkDeleteImpact(catalog, new Set(["a"]));

    expect(impact.validIds).toHaveLength(1);
    expect(impact.photosRemoved).toBe(0);
  });

  it("filters stale ids not in catalog", () => {
    const catalog: Product[] = [makeProduct({ id: "a", image_id: "img-1", product_name: "A" })];

    const impact = computeBulkDeleteImpact(catalog, new Set(["a", "missing"]));

    expect(impact.validIds).toEqual(["a"]);
  });

  it("returns zero counts for empty or stale-only selection", () => {
    const catalog: Product[] = [makeProduct({ id: "a", image_id: "img-1", product_name: "A" })];

    expect(computeBulkDeleteImpact(catalog, new Set())).toEqual({
      photosRemoved: 0,
      validIds: [],
    });
    expect(computeBulkDeleteImpact(catalog, new Set(["gone"]))).toEqual({
      photosRemoved: 0,
      validIds: [],
    });
  });
});
