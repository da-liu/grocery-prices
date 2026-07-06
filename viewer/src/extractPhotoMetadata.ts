import { parseExifMetadata, type PhotoMetadata } from "./exifParse";

export type { PhotoMetadata };

export interface PhotoMetadataResult {
  id: string;
  fileName: string;
  fileSize: number;
  fileType: string;
  thumbnailUrl: string;
  metadata: PhotoMetadata;
  error?: string;
}

export function formatMetadataValue(value: string | number | undefined): string {
  if (value == null || value === "") return "—";
  if (typeof value === "number") {
    return Number.isInteger(value) ? String(value) : value.toFixed(6).replace(/\.?0+$/, "");
  }
  return value;
}

export function hasPhotoMetadata(metadata: PhotoMetadata): boolean {
  return (
    metadata.dateTime != null ||
    metadata.dateTimeOriginal != null ||
    metadata.gpsLatitude != null ||
    metadata.gpsLongitude != null
  );
}

function thumbnailUrlForFile(file: File): string {
  return URL.createObjectURL(file);
}

export async function extractPhotoMetadata(file: File): Promise<PhotoMetadataResult> {
  const ext = file.name.split(".").pop()?.toLowerCase() ?? "";
  const thumbnailUrl = thumbnailUrlForFile(file);

  try {
    const buffer = await file.arrayBuffer();
    return {
      id: crypto.randomUUID(),
      fileName: file.name || "Photo",
      fileSize: file.size,
      fileType: file.type || ext || "unknown",
      thumbnailUrl,
      metadata: parseExifMetadata(buffer),
    };
  } catch (err) {
    return {
      id: crypto.randomUUID(),
      fileName: file.name || "Photo",
      fileSize: file.size,
      fileType: file.type || ext || "unknown",
      thumbnailUrl,
      metadata: {},
      error: err instanceof Error ? err.message : "Could not read metadata",
    };
  }
}

export function revokePhotoMetadataResult(result: PhotoMetadataResult) {
  if (result.thumbnailUrl.startsWith("blob:")) {
    URL.revokeObjectURL(result.thumbnailUrl);
  }
}
