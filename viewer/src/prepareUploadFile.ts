import type { ClientExifPayload } from "./api";
import { compressImageFile, revokeCompressResult } from "./compressImage";
import { parseExifMetadata, type PhotoMetadata } from "./exifParse";

export function photoMetadataToClientExif(
  metadata: PhotoMetadata,
): ClientExifPayload | undefined {
  const payload: ClientExifPayload = {};
  if (metadata.gpsLatitude != null && metadata.gpsLongitude != null) {
    payload.GPSLatitude = metadata.gpsLatitude;
    payload.GPSLongitude = metadata.gpsLongitude;
  }
  const captured = metadata.dateTimeOriginal ?? metadata.dateTime;
  if (captured) {
    payload.DateTimeOriginal = captured;
  }
  return Object.keys(payload).length > 0 ? payload : undefined;
}

export async function prepareUploadFile(file: File): Promise<{
  file: File;
  clientExif?: ClientExifPayload;
  compressed: boolean;
}> {
  const buffer = await file.arrayBuffer();
  const clientExif = photoMetadataToClientExif(parseExifMetadata(buffer));

  const alreadyWebp =
    file.type === "image/webp" || file.name.toLowerCase().endsWith(".webp");
  if (alreadyWebp) {
    return { file, clientExif, compressed: false };
  }

  const result = await compressImageFile(file, { encodeWebp: true });
  if (result.error || !result.compressed) {
    const message = result.error ?? "Could not encode image as WebP";
    revokeCompressResult(result);
    throw new Error(message);
  }

  const uploadFile = new File([result.blob], result.downloadName, {
    type: result.blob.type || "image/webp",
  });
  revokeCompressResult(result);
  return { file: uploadFile, clientExif, compressed: true };
}
