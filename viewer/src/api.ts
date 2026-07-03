import { authHeaders, clearToken, getToken, setToken } from "./auth";
import type { Product } from "./types";

const API_BASE = import.meta.env.VITE_API_URL ?? "";

const fetchOpts: RequestInit = {
  credentials: "include",
};

export interface UserProfile {
  authenticated: boolean;
  username: string;
  upload_count: number;
  needs_onboarding: boolean;
}

async function parseError(resp: Response): Promise<string> {
  try {
    const body = await resp.json();
    if (typeof body.detail === "string") return body.detail;
    return JSON.stringify(body.detail ?? body);
  } catch {
    return resp.statusText || `Request failed (${resp.status})`;
  }
}

function authFetch(url: string, init: RequestInit = {}) {
  return fetch(url, {
    ...fetchOpts,
    ...init,
    headers: {
      ...authHeaders(),
      ...(init.headers ?? {}),
    },
  });
}

export async function fetchHealth(): Promise<{ auth_required: boolean }> {
  const resp = await fetch(`${API_BASE}/health`, fetchOpts);
  if (!resp.ok) throw new Error(await parseError(resp));
  return resp.json();
}

async function authAction(
  path: string,
  body: { username: string; password: string },
): Promise<UserProfile> {
  const resp = await fetch(`${API_BASE}${path}`, {
    ...fetchOpts,
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  if (!resp.ok) throw new Error(await parseError(resp));
  const payload = await resp.json();
  setToken(payload.token);
  return {
    authenticated: true,
    username: payload.username,
    upload_count: payload.upload_count,
    needs_onboarding: payload.needs_onboarding,
  };
}

export function register(username: string, password: string) {
  return authAction("/api/auth/register", { username, password });
}

export function login(username: string, password: string) {
  return authAction("/api/auth/login", { username, password });
}

export async function logout() {
  try {
    await authFetch(`${API_BASE}/api/auth/logout`, { method: "POST" });
  } finally {
    clearToken();
  }
}

export async function fetchMe(): Promise<UserProfile> {
  const resp = await authFetch(`${API_BASE}/api/auth/me`);
  if (!resp.ok) throw new Error(await parseError(resp));
  return resp.json();
}

export async function completeOnboarding(): Promise<UserProfile> {
  const resp = await authFetch(`${API_BASE}/api/auth/onboarding/complete`, {
    method: "POST",
  });
  if (!resp.ok) throw new Error(await parseError(resp));
  const me = await fetchMe();
  return me;
}

export async function fetchProducts(): Promise<Product[]> {
  const resp = await authFetch(`${API_BASE}/api/products`);
  if (!resp.ok) throw new Error(await parseError(resp));
  return resp.json();
}

export async function deleteProduct(productId: string): Promise<void> {
  const resp = await authFetch(`${API_BASE}/api/products/${encodeURIComponent(productId)}`, {
    method: "DELETE",
  });
  if (!resp.ok) throw new Error(await parseError(resp));
}

export interface BulkDeleteResult {
  deleted: number;
  photos_removed: number;
  failed: string[];
}

export async function deleteProductsBulk(productIds: string[]): Promise<BulkDeleteResult> {
  const resp = await authFetch(`${API_BASE}/api/products/bulk-delete`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ ids: productIds }),
  });
  if (!resp.ok) throw new Error(await parseError(resp));
  return resp.json();
}

export function productImageUrl(imageId: string): string {
  const token = getToken();
  const base = `${API_BASE}/api/media/${imageId}`;
  return token ? `${base}?access_token=${encodeURIComponent(token)}` : base;
}

export interface ExtractedProductRow {
  product_name: string;
  price: number | null;
  category: string;
}

export type DuplicateAction = "skip" | "replace" | "new";

export type ExtractionStatus = "pending" | "processing" | "done" | "failed";

export interface UploadResult {
  image_id: string;
  image_path: string;
  products: ExtractedProductRow[];
  product_count: number;
  needs_store_label?: boolean;
  meta: {
    captured_at?: string;
    gps_latitude?: number | null;
    gps_longitude?: number | null;
  };
  duplicate?: boolean;
  duplicate_of?: string;
  action_required?: boolean;
  skipped?: boolean;
  extraction_empty?: boolean;
  extraction_status?: ExtractionStatus;
  extraction_error?: string;
  overlapping_products?: import("./types").OverlappingProduct[];
}

export interface ReextractResult {
  image_id: string;
  products: ExtractedProductRow[];
  product_count: number;
  extraction_empty: boolean;
  overlapping_products?: import("./types").OverlappingProduct[];
}

export type ProductUpdateInput = {
  product_name?: string;
  product_name_zh?: string | null;
  brand?: string | null;
  price?: number | null;
  unit?: string | null;
  unit_price?: number | null;
  unit_price_per_100g?: number | null;
  regular_price?: number | null;
  is_special?: boolean | null;
  promo?: string | null;
  barcode?: string | null;
  size?: string | null;
  category?: string | null;
  notes?: string | null;
};

export type ManualProductInput = {
  product_name: string;
  product_name_zh?: string;
  brand?: string;
  price?: number | null;
  unit?: string;
  unit_price?: number | null;
  barcode?: string;
  size?: string;
  category?: string;
  notes?: string;
};

async function postUpload(
  url: string,
  form: FormData,
  duplicateAction?: DuplicateAction,
): Promise<Response> {
  if (duplicateAction) {
    form.append("duplicate_action", duplicateAction);
  }
  try {
    return await authFetch(url, { method: "POST", body: form });
  } catch (err) {
    const message = err instanceof Error ? err.message : "Network error";
    throw new Error(
      message === "Load failed" || message === "Failed to fetch"
        ? `Could not reach API at ${API_BASE}. Check network or try again.`
        : message,
    );
  }
}

export async function uploadPhotos(
  files: File[],
  source: "shelf" | "receipt",
  duplicateAction?: DuplicateAction,
): Promise<{ results: UploadResult[] }> {
  const form = new FormData();
  for (const file of files) {
    form.append("files", file);
  }
  form.append("source", source === "receipt" ? "receipt" : "upload");
  const resp = await postUpload(`${API_BASE}/api/photos/bulk`, form, duplicateAction);
  if (!resp.ok) throw new Error(await parseError(resp));
  return resp.json();
}

export async function fetchPhotoStatuses(imageIds: string[]): Promise<{ results: UploadResult[] }> {
  if (!imageIds.length) return { results: [] };
  const resp = await authFetch(`${API_BASE}/api/photos/status`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ ids: imageIds }),
  });
  if (!resp.ok) throw new Error(await parseError(resp));
  return resp.json();
}

export async function updateProduct(productId: string, updates: ProductUpdateInput): Promise<Product> {
  const resp = await authFetch(`${API_BASE}/api/products/${encodeURIComponent(productId)}`, {
    method: "PATCH",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(updates),
  });
  if (!resp.ok) throw new Error(await parseError(resp));
  return resp.json();
}

export async function addManualProduct(imageId: string, product: ManualProductInput): Promise<Product> {
  const resp = await authFetch(`${API_BASE}/api/photos/${encodeURIComponent(imageId)}/products`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(product),
  });
  if (!resp.ok) throw new Error(await parseError(resp));
  return resp.json();
}

export async function reextractPhoto(imageId: string): Promise<ReextractResult> {
  const resp = await authFetch(`${API_BASE}/api/photos/${encodeURIComponent(imageId)}/re-extract`, {
    method: "POST",
  });
  if (!resp.ok) throw new Error(await parseError(resp));
  return resp.json();
}

export type StoreLocationInput = {
  name: string;
  latitude: number;
  longitude: number;
  match_radius_m?: number;
  maps_url?: string | null;
};

export async function fetchStoreLocations() {
  const resp = await authFetch(`${API_BASE}/api/store-locations`);
  if (!resp.ok) throw new Error(await parseError(resp));
  return resp.json() as Promise<import("./types").StoreLocation[]>;
}

export async function createStoreLocation(body: StoreLocationInput) {
  const resp = await authFetch(`${API_BASE}/api/store-locations`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  if (!resp.ok) throw new Error(await parseError(resp));
  return resp.json() as Promise<import("./types").StoreLocation>;
}

export async function updateStoreLocation(storeId: string, body: StoreLocationInput) {
  const resp = await authFetch(`${API_BASE}/api/store-locations/${encodeURIComponent(storeId)}`, {
    method: "PUT",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  if (!resp.ok) throw new Error(await parseError(resp));
  return resp.json() as Promise<import("./types").StoreLocation>;
}

export async function deleteStoreLocation(storeId: string) {
  const resp = await authFetch(`${API_BASE}/api/store-locations/${encodeURIComponent(storeId)}`, {
    method: "DELETE",
  });
  if (!resp.ok) throw new Error(await parseError(resp));
}

export async function assignPhotoStore(imageId: string, storeLocationId: string) {
  const resp = await authFetch(`${API_BASE}/api/photos/${encodeURIComponent(imageId)}/store-location`, {
    method: "PUT",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ store_location_id: storeLocationId }),
  });
  if (!resp.ok) throw new Error(await parseError(resp));
}
