import { authHeaders, clearToken, getToken, setToken } from "@/features/auth/auth";
import type { CreateStoreLocationResult, Product, StoreLocation } from "@/shared/types/types";

const API_BASE = import.meta.env.VITE_API_URL ?? "";
const JSON_HEADERS = { "Content-Type": "application/json" };

export interface UserProfile {
  authenticated: boolean;
  username: string;
  upload_count: number;
  onboarding_completed: string[];
}

export const ONBOARDING_WELCOME = "welcome";

export function needsWelcomeOnboarding(completed: string[]): boolean {
  return !completed.includes(ONBOARDING_WELCOME);
}

export class ApiError extends Error {
  readonly status: number;

  constructor(message: string, status: number) {
    super(message);
    this.name = "ApiError";
    this.status = status;
  }
}

export function isAuthError(err: unknown): boolean {
  return err instanceof ApiError && err.status === 401;
}

function toUserProfile(payload: {
  username: string;
  upload_count: number;
  onboarding_completed: string[];
}): UserProfile {
  return {
    authenticated: true,
    username: payload.username,
    upload_count: payload.upload_count,
    onboarding_completed: payload.onboarding_completed,
  };
}

const FIELD_LABELS: Record<string, string> = {
  username: "Email",
  password: "Password",
  email: "Email",
};

function fieldLabel(loc: unknown): string | null {
  if (!Array.isArray(loc) || loc.length === 0) return null;
  const raw = loc[loc.length - 1];
  if (typeof raw !== "string" || raw === "body") return null;
  return FIELD_LABELS[raw] ?? raw.replace(/_/g, " ");
}

function formatValidationItem(item: unknown): string | null {
  if (!item || typeof item !== "object") return null;
  const entry = item as { msg?: unknown; loc?: unknown; type?: unknown };
  const msg = typeof entry.msg === "string" ? entry.msg.trim() : "";
  if (!msg) return null;

  const label = fieldLabel(entry.loc);
  const type = typeof entry.type === "string" ? entry.type : "";

  if (type === "string_too_short" && label === "Password") {
    return "Password must be at least 8 characters";
  }
  if (type === "string_too_short" && label === "Email") {
    return "Email must be at least 3 characters";
  }
  if (type === "string_too_long" && label) {
    return `${label} is too long`;
  }
  if (type === "missing" && label) {
    return `${label} is required`;
  }
  if (label && !msg.toLowerCase().startsWith(label.toLowerCase())) {
    return `${label}: ${msg}`;
  }
  return msg;
}

/** Turn FastAPI / API error JSON into a short user-facing message. */
export function formatErrorDetail(body: unknown): string {
  if (typeof body === "string" && body.trim()) return body.trim();
  if (!body || typeof body !== "object") return "Request failed";

  if ("detail" in body) {
    const { detail } = body as { detail: unknown };
    if (typeof detail === "string" && detail.trim()) return detail.trim();

    if (Array.isArray(detail)) {
      const messages = detail
        .map(formatValidationItem)
        .filter((m): m is string => Boolean(m));
      if (messages.length === 1) return messages[0];
      if (messages.length > 1) return messages.join(". ");
      return "Please check your input and try again";
    }

    if (detail && typeof detail === "object") {
      const nested = formatValidationItem(detail);
      if (nested) return nested;
    }
  }

  if ("message" in body && typeof (body as { message: unknown }).message === "string") {
    const message = (body as { message: string }).message.trim();
    if (message) return message;
  }

  return "Request failed";
}

async function parseError(resp: Response): Promise<string> {
  try {
    return formatErrorDetail(await resp.json());
  } catch {
    return resp.statusText || `Request failed (${resp.status})`;
  }
}

function parseXhrError(xhr: XMLHttpRequest): string {
  try {
    return formatErrorDetail(JSON.parse(xhr.responseText));
  } catch {
    return xhr.statusText || `Request failed (${xhr.status})`;
  }
}

function errorMessage(err: unknown): string {
  return err instanceof Error ? err.message : "Network error";
}

export function describeRequestError(
  err: unknown,
  action: "upload" | "status",
  apiBase: string = API_BASE,
): string {
  const message = errorMessage(err);
  if (message !== "Load failed" && message !== "Failed to fetch") {
    return message;
  }
  if (action === "status") {
    return `Lost connection while checking upload progress at ${apiBase}. Your photo may still finish processing; refresh in a moment.`;
  }
  return `Could not reach API at ${apiBase}. Check network or try again.`;
}

function authFetch(path: string, init: RequestInit = {}) {
  return fetch(`${API_BASE}${path}`, {
    credentials: "omit",
    ...init,
    headers: { ...authHeaders(), ...(init.headers ?? {}) },
  });
}

async function checkResponse(resp: Response): Promise<void> {
  if (!resp.ok) throw new Error(await parseError(resp));
}

async function authJson<T>(path: string, init: RequestInit = {}): Promise<T> {
  const resp = await authFetch(path, init);
  await checkResponse(resp);
  return resp.json();
}

async function authVoid(path: string, init: RequestInit = {}): Promise<void> {
  await checkResponse(await authFetch(path, init));
}

async function authAction(
  path: string,
  body: { username: string; password: string },
): Promise<UserProfile> {
  const resp = await fetch(`${API_BASE}${path}`, {
    method: "POST",
    credentials: "omit",
    headers: JSON_HEADERS,
    body: JSON.stringify(body),
  });
  await checkResponse(resp);
  const payload = await resp.json();
  setToken(payload.token);
  return toUserProfile(payload);
}

export function register(username: string, password: string) {
  return authAction("/api/auth/register", { username, password });
}

export function login(username: string, password: string) {
  return authAction("/api/auth/login", { username, password });
}

export async function logout() {
  try {
    await authFetch("/api/auth/logout", { method: "POST" });
  } finally {
    clearToken();
  }
}

export async function fetchMe(): Promise<UserProfile> {
  const resp = await authFetch("/api/auth/me");
  if (!resp.ok) throw new ApiError(await parseError(resp), resp.status);
  return toUserProfile(await resp.json());
}

export async function completeOnboarding(
  key: string = ONBOARDING_WELCOME,
): Promise<UserProfile> {
  const resp = await authFetch("/api/auth/onboarding/complete", {
    method: "POST",
    headers: JSON_HEADERS,
    body: JSON.stringify({ key }),
  });
  await checkResponse(resp);
  return fetchMe();
}

export async function fetchProducts(): Promise<Product[]> {
  return authJson("/api/products");
}

export async function deleteProduct(productId: string): Promise<void> {
  await authVoid(`/api/products/${encodeURIComponent(productId)}`, { method: "DELETE" });
}

export async function deletePhoto(imageId: string): Promise<void> {
  await authVoid(`/api/photos/${encodeURIComponent(imageId)}`, { method: "DELETE" });
}

export interface BulkDeleteResult {
  deleted: number;
  failed: string[];
}

function parseBulkDeleteResult(body: unknown): BulkDeleteResult {
  if (!body || typeof body !== "object") {
    throw new Error("Invalid bulk delete response");
  }
  const record = body as Record<string, unknown>;
  if (typeof record.deleted !== "number" || !Array.isArray(record.failed)) {
    throw new Error("Invalid bulk delete response");
  }
  return {
    deleted: record.deleted,
    failed: record.failed.filter((id): id is string => typeof id === "string"),
  };
}

export async function deleteProductsBulk(productIds: string[]): Promise<BulkDeleteResult> {
  const resp = await authFetch("/api/products/bulk-delete", {
    method: "POST",
    headers: JSON_HEADERS,
    body: JSON.stringify({ ids: productIds }),
  });
  await checkResponse(resp);
  return parseBulkDeleteResult(await resp.json());
}

export function productImageUrl(imageId: string): string {
  const token = getToken();
  const base = `${API_BASE}/api/media/${imageId}`;
  // <img> cannot send Authorization; pass token as query param instead.
  return token ? `${base}?access_token=${encodeURIComponent(token)}` : base;
}

export interface ExtractedProductRow {
  product_name: string;
  price: number | null;
  category: string;
}

export type DuplicateAction = "skip" | "replace" | "new";

export type ClientExifPayload = {
  GPSLatitude?: number;
  GPSLongitude?: number;
  /** ISO 8601 capture time with timezone offset, ready for DB storage. */
  captured_at?: string;
  /** Local capture date folder name (`YYYY_MM_DD`). */
  date_folder?: string;
};

export type ExtractionStatus = "pending" | "done" | "failed";

export type PhotoPipelineStatus =
  | "pending"
  | "extracted"
  | "matched"
  | "failed"
  | "match_failed";

export interface UploadResult {
  image_id: string;
  product_count: number;
  needs_store_label?: boolean;
  duplicate_of?: string;
  action_required?: boolean;
  skipped?: boolean;
  extraction_empty?: boolean;
  extraction_status?: ExtractionStatus;
  status?: PhotoPipelineStatus;
  extraction_error?: string;
}

export interface ReextractResult {
  image_id: string;
  products: ExtractedProductRow[];
  product_count: number;
  extraction_empty: boolean;
}

export type ProductUpdateInput = {
  product_name?: string;
  other?: Record<string, string | number | boolean | null> | null;
  price?: number | null;
  unit?: string | null;
  unit_price?: number | null;
  category?: string | null;
};

export type ManualProductInput = {
  product_name: string;
  other?: Record<string, string | number | boolean | null>;
  price?: number | null;
  unit?: string;
  unit_price?: number | null;
  category?: string;
};

export function buildUploadForm(
  files: File[],
  duplicateAction?: DuplicateAction,
  clientExifs?: (ClientExifPayload | undefined)[],
): FormData {
  const form = new FormData();
  for (const file of files) {
    form.append("files", file);
  }
  if (duplicateAction) {
    form.append("duplicate_action", duplicateAction);
  }
  if (clientExifs?.length) {
    const payloads = clientExifs.map((entry) => entry ?? null);
    if (payloads.some((entry) => entry != null && Object.keys(entry).length > 0)) {
      form.append("exif_json", JSON.stringify(payloads));
    }
  }
  return form;
}

export function uploadPhotosWithProgress(
  files: File[],
  onProgress: (percent: number) => void,
  duplicateAction?: DuplicateAction,
  clientExifs?: (ClientExifPayload | undefined)[],
): Promise<{ results: UploadResult[] }> {
  return new Promise((resolve, reject) => {
    const xhr = new XMLHttpRequest();
    xhr.open("POST", `${API_BASE}/api/photos/bulk`);
    for (const [key, value] of Object.entries(authHeaders())) {
      xhr.setRequestHeader(key, value);
    }

    xhr.upload.addEventListener("progress", (event) => {
      if (event.lengthComputable && event.total > 0) {
        onProgress(Math.min(100, Math.round((event.loaded / event.total) * 100)));
      }
    });

    xhr.addEventListener("load", () => {
      if (xhr.status >= 200 && xhr.status < 300) {
        try {
          resolve(JSON.parse(xhr.responseText));
        } catch {
          reject(new Error("Invalid upload response"));
        }
        return;
      }
      reject(new Error(parseXhrError(xhr)));
    });

    xhr.addEventListener("error", () => {
      reject(new Error(describeRequestError(new Error("Failed to fetch"), "upload")));
    });

    xhr.addEventListener("abort", () => {
      reject(new Error("Upload cancelled"));
    });

    xhr.send(buildUploadForm(files, duplicateAction, clientExifs));
  });
}

export async function fetchPhotoStatuses(imageIds: string[]): Promise<{ results: UploadResult[] }> {
  if (!imageIds.length) return { results: [] };
  let resp: Response;
  try {
    resp = await authFetch("/api/photos/status", {
      method: "POST",
      headers: JSON_HEADERS,
      body: JSON.stringify({ ids: imageIds }),
    });
  } catch (err) {
    throw new Error(describeRequestError(err, "status"));
  }
  await checkResponse(resp);
  return resp.json();
}

export async function updateProduct(productId: string, updates: ProductUpdateInput): Promise<Product> {
  return authJson(`/api/products/${encodeURIComponent(productId)}`, {
    method: "PATCH",
    headers: JSON_HEADERS,
    body: JSON.stringify(updates),
  });
}

export async function addManualProduct(imageId: string, product: ManualProductInput): Promise<Product> {
  return authJson(`/api/photos/${encodeURIComponent(imageId)}/products`, {
    method: "POST",
    headers: JSON_HEADERS,
    body: JSON.stringify(product),
  });
}

export async function reextractPhoto(imageId: string): Promise<ReextractResult> {
  return authJson(`/api/photos/${encodeURIComponent(imageId)}/re-extract`, { method: "POST" });
}

export type StoreLocationInput = {
  name: string;
  latitude: number;
  longitude: number;
  match_radius_m?: number;
};

export async function fetchStoreLocations(): Promise<StoreLocation[]> {
  return authJson("/api/store-locations");
}

export async function createStoreLocation(body: StoreLocationInput): Promise<CreateStoreLocationResult> {
  return authJson("/api/store-locations", {
    method: "POST",
    headers: JSON_HEADERS,
    body: JSON.stringify(body),
  });
}

export async function updateStoreLocation(storeId: string, body: StoreLocationInput): Promise<StoreLocation> {
  return authJson(`/api/store-locations/${encodeURIComponent(storeId)}`, {
    method: "PUT",
    headers: JSON_HEADERS,
    body: JSON.stringify(body),
  });
}

export async function deleteStoreLocation(storeId: string): Promise<void> {
  await authVoid(`/api/store-locations/${encodeURIComponent(storeId)}`, { method: "DELETE" });
}

export async function assignPhotoStore(imageId: string, storeLocationId: string): Promise<void> {
  await authVoid(`/api/photos/${encodeURIComponent(imageId)}/store-location`, {
    method: "PUT",
    headers: JSON_HEADERS,
    body: JSON.stringify({ store_location_id: storeLocationId }),
  });
}
