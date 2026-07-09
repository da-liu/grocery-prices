import { beforeEach, describe, expect, it, vi } from "vitest";
import {
  EMPTY_BROWSE_QUERY,
  browseQueryToSearchParams,
  buildActiveChips,
  buildCapturedDateHistogram,
  buildPriceHistogram,
  countActiveChips,
  filterProducts,
  getPriceExtents,
  loadBrowseViewPrefsFromStorage,
  mergeBrowseQuery,
  photoGroupLinkLabel,
  photoGroupNeedsStoreLabel,
  photoGroupTitle,
  photoTimesByImage,
  parseBrowseQueryFromSearch,
  roundPrice,
  removeChip,
  saveBrowseViewPrefsToStorage,
  sortProducts,
  type PhotoGroup,
} from "./browseQuery";
import type { Product } from "@/shared/types/types";

function makeProduct(overrides: Partial<Product> & Pick<Product, "id" | "product_name">): Product {
  return {
    image_id: "img-1",
    image_path: "/x.jpg",
    price: 5,
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
    other: { is_special: false },
    location: { store: "Longos", store_location_id: "s1" },
  }),
  makeProduct({
    id: "2",
    product_name: "Bananas",
    price: 1.99,
    category: "produce",
    captured_at: "2026-02-01T12:00:00Z",
    other: { is_special: true },
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
    other: { is_special: false },
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

describe("captured date histogram", () => {
  it("bins photos by calendar day", () => {
    const products: Product[] = [
      makeProduct({
        id: "a",
        product_name: "A",
        image_id: "img-a",
        captured_at: "2026-07-04T10:15:00-04:00",
      }),
      makeProduct({
        id: "b",
        product_name: "B",
        image_id: "img-b",
        captured_at: "2026-07-04T22:45:00-04:00",
      }),
      makeProduct({
        id: "c",
        product_name: "C",
        image_id: "img-c",
        captured_at: "2026-07-05T11:30:00-04:00",
      }),
    ];

    const timeByImage = photoTimesByImage(products);
    const bins = buildCapturedDateHistogram(timeByImage);

    expect(bins).toHaveLength(2);
    expect(bins[0].from).toBe("2026-07-04");
    expect(bins[0].count).toBe(2);
    expect(bins[1].from).toBe("2026-07-05");
    expect(bins[1].count).toBe(1);
  });
});

describe("view prefs storage", () => {
  const storageKey = "grocery-prices-browse-view-prefs";
  const storage = new Map<string, string>();

  beforeEach(() => {
    storage.clear();
    vi.stubGlobal("localStorage", {
      getItem: (key: string) => storage.get(key) ?? null,
      setItem: (key: string, value: string) => {
        storage.set(key, value);
      },
      removeItem: (key: string) => {
        storage.delete(key);
      },
      clear: () => {
        storage.clear();
      },
    });
  });

  it("persists view mode and grid columns on the device", () => {
    saveBrowseViewPrefsToStorage({
      ...EMPTY_BROWSE_QUERY,
      viewMode: "products",
      gridColumns: 3,
    });

    expect(loadBrowseViewPrefsFromStorage()).toEqual({
      viewMode: "products",
      gridColumns: 3,
    });
    expect(localStorage.getItem(storageKey)).toBeTruthy();
  });

  it("restores saved view prefs when starting a new session", () => {
    saveBrowseViewPrefsToStorage({
      ...EMPTY_BROWSE_QUERY,
      viewMode: "products",
      gridColumns: 2,
    });

    const query = mergeBrowseQuery(EMPTY_BROWSE_QUERY, loadBrowseViewPrefsFromStorage() ?? {});
    expect(query.viewMode).toBe("products");
    expect(query.gridColumns).toBe(2);
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

function makePhotoGroup(
  overrides: Partial<PhotoGroup> & Pick<PhotoGroup, "imageId">,
): PhotoGroup {
  return {
    products: [],
    location: { store: "Longos" },
    photoType: "shelf",
    ...overrides,
  };
}

describe("photoGroupTitle", () => {
  it("uses a single product name", () => {
    const group = makePhotoGroup({
      imageId: "img-1",
      products: [makeProduct({ id: "1", product_name: "Milk" })],
    });
    expect(photoGroupTitle(group)).toBe("Milk");
  });

  it("joins two product names", () => {
    const group = makePhotoGroup({
      imageId: "img-1",
      products: [
        makeProduct({ id: "1", product_name: "Milk" }),
        makeProduct({ id: "2", product_name: "Bread" }),
      ],
    });
    expect(photoGroupTitle(group)).toBe("Milk, Bread");
  });

  it("summarizes three or more products", () => {
    const group = makePhotoGroup({
      imageId: "img-1",
      products: [
        makeProduct({ id: "1", product_name: "Milk" }),
        makeProduct({ id: "2", product_name: "Bread" }),
        makeProduct({ id: "3", product_name: "Eggs" }),
        makeProduct({ id: "4", product_name: "Butter" }),
      ],
    });
    expect(photoGroupTitle(group)).toBe("Milk, Bread +2 more");
  });

  it("uses shelf photo label for empty extraction", () => {
    const group = makePhotoGroup({
      imageId: "img-1",
      products: [
        makeProduct({
          id: "1",
          product_name: "No products extracted",
          extraction_empty: true,
        }),
      ],
      photoType: "shelf",
    });
    expect(photoGroupTitle(group)).toBe("Shelf photo");
  });

  it("uses receipt label for empty receipt extraction", () => {
    const group = makePhotoGroup({
      imageId: "img-1",
      products: [
        makeProduct({
          id: "1",
          product_name: "No products extracted",
          extraction_empty: true,
        }),
      ],
      photoType: "receipt",
    });
    expect(photoGroupTitle(group)).toBe("Receipt");
  });

  it("truncates very long product names", () => {
    const longName = "A".repeat(50);
    const group = makePhotoGroup({
      imageId: "img-1",
      products: [makeProduct({ id: "1", product_name: longName })],
    });
    expect(photoGroupTitle(group)).toHaveLength(40);
    expect(photoGroupTitle(group).endsWith("…")).toBe(true);
  });
});

describe("photoGroupNeedsStoreLabel", () => {
  it("is true for unknown store", () => {
    const group = makePhotoGroup({
      imageId: "img-1",
      location: { store: "Unknown store" },
    });
    expect(photoGroupNeedsStoreLabel(group)).toBe(true);
  });

  it("is true when store_location_id is missing", () => {
    const group = makePhotoGroup({
      imageId: "img-1",
      location: { store: "Longos" },
    });
    expect(photoGroupNeedsStoreLabel(group)).toBe(true);
  });

  it("is false when store is labeled", () => {
    const group = makePhotoGroup({
      imageId: "img-1",
      location: { store: "Longos", store_location_id: "s1" },
    });
    expect(photoGroupNeedsStoreLabel(group)).toBe(false);
  });
});

describe("roundPrice", () => {
  it("snaps to cents without float artifacts", () => {
    const min = 2.49;
    const max = 15.99;
    const span = max - min;
    for (let ratio = 0; ratio <= 1; ratio += 0.01) {
      const raw = min + ratio * span;
      const rounded = roundPrice(raw);
      expect(String(rounded)).not.toMatch(/0{4,}|9{4,}/);
      expect(rounded).toBe(Math.round(raw * 100) / 100);
    }
  });

  it("supports quarter steps", () => {
    expect(roundPrice(7.13, 0.25)).toBe(7.25);
    expect(String(roundPrice(7.13, 0.25))).toBe("7.25");
  });
});
