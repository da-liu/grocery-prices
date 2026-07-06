import {
  MAX_SCALE_REFINEMENTS,
  guessCompressParams,
  qualityForTargetSize,
  scaleForTargetSize,
} from "./compressHeuristic";

export const COMPRESS_TARGET_BYTES = 450 * 1024;
/** WebP quality for photos already under the size target (no downscaling). */
export const FULL_RES_WEBP_QUALITY = 0.92;

export interface CompressEncodeStep {
  phase: "guess" | "scale-refine" | "quality-adjust" | "fallback";
  pass: number;
  iteration: number;
  scale: number;
  width: number;
  height: number;
  quality: number;
  outputBytes: number;
  underTarget: boolean;
  searchLow: number;
  searchHigh: number;
  durationMs: number;
}

export interface CompressImageResult {
  id: string;
  fileName: string;
  originalSize: number;
  compressedSize: number;
  compressed: boolean;
  blob: Blob;
  thumbnailUrl: string;
  downloadName: string;
  durationMs: number;
  encodeSteps: CompressEncodeStep[];
  error?: string;
}

export interface CompressImageOptions {
  targetBytes?: number;
  onEncodeStep?: (step: CompressEncodeStep) => void;
  /** When true, emit WebP at full resolution for photos already under targetBytes. */
  encodeWebp?: boolean;
}

export function formatFileSize(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}

export function formatDuration(ms: number): string {
  if (ms < 1000) return `${Math.round(ms)} ms`;
  if (ms < 60_000) return `${(ms / 1000).toFixed(1)} s`;
  const minutes = Math.floor(ms / 60_000);
  const seconds = Math.round((ms % 60_000) / 1000);
  return `${minutes}m ${seconds}s`;
}

export function formatEncodeStep(step: CompressEncodeStep): string {
  const qualityPct = Math.round(step.quality * 100);
  const size = formatFileSize(step.outputBytes);
  const fit = step.underTarget ? "under target" : "over target";
  const phase =
    step.phase === "fallback"
      ? "fallback"
      : step.phase === "guess"
        ? "initial guess"
        : step.phase === "scale-refine"
          ? `scale refine ${step.iteration}`
          : `quality adjust ${step.iteration}`;
  return (
    `pass ${step.pass + 1} · ${phase} · q ${qualityPct}% · ${step.width}×${step.height} ` +
    `@ scale ${step.scale.toFixed(2)} → ${size} (${fit}) · ${formatDuration(step.durationMs)}`
  );
}

function downloadNameFor(file: File): string {
  const fileName = file.name || "photo";
  const baseName = fileName.replace(/\.[^.]+$/, "") || "photo";
  return `${baseName}.webp`;
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
): Promise<{ blob: Blob; width: number; height: number }> {
  const width = Math.max(1, Math.round(bitmap.width * scale));
  const height = Math.max(1, Math.round(bitmap.height * scale));
  const canvas = document.createElement("canvas");
  canvas.width = width;
  canvas.height = height;
  const ctx = canvas.getContext("2d");
  if (!ctx) throw new Error("Canvas not supported");
  ctx.drawImage(bitmap, 0, 0, width, height);
  const blob = await canvasToWebpBlob(canvas, quality);
  return { blob, width, height };
}

interface EncodeAttempt {
  blob: Blob;
  scale: number;
  quality: number;
  width: number;
  height: number;
}

async function compressBitmapToTarget(
  bitmap: ImageBitmap,
  originalBytes: number,
  targetBytes: number,
  steps: CompressEncodeStep[],
  onEncodeStep?: (step: CompressEncodeStep) => void,
): Promise<Blob> {
  const recordStep = (
    phase: CompressEncodeStep["phase"],
    pass: number,
    iteration: number,
    attempt: EncodeAttempt,
    started: number,
  ) => {
    const step: CompressEncodeStep = {
      phase,
      pass,
      iteration,
      scale: attempt.scale,
      width: attempt.width,
      height: attempt.height,
      quality: attempt.quality,
      outputBytes: attempt.blob.size,
      underTarget: attempt.blob.size <= targetBytes,
      searchLow: 0,
      searchHigh: 0,
      durationMs: Math.round(performance.now() - started),
    };
    steps.push(step);
    onEncodeStep?.(step);
    return step;
  };

  const encode = async (
    phase: CompressEncodeStep["phase"],
    pass: number,
    iteration: number,
    scale: number,
    quality: number,
  ): Promise<EncodeAttempt> => {
    const started = performance.now();
    const { blob, width, height } = await encodeWebpAt(bitmap, scale, quality);
    const attempt = { blob, scale, quality, width, height };
    recordStep(phase, pass, iteration, attempt, started);
    return attempt;
  };

  let pass = 0;
  let iteration = 0;
  const guess = guessCompressParams(
    originalBytes,
    targetBytes,
    bitmap.width,
    bitmap.height,
  );
  let attempt = await encode("guess", pass, ++iteration, guess.scale, guess.quality);

  let refinements = 0;
  while (attempt.blob.size > targetBytes && refinements < MAX_SCALE_REFINEMENTS) {
    const nextScale = scaleForTargetSize(attempt.blob.size, attempt.scale, targetBytes);
    if (nextScale >= attempt.scale * 0.99) break;
    attempt = await encode("scale-refine", pass, ++iteration, nextScale, attempt.quality);
    refinements += 1;
  }

  if (attempt.blob.size <= targetBytes) {
    const nextQuality = qualityForTargetSize(
      attempt.blob.size,
      attempt.quality,
      targetBytes,
    );
    if (nextQuality > attempt.quality + 0.02) {
      const tuned = await encode(
        "quality-adjust",
        pass,
        ++iteration,
        attempt.scale,
        nextQuality,
      );
      if (tuned.blob.size <= targetBytes) {
        attempt = tuned;
      }
    }
    return attempt.blob;
  }

  const fallbackStarted = performance.now();
  const fallbackQuality = Math.max(0.25, attempt.quality - 0.15);
  const fallback = await encodeWebpAt(bitmap, attempt.scale, fallbackQuality);
  recordStep(
    "fallback",
    pass,
    ++iteration,
    {
      blob: fallback.blob,
      scale: attempt.scale,
      quality: fallbackQuality,
      width: fallback.width,
      height: fallback.height,
    },
    fallbackStarted,
  );
  return fallback.blob;
}

async function encodeFullResWebp(bitmap: ImageBitmap): Promise<Blob> {
  const { blob } = await encodeWebpAt(bitmap, 1, FULL_RES_WEBP_QUALITY);
  return blob;
}

export async function compressImageFile(
  file: File,
  options: CompressImageOptions = {},
): Promise<CompressImageResult> {
  const targetBytes = options.targetBytes ?? COMPRESS_TARGET_BYTES;
  const encodeWebp = options.encodeWebp ?? false;
  const onEncodeStep = options.onEncodeStep;
  const encodeSteps: CompressEncodeStep[] = [];
  const started = performance.now();
  const elapsed = () => Math.round(performance.now() - started);
  const id = crypto.randomUUID();
  const fileName = file.name || "Photo";
  const alreadyWebp =
    file.type === "image/webp" || fileName.toLowerCase().endsWith(".webp");

  if (file.size <= targetBytes && !encodeWebp) {
    return {
      id,
      fileName,
      originalSize: file.size,
      compressedSize: file.size,
      compressed: false,
      blob: file,
      thumbnailUrl: URL.createObjectURL(file),
      downloadName: fileName,
      durationMs: elapsed(),
      encodeSteps,
    };
  }

  if (file.size <= targetBytes && encodeWebp && alreadyWebp) {
    return {
      id,
      fileName,
      originalSize: file.size,
      compressedSize: file.size,
      compressed: false,
      blob: file,
      thumbnailUrl: URL.createObjectURL(file),
      downloadName: fileName,
      durationMs: elapsed(),
      encodeSteps,
    };
  }

  try {
    const bitmap = await loadImageBitmap(file);
    try {
      const blob =
        file.size <= targetBytes && encodeWebp
          ? await encodeFullResWebp(bitmap)
          : await compressBitmapToTarget(
              bitmap,
              file.size,
              targetBytes,
              encodeSteps,
              onEncodeStep,
            );

      return {
        id,
        fileName,
        originalSize: file.size,
        compressedSize: blob.size,
        compressed: true,
        blob,
        thumbnailUrl: URL.createObjectURL(blob),
        downloadName: downloadNameFor(file),
        durationMs: elapsed(),
        encodeSteps,
      };
    } finally {
      bitmap.close();
    }
  } catch (err) {
    return {
      id,
      fileName,
      originalSize: file.size,
      compressedSize: file.size,
      compressed: false,
      blob: file,
      thumbnailUrl: "",
      downloadName: fileName,
      durationMs: elapsed(),
      encodeSteps,
      error: err instanceof Error ? err.message : "Compression failed",
    };
  }
}

export function revokeCompressResult(result: CompressImageResult) {
  if (result.thumbnailUrl.startsWith("blob:")) {
    URL.revokeObjectURL(result.thumbnailUrl);
  }
}

export function downloadCompressedResult(result: CompressImageResult) {
  const url = URL.createObjectURL(result.blob);
  const anchor = document.createElement("a");
  anchor.href = url;
  anchor.download = result.downloadName;
  anchor.click();
  URL.revokeObjectURL(url);
}
