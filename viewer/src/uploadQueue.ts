import type { UploadResult } from "./api";

export type UploadSource = "shelf" | "receipt";

export type UploadQueueStatus = "queued" | "processing" | "done" | "failed";

export interface UploadQueueItem {
  id: string;
  label: string;
  thumbnailUrl: string;
  status: UploadQueueStatus;
  source: UploadSource;
  file: File;
  productCount?: number;
  imageId?: string;
  error?: string;
}

export interface UploadToast {
  id: string;
  productCount: number;
  imageId: string;
}

export function createQueueItem(file: File, source: UploadSource): UploadQueueItem {
  return {
    id: crypto.randomUUID(),
    label: file.name || "Photo",
    thumbnailUrl: URL.createObjectURL(file),
    status: "queued",
    source,
    file,
  };
}

export function revokeQueueItem(item: UploadQueueItem) {
  URL.revokeObjectURL(item.thumbnailUrl);
}

export function productCountFromResult(result: UploadResult): number {
  return result.product_count ?? result.products.length;
}
