import type { Product } from "./types";

export type SortOption =
  | "captured_desc"
  | "captured_asc"
  | "price_asc"
  | "price_desc"
  | "name_asc"
  | "name_desc";

export const DEFAULT_SORT: SortOption = "captured_desc";

export const SORT_OPTIONS: { value: SortOption; label: string }[] = [
  { value: "captured_desc", label: "Newest first" },
  { value: "captured_asc", label: "Oldest first" },
  { value: "price_asc", label: "Price low to high" },
  { value: "price_desc", label: "Price high to low" },
  { value: "name_asc", label: "Name A to Z" },
  { value: "name_desc", label: "Name Z to A" },
];

export type GridColumns = 1 | 2 | 3 | 4;

export const GRID_COLUMN_OPTIONS: { value: GridColumns; label: string }[] = [
  { value: 1, label: "Large" },
  { value: 2, label: "Medium" },
  { value: 3, label: "Small" },
  { value: 4, label: "Dense" },
];

export const DEFAULT_GRID_COLUMNS: GridColumns = 1;

export type ViewMode = "products" | "photos";

export interface BrowseQueryState {
  sort: SortOption;
  stores: string[];
  categories: string[];
  priceMin: number | null;
  priceMax: number | null;
  onSale: boolean | null;
  hasPrice: boolean | null;
  storeLabeled: boolean | null;
  capturedAfter: string | null;
  capturedBefore: string | null;
  gridColumns: GridColumns;
  viewMode: ViewMode;
}

export const EMPTY_BROWSE_QUERY: BrowseQueryState = {
  sort: DEFAULT_SORT,
  stores: [],
  categories: [],
  priceMin: null,
  priceMax: null,
  onSale: null,
  hasPrice: null,
  storeLabeled: null,
  capturedAfter: null,
  capturedBefore: null,
  gridColumns: DEFAULT_GRID_COLUMNS,
  viewMode: "products",
};

export interface PriceExtents {
  min: number;
  max: number;
  pricedCount: number;
  totalCount: number;
}

export interface PriceBin {
  from: number;
  to: number;
  count: number;
}

export interface BrowseChip {
  id: string;
  label: string;
}

const BROWSE_QUERY_STORAGE_KEY = "grocery-prices-browse-query";

export function isDefaultSort(sort: SortOption): boolean {
  return sort === DEFAULT_SORT;
}

export function sortLabel(sort: SortOption): string {
  return SORT_OPTIONS.find((o) => o.value === sort)?.label ?? sort;
}

export function productMatchesSearch(product: Product, search: string): boolean {
  const q = search.trim().toLowerCase();
  if (!q) return true;
  const hay = [
    product.product_name,
    ...Object.values(product.other ?? {}),
    product.location.store,
    product.category,
  ]
    .filter(Boolean)
    .join(" ")
    .toLowerCase();
  return hay.includes(q);
}

export function isStoreLabeled(product: Product): boolean {
  return (
    product.location.store !== "Unknown store" && Boolean(product.location.store_location_id)
  );
}

function capturedDateKey(capturedAt: string | undefined): string | null {
  if (!capturedAt) return null;
  const d = capturedAt.slice(0, 10);
  return /^\d{4}-\d{2}-\d{2}$/.test(d) ? d : null;
}

export interface DateBin {
  from: string;
  to: string;
  count: number;
}

export type DatePresetId = "week" | "month" | "quarter" | "year" | "all";

export const DATE_PRESETS: {
  id: DatePresetId;
  label: string;
  after: string | null;
  before: string | null;
}[] = [
  { id: "week", label: "Last 7 days", after: null, before: null },
  { id: "month", label: "Last 30 days", after: null, before: null },
  { id: "quarter", label: "Last 3 months", after: null, before: null },
  { id: "year", label: "This year", after: null, before: null },
  { id: "all", label: "All time", after: null, before: null },
];

function isoDateLocal(date: Date): string {
  const year = date.getFullYear();
  const month = String(date.getMonth() + 1).padStart(2, "0");
  const day = String(date.getDate()).padStart(2, "0");
  return `${year}-${month}-${day}`;
}

function daysAgoISO(days: number): string {
  const date = new Date();
  date.setDate(date.getDate() - days);
  return isoDateLocal(date);
}

export function datePresetRange(id: DatePresetId): { capturedAfter: string | null; capturedBefore: string | null } {
  switch (id) {
    case "week":
      return { capturedAfter: daysAgoISO(7), capturedBefore: null };
    case "month":
      return { capturedAfter: daysAgoISO(30), capturedBefore: null };
    case "quarter":
      return { capturedAfter: daysAgoISO(90), capturedBefore: null };
    case "year":
      return { capturedAfter: `${new Date().getFullYear()}-01-01`, capturedBefore: null };
    case "all":
      return { capturedAfter: null, capturedBefore: null };
  }
}

export function matchDatePreset(
  capturedAfter: string | null,
  capturedBefore: string | null,
): DatePresetId | null {
  if (!capturedAfter && !capturedBefore) return "all";

  for (const preset of DATE_PRESETS) {
    if (preset.id === "all") continue;
    const range = datePresetRange(preset.id);
    if (range.capturedAfter === capturedAfter && range.capturedBefore === capturedBefore) {
      return preset.id;
    }
  }
  return null;
}

function parseISODate(iso: string): Date {
  const [year, month, day] = iso.split("-").map(Number);
  return new Date(year, month - 1, day);
}

function addDays(date: Date, days: number): Date {
  const next = new Date(date);
  next.setDate(next.getDate() + days);
  return next;
}

function uniquePhotoDates(products: Product[]): string[] {
  const dateByImage = new Map<string, string>();
  for (const product of products) {
    const day = capturedDateKey(product.captured_at);
    if (!day) continue;
    if (!dateByImage.has(product.image_id)) {
      dateByImage.set(product.image_id, day);
    }
  }
  return [...dateByImage.values()].sort();
}

export function buildCapturedDateHistogram(products: Product[]): DateBin[] {
  const photoDays = uniquePhotoDates(products);
  if (photoDays.length === 0) return [];

  const counts = new Map<string, number>();
  for (const day of photoDays) {
    counts.set(day, (counts.get(day) ?? 0) + 1);
  }

  const min = photoDays[0];
  const max = photoDays[photoDays.length - 1];
  const bins: DateBin[] = [];

  for (let cursor = parseISODate(min); cursor <= parseISODate(max); cursor = addDays(cursor, 1)) {
    const day = isoDateLocal(cursor);
    bins.push({ from: day, to: day, count: counts.get(day) ?? 0 });
  }

  if (bins.length <= 60) {
    return bins;
  }

  const weekly: DateBin[] = [];
  for (let i = 0; i < bins.length; i += 7) {
    const slice = bins.slice(i, i + 7);
    weekly.push({
      from: slice[0].from,
      to: slice[slice.length - 1].to,
      count: slice.reduce((sum, bin) => sum + bin.count, 0),
    });
  }
  return weekly;
}

export function countDatedPhotos(products: Product[]): number {
  return uniquePhotoDates(products).length;
}

export interface DateExtents {
  min: string;
  max: string;
  datedPhotoCount: number;
}

export function getDateExtents(bins: DateBin[], datedPhotoCount: number): DateExtents | null {
  if (bins.length === 0) return null;
  return {
    min: bins[0].from,
    max: bins[bins.length - 1].to,
    datedPhotoCount,
  };
}

export function dateToMs(iso: string): number {
  return parseISODate(iso).getTime();
}

export function msToISODate(ms: number): string {
  return isoDateLocal(new Date(ms));
}

export function clampDateISO(iso: string, min: string, max: string): string {
  const clamped = Math.min(Math.max(dateToMs(iso), dateToMs(min)), dateToMs(max));
  return msToISODate(clamped);
}

export function productsForDateHistogram(
  products: Product[],
  query: BrowseQueryState,
  search: string,
): Product[] {
  return products.filter(
    (p) =>
      productMatchesSearch(p, search) &&
      matchesBrowseQuery(p, query, { skipCapturedDate: true }),
  );
}

function effectivePriceBounds(
  query: BrowseQueryState,
  extents: PriceExtents,
): { min: number; max: number } {
  return {
    min: query.priceMin ?? extents.min,
    max: query.priceMax ?? extents.max,
  };
}

export function isPriceFilterActive(
  query: BrowseQueryState,
  extents: PriceExtents | null,
): boolean {
  if (!extents || extents.pricedCount === 0) return false;
  const { min, max } = effectivePriceBounds(query, extents);
  return min > extents.min || max < extents.max;
}

export function matchesBrowseQuery(
  product: Product,
  query: BrowseQueryState,
  options?: { skipPrice?: boolean; skipCapturedDate?: boolean; extents?: PriceExtents | null },
): boolean {
  if (query.stores.length > 0 && !query.stores.includes(product.location.store)) {
    return false;
  }
  if (query.categories.length > 0 && !query.categories.includes(product.category)) {
    return false;
  }

  if (query.onSale !== null) {
    const onSale = product.other?.is_special === true;
    if (onSale !== query.onSale) return false;
  }

  if (query.hasPrice !== null) {
    const hasPrice = product.price != null;
    if (hasPrice !== query.hasPrice) return false;
  }

  if (query.storeLabeled !== null) {
    const labeled = isStoreLabeled(product);
    if (labeled !== query.storeLabeled) return false;
  }

  const capturedKey = capturedDateKey(product.captured_at);
  if (!options?.skipCapturedDate) {
    if (query.capturedAfter) {
      if (!capturedKey || capturedKey < query.capturedAfter) return false;
    }
    if (query.capturedBefore) {
      if (!capturedKey || capturedKey > query.capturedBefore) return false;
    }
  }

  if (!options?.skipPrice) {
    const extents = options?.extents ?? null;
    if (extents && extents.pricedCount > 0 && isPriceFilterActive(query, extents)) {
      if (product.price == null) return false;
      const { min, max } = effectivePriceBounds(query, extents);
      if (product.price < min) return false;
      if (product.price > max) return false;
    }
  }

  return true;
}

export function filterProducts(
  products: Product[],
  query: BrowseQueryState,
  search: string,
  options?: { skipPrice?: boolean; extents?: PriceExtents | null },
): Product[] {
  const extents = options?.extents ?? getPriceExtents(products);
  return products.filter(
    (p) =>
      productMatchesSearch(p, search) &&
      matchesBrowseQuery(p, query, { ...options, extents }),
  );
}

export function sortProducts(products: Product[], sort: SortOption): Product[] {
  const rows = [...products];
  rows.sort((a, b) => {
    switch (sort) {
      case "captured_desc":
      case "captured_asc": {
        const ta = a.captured_at ? new Date(a.captured_at).getTime() : 0;
        const tb = b.captured_at ? new Date(b.captured_at).getTime() : 0;
        return sort === "captured_desc" ? tb - ta : ta - tb;
      }
      case "price_asc":
      case "price_desc": {
        const ap = a.price;
        const bp = b.price;
        if (ap == null && bp == null) return 0;
        if (ap == null) return 1;
        if (bp == null) return -1;
        return sort === "price_asc" ? ap - bp : bp - ap;
      }
      case "name_asc":
      case "name_desc": {
        const cmp = a.product_name.localeCompare(b.product_name);
        return sort === "name_asc" ? cmp : -cmp;
      }
      default:
        return 0;
    }
  });
  return rows;
}

export function getPriceExtents(products: Product[]): PriceExtents {
  const priced = products.filter((p) => p.price != null) as Array<Product & { price: number }>;
  if (priced.length === 0) {
    return { min: 0, max: 0, pricedCount: 0, totalCount: products.length };
  }
  let min = priced[0].price;
  let max = priced[0].price;
  for (const p of priced) {
    if (p.price < min) min = p.price;
    if (p.price > max) max = p.price;
  }
  return { min, max, pricedCount: priced.length, totalCount: products.length };
}

export function buildPriceHistogram(products: Product[], bucketCount = 24): PriceBin[] {
  const extents = getPriceExtents(products);
  if (extents.pricedCount === 0) return [];

  const { min, max } = extents;
  const span = max - min;
  const bins: PriceBin[] = [];

  if (span === 0) {
    return [{ from: min, to: max, count: extents.pricedCount }];
  }

  const step = span / bucketCount;
  for (let i = 0; i < bucketCount; i++) {
    const from = min + step * i;
    const to = i === bucketCount - 1 ? max : min + step * (i + 1);
    bins.push({ from, to, count: 0 });
  }

  for (const p of products) {
    if (p.price == null) continue;
    let idx = Math.floor(((p.price - min) / span) * bucketCount);
    if (idx >= bucketCount) idx = bucketCount - 1;
    if (idx < 0) idx = 0;
    bins[idx].count += 1;
  }

  return bins;
}

export function formatPriceChip(
  query: BrowseQueryState,
  extents: PriceExtents | null,
  currency = "CAD",
): string | null {
  if (!extents || !isPriceFilterActive(query, extents)) return null;
  const fmt = (n: number) =>
    new Intl.NumberFormat("en-CA", { style: "currency", currency }).format(n);
  const { min, max } = effectivePriceBounds(query, extents);
  const atMin = min <= extents.min;
  const atMax = max >= extents.max;
  if (!atMin && !atMax) return `Price: ${fmt(min)}–${fmt(max)}`;
  if (!atMin) return `Price ≥ ${fmt(min)}`;
  if (!atMax) return `Price ≤ ${fmt(max)}`;
  return null;
}

export function buildActiveChips(
  query: BrowseQueryState,
  extents: PriceExtents | null,
): BrowseChip[] {
  const chips: BrowseChip[] = [];

  if (!isDefaultSort(query.sort)) {
    chips.push({ id: "sort", label: `Sort: ${sortLabel(query.sort)}` });
  }

  for (const store of query.stores) {
    chips.push({ id: `store:${store}`, label: `Store: ${store}` });
  }
  for (const category of query.categories) {
    chips.push({ id: `category:${category}`, label: `Category: ${category}` });
  }

  const priceChip = formatPriceChip(query, extents);
  if (priceChip) chips.push({ id: "price", label: priceChip });

  if (query.onSale !== null) {
    chips.push({ id: "onSale", label: `On sale: ${query.onSale ? "yes" : "no"}` });
  }
  if (query.hasPrice !== null) {
    chips.push({ id: "hasPrice", label: `Has price: ${query.hasPrice ? "yes" : "no"}` });
  }
  if (query.storeLabeled !== null) {
    chips.push({
      id: "storeLabeled",
      label: query.storeLabeled ? "Store: labeled" : "Store: unknown",
    });
  }
  if (query.capturedAfter) {
    chips.push({ id: "capturedAfter", label: `After ${query.capturedAfter}` });
  }
  if (query.capturedBefore) {
    chips.push({ id: "capturedBefore", label: `Before ${query.capturedBefore}` });
  }

  return chips;
}

export function countActiveChips(query: BrowseQueryState, extents: PriceExtents | null): number {
  return buildActiveChips(query, extents).length;
}

export function removeChip(query: BrowseQueryState, chipId: string): BrowseQueryState {
  if (chipId === "sort") return { ...query, sort: DEFAULT_SORT };
  if (chipId === "price") return { ...query, priceMin: null, priceMax: null };
  if (chipId === "onSale") return { ...query, onSale: null };
  if (chipId === "hasPrice") return { ...query, hasPrice: null };
  if (chipId === "storeLabeled") return { ...query, storeLabeled: null };
  if (chipId === "capturedAfter") return { ...query, capturedAfter: null };
  if (chipId === "capturedBefore") return { ...query, capturedBefore: null };
  if (chipId.startsWith("store:")) {
    const store = chipId.slice("store:".length);
    return { ...query, stores: query.stores.filter((s) => s !== store) };
  }
  if (chipId.startsWith("category:")) {
    const category = chipId.slice("category:".length);
    return { ...query, categories: query.categories.filter((c) => c !== category) };
  }
  return query;
}

export function productsForPriceHistogram(
  products: Product[],
  query: BrowseQueryState,
  search: string,
): Product[] {
  return products.filter(
    (p) =>
      productMatchesSearch(p, search) &&
      matchesBrowseQuery(p, query, { skipPrice: true }),
  );
}

const SORT_VALUES = new Set<string>(SORT_OPTIONS.map((o) => o.value));

function parseSort(value: string | null): SortOption | undefined {
  if (value && SORT_VALUES.has(value)) return value as SortOption;
  return undefined;
}

function parseStringList(value: string | null): string[] | undefined {
  if (value == null) return undefined;
  if (!value.trim()) return [];
  return value.split(",").map((s) => decodeURIComponent(s.trim())).filter(Boolean);
}

function parseBool(value: string | null): boolean | null | undefined {
  if (value == null) return undefined;
  if (value === "yes" || value === "true" || value === "1") return true;
  if (value === "no" || value === "false" || value === "0") return false;
  return undefined;
}

function parseNumber(value: string | null): number | null | undefined {
  if (value == null || value === "") return undefined;
  const n = Number(value);
  return Number.isFinite(n) ? n : undefined;
}

function parseGridColumns(value: string | null): GridColumns | undefined {
  if (value === "1" || value === "2" || value === "3" || value === "4") {
    return Number(value) as GridColumns;
  }
  return undefined;
}

export function parseBrowseQueryFromSearch(search: string): Partial<BrowseQueryState> {
  const params = new URLSearchParams(search);
  const partial: Partial<BrowseQueryState> = {};

  const sort = parseSort(params.get("sort"));
  if (sort) partial.sort = sort;

  const stores = parseStringList(params.get("stores"));
  if (stores !== undefined) partial.stores = stores;

  const categories = parseStringList(params.get("categories"));
  if (categories !== undefined) partial.categories = categories;

  const priceMin = parseNumber(params.get("priceMin"));
  if (priceMin !== undefined) partial.priceMin = priceMin;

  const priceMax = parseNumber(params.get("priceMax"));
  if (priceMax !== undefined) partial.priceMax = priceMax;

  const onSale = parseBool(params.get("onSale"));
  if (onSale !== undefined) partial.onSale = onSale;

  const hasPrice = parseBool(params.get("hasPrice"));
  if (hasPrice !== undefined) partial.hasPrice = hasPrice;

  const storeLabeled = parseBool(params.get("storeLabeled"));
  if (storeLabeled !== undefined) partial.storeLabeled = storeLabeled;

  const capturedAfter = params.get("capturedAfter");
  if (capturedAfter) partial.capturedAfter = capturedAfter;

  const capturedBefore = params.get("capturedBefore");
  if (capturedBefore) partial.capturedBefore = capturedBefore;

  const gridColumns = parseGridColumns(params.get("cols"));
  if (gridColumns) partial.gridColumns = gridColumns;

  return partial;
}

export function browseQueryToSearchParams(query: BrowseQueryState): URLSearchParams {
  const params = new URLSearchParams();

  if (!isDefaultSort(query.sort)) params.set("sort", query.sort);
  if (query.stores.length) params.set("stores", query.stores.map(encodeURIComponent).join(","));
  if (query.categories.length) {
    params.set("categories", query.categories.map(encodeURIComponent).join(","));
  }
  if (query.priceMin != null) params.set("priceMin", String(query.priceMin));
  if (query.priceMax != null) params.set("priceMax", String(query.priceMax));
  if (query.onSale !== null) params.set("onSale", query.onSale ? "yes" : "no");
  if (query.hasPrice !== null) params.set("hasPrice", query.hasPrice ? "yes" : "no");
  if (query.storeLabeled !== null) {
    params.set("storeLabeled", query.storeLabeled ? "yes" : "no");
  }
  if (query.capturedAfter) params.set("capturedAfter", query.capturedAfter);
  if (query.capturedBefore) params.set("capturedBefore", query.capturedBefore);
  if (query.gridColumns !== DEFAULT_GRID_COLUMNS) {
    params.set("cols", String(query.gridColumns));
  }

  return params;
}

export function syncBrowseQueryToUrl(query: BrowseQueryState) {
  const params = browseQueryToSearchParams(query);
  const next = params.toString();
  const url = new URL(window.location.href);
  if (next) url.search = next;
  else url.search = "";
  window.history.replaceState(null, "", url.toString());
}

export function loadBrowseQueryFromStorage(): Partial<BrowseQueryState> | null {
  try {
    const raw = sessionStorage.getItem(BROWSE_QUERY_STORAGE_KEY);
    if (!raw) return null;
    const parsed = JSON.parse(raw) as Partial<BrowseQueryState>;
    return parsed;
  } catch {
    return null;
  }
}

export function saveBrowseQueryToStorage(query: BrowseQueryState) {
  try {
    sessionStorage.setItem(BROWSE_QUERY_STORAGE_KEY, JSON.stringify(query));
  } catch {
    // ignore quota errors
  }
}

export function mergeBrowseQuery(
  base: BrowseQueryState,
  partial: Partial<BrowseQueryState>,
): BrowseQueryState {
  const merged = { ...base, ...partial };
  const cols = partial.gridColumns ?? merged.gridColumns;
  merged.gridColumns =
    cols === 1 || cols === 2 || cols === 3 || cols === 4 ? cols : DEFAULT_GRID_COLUMNS;
  merged.viewMode = partial.viewMode === "photos" ? "photos" : partial.viewMode === "products" ? "products" : merged.viewMode;
  return merged;
}

export interface PhotoGroup {
  imageId: string;
  products: Product[];
  capturedAt?: string;
  store: string;
  photoType: "shelf" | "receipt";
}

export function photoGroupLinkLabel(productCount: number): string {
  return productCount > 1
    ? `View with ${productCount} products`
    : "View in photo view";
}

export function groupProductsByImageId(products: Product[]): PhotoGroup[] {
  const groups = new Map<string, Product[]>();
  for (const product of products) {
    const bucket = groups.get(product.image_id) ?? [];
    bucket.push(product);
    groups.set(product.image_id, bucket);
  }

  return [...groups.entries()]
    .map(([imageId, groupProducts]) => {
      const sorted = [...groupProducts].sort((a, b) => {
        const aTs = a.captured_at ?? "";
        const bTs = b.captured_at ?? "";
        return bTs.localeCompare(aTs);
      });
      const lead = sorted[0];
      return {
        imageId,
        products: sorted,
        capturedAt: lead.captured_at,
        store: lead.location.store,
        photoType: lead.photo_type ?? "shelf",
      };
    })
    .sort((a, b) => (b.capturedAt ?? "").localeCompare(a.capturedAt ?? ""));
}

export function toggleListValue(list: string[], value: string): string[] {
  return list.includes(value) ? list.filter((v) => v !== value) : [...list, value];
}

export function clampPrice(value: number, min: number, max: number): number {
  return Math.min(max, Math.max(min, value));
}

export function roundPrice(value: number, step = 0.01): number {
  return Math.round(value / step) * step;
}
