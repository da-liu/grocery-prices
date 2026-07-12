import { beforeEach, describe, expect, it, vi } from "vitest";
import {
  EMPTY_BROWSE_QUERY,
  SESSION_GAP_MS,
  browseQueryToSearchParams,
  buildActiveChips,
  buildCapturedDateHistogram,
  buildPriceHistogram,
  clusterPhotosByTime,
  countActiveChips,
  filterProducts,
  getPriceExtents,
  hasActiveSession,
  isBrowseHistoryState,
  isRecentTripRange,
  loadBrowseViewPrefsFromStorage,
  mergeBrowseQuery,
  newestSessionImageIds,
  photoGroupLinkLabel,
  photoGroupNeedsStoreLabel,
  photoGroupTitle,
  photoTimesByImage,
  parseBrowseQueryFromSearch,
  pushBrowseEscapeNavigation,
  recentTripRange,
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

  it("falls back to created_at when captured_at is missing", () => {
    const products = [
      makeProduct({
        id: "old",
        product_name: "Old",
        captured_at: "2026-01-01T12:00:00Z",
        created_at: "2026-01-01T12:00:00Z",
      }),
      makeProduct({
        id: "new-upload",
        product_name: "New Upload",
        created_at: "2026-07-11T18:00:00Z",
      }),
    ];
    const rows = sortProducts(products, "captured_desc");
    expect(rows.map((p) => p.id)).toEqual(["new-upload", "old"]);
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

  it("includes photos that only have created_at", () => {
    const products: Product[] = [
      makeProduct({
        id: "upload-only",
        product_name: "Upload Only",
        image_id: "img-upload",
        created_at: "2026-07-11T18:30:00Z",
      }),
    ];
    const timeByImage = photoTimesByImage(products);
    expect(timeByImage.has("img-upload")).toBe(true);

    const rows = filterProducts(
      products,
      {
        ...EMPTY_BROWSE_QUERY,
        capturedAfter: "2026-07-11",
        capturedBefore: "2026-07-11",
      },
      "",
    );
    expect(rows.map((p) => p.id)).toEqual(["upload-only"]);
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

  it("round-trips datetime capture bounds", () => {
    const query = {
      ...EMPTY_BROWSE_QUERY,
      capturedAfter: "2026-07-12T15:00:00.000Z",
      capturedBefore: "2026-07-12T16:10:00.000Z",
    };
    const params = browseQueryToSearchParams(query).toString();
    const parsed = parseBrowseQueryFromSearch(`?${params}`);
    expect(parsed.capturedAfter).toBe("2026-07-12T15:00:00.000Z");
    expect(parsed.capturedBefore).toBe("2026-07-12T16:10:00.000Z");
  });
});

describe("session clustering", () => {
  const base = Date.parse("2026-07-12T15:00:00Z");

  function timedPhoto(
    imageId: string,
    offsetMin: number,
    opts?: { createdOnly?: boolean },
  ): Product {
    const iso = new Date(base + offsetMin * 60_000).toISOString();
    return makeProduct({
      id: imageId,
      product_name: imageId,
      image_id: imageId,
      ...(opts?.createdOnly ? { created_at: iso } : { captured_at: iso }),
    });
  }

  it("keeps photos within the gap in one cluster", () => {
    const products = [
      timedPhoto("a", 0),
      timedPhoto("b", 20),
      timedPhoto("c", 39),
    ];
    const clusters = clusterPhotosByTime(products, SESSION_GAP_MS);
    expect(clusters).toHaveLength(1);
    expect(clusters[0].imageIds.sort()).toEqual(["a", "b", "c"]);
  });

  it("splits when consecutive gap exceeds 40 minutes", () => {
    const products = [
      timedPhoto("a", 0),
      timedPhoto("b", 30),
      timedPhoto("c", 71), // 41 min after b
      timedPhoto("d", 80),
    ];
    const clusters = clusterPhotosByTime(products, SESSION_GAP_MS);
    expect(clusters).toHaveLength(2);
    expect(clusters[0].imageIds.sort()).toEqual(["a", "b"]);
    expect(clusters[1].imageIds.sort()).toEqual(["c", "d"]);
  });

  it("uses created_at when captured_at is missing", () => {
    const products = [timedPhoto("upload", 0, { createdOnly: true })];
    expect(newestSessionImageIds(products).has("upload")).toBe(true);
  });

  it("skips photos with no timestamp", () => {
    const products = [
      makeProduct({ id: "x", product_name: "X", image_id: "no-time" }),
      timedPhoto("a", 0),
    ];
    const clusters = clusterPhotosByTime(products);
    expect(clusters).toHaveLength(1);
    expect(clusters[0].imageIds).toEqual(["a"]);
  });

  it("recent trip range filters to the newest cluster via capture bounds", () => {
    const products = [
      timedPhoto("old-a", 0),
      timedPhoto("old-b", 10),
      timedPhoto("new-a", 100),
      timedPhoto("new-b", 110),
    ];
    const trip = recentTripRange(products);
    expect(trip).not.toBeNull();
    const rows = filterProducts(products, { ...EMPTY_BROWSE_QUERY, ...trip! }, "");
    expect(rows.map((p) => p.image_id).sort()).toEqual(["new-a", "new-b"]);
    expect(isRecentTripRange({ ...EMPTY_BROWSE_QUERY, ...trip! }, products)).toBe(true);
  });

  it("hasActiveSession when newest cluster is recent", () => {
    const products = [timedPhoto("a", 0), timedPhoto("b", 10)];
    expect(hasActiveSession(products, base + 20 * 60_000)).toBe(true);
    expect(hasActiveSession(products, base + 60 * 60_000)).toBe(false);
  });

  it("builds and removes recent trip chip from capture bounds", () => {
    const products = [timedPhoto("a", 0), timedPhoto("b", 10)];
    const trip = recentTripRange(products)!;
    const query = { ...EMPTY_BROWSE_QUERY, ...trip };
    const chips = buildActiveChips(query, null, products);
    expect(chips.some((c) => c.id === "recentTrip" && c.label === "Recent trip")).toBe(true);
    expect(removeChip(query, "recentTrip")).toMatchObject({
      capturedAfter: null,
      capturedBefore: null,
    });
  });
});

describe("browse history state", () => {
  it("accepts valid navigation snapshots", () => {
    expect(
      isBrowseHistoryState({
        browseQuery: EMPTY_BROWSE_QUERY,
        browseSearch: "milk",
        scrollY: 120,
      }),
    ).toBe(true);
    expect(isBrowseHistoryState(null)).toBe(false);
    expect(isBrowseHistoryState({ browseSearch: "x" })).toBe(false);
  });

  it("pushBrowseEscapeNavigation snapshots prior then pushes next", () => {
    const states: unknown[] = [];
    const urls: string[] = [];
    const history = {
      state: null as unknown,
      replaceState(state: unknown, _title: string, url?: string) {
        this.state = state;
        states.push({ op: "replace", state });
        if (url) urls.push(url);
      },
      pushState(state: unknown, _title: string, url?: string) {
        this.state = state;
        states.push({ op: "push", state });
        if (url) urls.push(url);
      },
    };
    vi.stubGlobal("window", {
      location: { href: "http://localhost:5173/" },
      history,
    });

    const prior = {
      browseQuery: {
        ...EMPTY_BROWSE_QUERY,
        capturedAfter: "2026-07-12T15:00:00.000Z",
        capturedBefore: "2026-07-12T15:40:00.000Z",
      },
      browseSearch: "",
      scrollY: 40,
    };
    const next = { ...EMPTY_BROWSE_QUERY, viewMode: "products" as const };
    pushBrowseEscapeNavigation(prior, next);

    expect(states[0]).toEqual({ op: "replace", state: prior });
    expect(states[1]).toMatchObject({
      op: "push",
      state: { browseQuery: next, browseSearch: "", scrollY: 0 },
    });
    expect(urls[0]).toContain("capturedAfter=");
    vi.unstubAllGlobals();
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
