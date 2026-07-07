import type { ClientExifPayload, DuplicateAction, ExtractBackend } from "@/shared/api/api";

export type UploadQueueStatus =
  | "queued"
  | "compressing"
  | "uploading"
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
  file: File;
  uploadFile?: File;
  clientExif?: ClientExifPayload;
  uploadProgress?: number;
  processingStartedAt?: number;
  extractBackend?: ExtractBackend;
  productCount?: number;
  imageId?: string;
  error?: string;
  duplicateOf?: string;
  extractionEmpty?: boolean;
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

function thumbnailUrlForFile(file: File): string {
  return URL.createObjectURL(file);
}

export function createQueueItem(file: File): UploadQueueItem {
  return {
    id: crypto.randomUUID(),
    label: file.name || "Photo",
    thumbnailUrl: thumbnailUrlForFile(file),
    status: "queued",
    file,
    uploadFile: file,
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
