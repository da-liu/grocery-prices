import { describe, expect, it } from "vitest";
import {
  EMPTY_BROWSE_QUERY,
  browseQueryToSearchParams,
  buildActiveChips,
  buildPriceHistogram,
  countActiveChips,
  filterProducts,
  getPriceExtents,
  photoGroupLinkLabel,
  parseBrowseQueryFromSearch,
  removeChip,
  sortProducts,
} from "./browseQuery";
import type { Product } from "./types";

function makeProduct(overrides: Partial<Product> & Pick<Product, "id" | "product_name">): Product {
  return {
    image_id: "img-1",
    image_path: "/x.jpg",
    price: 5,
    price_currency: "CAD",
    category: "grocery",
    location: { store: "Longos" },
    ...overrides,
  };
}

const sampleProducts: Product[] = [
  makeProduct({
    id: "1",
    product_name: "Apples",
    price: 3.99,
    category: "produce",
    captured_at: "2026-01-15T12:00:00Z",
    is_special: false,
    location: { store: "Longos", store_location_id: "s1" },
  }),
  makeProduct({
    id: "2",
    product_name: "Bananas",
    price: 1.99,
    category: "produce",
    captured_at: "2026-02-01T12:00:00Z",
    is_special: true,
    location: { store: "Costco" },
  }),
  makeProduct({
    id: "3",
    product_name: "Milk",
    price: null,
    category: "dairy",
    captured_at: "2026-01-20T12:00:00Z",
    location: { store: "Unknown store" },
  }),
  makeProduct({
    id: "4",
    product_name: "Bread",
    price: 4.5,
    category: "bakery",
    captured_at: "2025-12-01T12:00:00Z",
    is_special: false,
    location: { store: "Longos", store_location_id: "s1" },
  }),
];

describe("filterProducts", () => {
  it("filters by search text", () => {
    const rows = filterProducts(sampleProducts, EMPTY_BROWSE_QUERY, "banana");
    expect(rows.map((p) => p.id)).toEqual(["2"]);
  });

  it("filters by multiple stores", () => {
    const rows = filterProducts(
      sampleProducts,
      { ...EMPTY_BROWSE_QUERY, stores: ["Longos"] },
      "",
    );
    expect(rows.map((p) => p.id).sort()).toEqual(["1", "4"]);
  });

  it("filters by category", () => {
    const rows = filterProducts(
      sampleProducts,
      { ...EMPTY_BROWSE_QUERY, categories: ["dairy"] },
      "",
    );
    expect(rows.map((p) => p.id)).toEqual(["3"]);
  });

  it("filters by on sale flag", () => {
    const rows = filterProducts(
      sampleProducts,
      { ...EMPTY_BROWSE_QUERY, onSale: true },
      "",
    );
    expect(rows.map((p) => p.id)).toEqual(["2"]);
  });

  it("filters by has price", () => {
    const rows = filterProducts(
      sampleProducts,
      { ...EMPTY_BROWSE_QUERY, hasPrice: false },
      "",
    );
    expect(rows.map((p) => p.id)).toEqual(["3"]);
  });

  it("filters by store labeled state", () => {
    const rows = filterProducts(
      sampleProducts,
      { ...EMPTY_BROWSE_QUERY, storeLabeled: false },
      "",
    );
    expect(rows.map((p) => p.id).sort()).toEqual(["2", "3"]);
  });

  it("filters by captured date range", () => {
    const rows = filterProducts(
      sampleProducts,
      {
        ...EMPTY_BROWSE_QUERY,
        capturedAfter: "2026-01-01",
        capturedBefore: "2026-01-31",
      },
      "",
    );
    expect(rows.map((p) => p.id).sort()).toEqual(["1", "3"]);
  });

  it("filters by price range", () => {
    const extents = getPriceExtents(sampleProducts);
    const rows = filterProducts(
      sampleProducts,
      { ...EMPTY_BROWSE_QUERY, priceMin: 3, priceMax: 4 },
      "",
      { extents },
    );
    expect(rows.map((p) => p.id)).toEqual(["1"]);
  });
});

describe("sortProducts", () => {
  it("sorts by price ascending with nulls last", () => {
    const rows = sortProducts(sampleProducts, "price_asc");
    expect(rows.map((p) => p.id)).toEqual(["2", "1", "4", "3"]);
  });

  it("sorts by name descending", () => {
    const rows = sortProducts(sampleProducts, "name_desc");
    expect(rows[0].product_name).toBe("Milk");
  });

  it("sorts by captured date ascending", () => {
    const rows = sortProducts(sampleProducts, "captured_asc");
    expect(rows[0].id).toBe("4");
    expect(rows.at(-1)?.id).toBe("2");
  });
});

describe("chips", () => {
  const extents = getPriceExtents(sampleProducts);

  it("counts default query as zero chips", () => {
    expect(countActiveChips(EMPTY_BROWSE_QUERY, extents)).toBe(0);
  });

  it("builds sort and filter chips", () => {
    const query = {
      ...EMPTY_BROWSE_QUERY,
      sort: "price_asc" as const,
      stores: ["Longos"],
      onSale: true,
    };
    const chips = buildActiveChips(query, extents);
    expect(chips.some((c) => c.id === "sort")).toBe(true);
    expect(chips.some((c) => c.label === "Store: Longos")).toBe(true);
    expect(chips.some((c) => c.id === "onSale")).toBe(true);
  });

  it("removes individual chips", () => {
    const query = {
      ...EMPTY_BROWSE_QUERY,
      sort: "price_asc" as const,
      stores: ["Longos", "Costco"],
    };
    const next = removeChip(query, "store:Longos");
    expect(next.stores).toEqual(["Costco"]);
    expect(removeChip(query, "sort").sort).toBe("captured_desc");
  });
});

describe("price histogram", () => {
  it("builds bins for priced products", () => {
    const bins = buildPriceHistogram(sampleProducts, 4);
    const total = bins.reduce((sum, b) => sum + b.count, 0);
    expect(total).toBe(3);
    expect(bins.length).toBeGreaterThan(0);
  });
});

describe("url sync", () => {
  it("round-trips query params", () => {
    const query = {
      ...EMPTY_BROWSE_QUERY,
      sort: "price_desc" as const,
      stores: ["Longos"],
      priceMin: 2.5,
      onSale: true,
      capturedAfter: "2026-01-01",
    };
    const params = browseQueryToSearchParams(query).toString();
    const parsed = parseBrowseQueryFromSearch(`?${params}`);
    expect(parsed.sort).toBe("price_desc");
    expect(parsed.stores).toEqual(["Longos"]);
    expect(parsed.priceMin).toBe(2.5);
    expect(parsed.onSale).toBe(true);
    expect(parsed.capturedAfter).toBe("2026-01-01");
  });
});

describe("photoGroupLinkLabel", () => {
  it("uses singular copy for one product", () => {
    expect(photoGroupLinkLabel(1)).toBe("View in photo view");
  });

  it("includes product count when grouped", () => {
    expect(photoGroupLinkLabel(4)).toBe("View with 4 products");
  });
});
