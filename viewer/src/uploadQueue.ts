import type { DuplicateAction } from "./api";

export type UploadSource = "shelf" | "receipt";

export type UploadQueueStatus =
  | "preparing"
  | "queued"
  | "processing"
  | "awaiting_duplicate"
  | "done"
  | "failed"
  | "skipped";

export interface UploadQueueItem {
  id: string;
  label: string;
  thumbnailUrl: string;
  status: UploadQueueStatus;
  source: UploadSource;
  file: File;
  uploadFile?: File;
  productCount?: number;
  imageId?: string;
  error?: string;
  duplicateOf?: string;
  extractionEmpty?: boolean;
  detectedReceipt?: boolean;
}

export interface UploadToast {
  id: string;
  productCount: number;
  imageId: string;
  extractionEmpty?: boolean;
  note?: string;
}

export const UNKNOWN_STORE_HINT_KEY = "grocery-unknown-store-hint";

export function shouldNotifyUnknownStoreHint(
  needsStoreLabel: boolean,
  alreadyShownThisSession: boolean,
): boolean {
  return needsStoreLabel && !alreadyShownThisSession;
}

export interface PendingDuplicate {
  itemId: string;
  duplicateOf: string;
  resolve: (action: DuplicateAction) => void;
}

export const UPLOAD_CONCURRENCY = 4;
export const MAX_BULK_BATCH = 8;

export function createQueueItem(file: File, source: UploadSource): UploadQueueItem {
  return {
    id: crypto.randomUUID(),
    label: file.name || "Photo",
    thumbnailUrl: "",
    status: "preparing",
    source,
    file,
  };
}

export function revokeQueueItem(item: UploadQueueItem) {
  if (item.thumbnailUrl.startsWith("blob:")) {
    URL.revokeObjectURL(item.thumbnailUrl);
  }
}

export function productCountFromResult(result: {
  product_count?: number;
  products?: unknown[];
  skipped?: boolean;
  extraction_empty?: boolean;
}): number {
  if (result.skipped) return 0;
  if (result.extraction_empty) return 0;
  return result.product_count ?? result.products?.length ?? 0;
}
