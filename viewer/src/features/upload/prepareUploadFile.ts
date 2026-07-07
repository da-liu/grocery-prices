import type { ClientExifPayload } from "@/shared/api/api";
import { photoMetadataToClientExif } from "./clientExif";
import { compressImageFile, revokeCompressResult } from "./compressImage";
import { parseExifMetadata } from "./exifParse";

export async function prepareUploadFile(file: File): Promise<{
  file: File;
  clientExif?: ClientExifPayload;
  compressed: boolean;
}> {
  const buffer = await file.arrayBuffer();
  const clientExif = photoMetadataToClientExif(parseExifMetadata(buffer));

  const result = await compressImageFile(file);
  if (result.error) {
    revokeCompressResult(result);
    throw new Error(result.error);
  }

  if (!result.compressed) {
    return { file, clientExif, compressed: false };
  }

  const uploadFile = new File([result.blob], result.downloadName, {
    type: result.blob.type || "image/webp",
  });
  revokeCompressResult(result);
  return { file: uploadFile, clientExif, compressed: true };
}
