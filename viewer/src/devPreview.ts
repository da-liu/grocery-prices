import type { Product } from "./types";

/** Set to true to preview loading and upload UI states locally. */
export const DEV_FORCE_LOADING = false;

/** Simulated upload queue when DEV_FORCE_LOADING is on (null to disable). */
export const DEV_PREVIEW_UPLOAD: {
  done: number;
  processing: number;
  queued: number;
} | null = null;

export type DevPreviewMode = "empty-extraction" | null;

function readPreviewMode(): DevPreviewMode {
  const preview = new URLSearchParams(window.location.search).get("preview");
  return preview === "empty-extraction" ? "empty-extraction" : null;
}

export const DEV_PREVIEW_MODE = readPreviewMode();

export const DEV_PREVIEW_EMPTY_IMAGE_URL = "/onboarding-shelf-sample.jpg";

export const DEV_PREVIEW_EMPTY_PRODUCT: Product = {
  id: "preview-empty-product",
  image_id: "preview-empty-image",
  image_path: DEV_PREVIEW_EMPTY_IMAGE_URL,
  product_name: "",
  price: null,
  price_currency: "CAD",
  category: "",
  captured_at: "2026-07-03T20:45:00Z",
  extraction_empty: true,
  location: {
    store: "Unknown store",
    latitude: 43.65349,
    longitude: -79.39821,
  },
};
