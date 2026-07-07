import {
  MAX_SCALE_REFINEMENTS,
  guessCompressParams,
  qualityForTargetSize,
  scaleForTargetSize,
} from "./compressHeuristic";

export const COMPRESS_TARGET_BYTES = 450 * 1024;
/** WebP quality for non-WebP photos already under the size target (no downscaling). */
export const FULL_RES_WEBP_QUALITY = 1;

export interface CompressImageResult {
  compressed: boolean;
  blob: Blob;
  downloadName: string;
  thumbnailUrl: string;
  error?: string;
}

function isWebpFile(file: File): boolean {
  const fileName = file.name || "photo";
  return file.type === "image/webp" || fileName.toLowerCase().endsWith(".webp");
}

function downloadNameFor(file: File): string {
  const fileName = file.name || "photo";
  const baseName = fileName.replace(/\.[^.]+$/, "") || "photo";
  return `${baseName}.webp`;
}

function outputDownloadName(file: File): string {
  return isWebpFile(file) ? file.name || "photo" : downloadNameFor(file);
}

function passthroughResult(file: File): CompressImageResult {
  return {
    compressed: false,
    blob: file,
    downloadName: file.name || "photo",
    thumbnailUrl: "",
  };
}

function compressedResult(file: File, blob: Blob): CompressImageResult {
  return {
    compressed: true,
    blob,
    downloadName: outputDownloadName(file),
    thumbnailUrl: URL.createObjectURL(blob),
  };
}

async function loadImageBitmap(file: File): Promise<ImageBitmap> {
  try {
    return await createImageBitmap(file);
  } catch {
    const url = URL.createObjectURL(file);
    try {
      const img = await new Promise<HTMLImageElement>((resolve, reject) => {
        const el = new Image();
        el.onload = () => resolve(el);
        el.onerror = () => reject(new Error("Could not decode image"));
        el.src = url;
      });
      return await createImageBitmap(img);
    } finally {
      URL.revokeObjectURL(url);
    }
  }
}

function canvasToWebpBlob(canvas: HTMLCanvasElement, quality: number): Promise<Blob> {
  return new Promise((resolve, reject) => {
    canvas.toBlob(
      (blob) => (blob ? resolve(blob) : reject(new Error("Compression failed"))),
      "image/webp",
      quality,
    );
  });
}

async function encodeWebpAt(
  bitmap: ImageBitmap,
  scale: number,
  quality: number,
): Promise<Blob> {
  const width = Math.max(1, Math.round(bitmap.width * scale));
  const height = Math.max(1, Math.round(bitmap.height * scale));
  const canvas = document.createElement("canvas");
  canvas.width = width;
  canvas.height = height;
  const ctx = canvas.getContext("2d");
  if (!ctx) throw new Error("Canvas not supported");
  ctx.imageSmoothingEnabled = true;
  ctx.imageSmoothingQuality = "high";
  ctx.drawImage(bitmap, 0, 0, width, height);
  return canvasToWebpBlob(canvas, quality);
}

async function compressBitmap(
  bitmap: ImageBitmap,
  originalBytes: number,
  targetBytes: number,
): Promise<Blob> {
  const encode = async (scale: number, quality: number) => {
    const blob = await encodeWebpAt(bitmap, scale, quality);
    return { blob, scale, quality };
  };

  const guess = guessCompressParams(
    originalBytes,
    targetBytes,
    bitmap.width,
    bitmap.height,
  );
  let attempt = await encode(guess.scale, guess.quality);

  let refinements = 0;
  while (attempt.blob.size > targetBytes && refinements < MAX_SCALE_REFINEMENTS) {
    const nextScale = scaleForTargetSize(attempt.blob.size, attempt.scale, targetBytes);
    if (nextScale >= attempt.scale * 0.99) break;
    attempt = await encode(nextScale, attempt.quality);
    refinements += 1;
  }

  if (attempt.blob.size <= targetBytes) {
    const nextQuality = qualityForTargetSize(
      attempt.blob.size,
      attempt.quality,
      targetBytes,
    );
    if (nextQuality > attempt.quality + 0.02) {
      const tuned = await encode(attempt.scale, nextQuality);
      if (tuned.blob.size <= targetBytes) {
        attempt = tuned;
      }
    }
  }

  return attempt.blob;
}

export async function compressImageFile(file: File): Promise<CompressImageResult> {
  if (file.size <= COMPRESS_TARGET_BYTES && isWebpFile(file)) {
    return passthroughResult(file);
  }

  try {
    const bitmap = await loadImageBitmap(file);
    try {
      const blob =
        file.size <= COMPRESS_TARGET_BYTES
          ? await encodeWebpAt(bitmap, 1, FULL_RES_WEBP_QUALITY)
          : await compressBitmap(bitmap, file.size, COMPRESS_TARGET_BYTES);
      return compressedResult(file, blob);
    } finally {
      bitmap.close();
    }
  } catch (err) {
    return {
      ...passthroughResult(file),
      error: err instanceof Error ? err.message : "Compression failed",
    };
  }
}

export function revokeCompressResult(result: CompressImageResult) {
  if (result.thumbnailUrl.startsWith("blob:")) {
    URL.revokeObjectURL(result.thumbnailUrl);
  }
}
