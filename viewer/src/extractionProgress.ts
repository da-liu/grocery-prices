import type { ExtractBackend } from "./api";

export const EXTRACTION_ESTIMATE_MS: Record<ExtractBackend, number> = {
  cursor: 25_000,
  gemini_direct: 3_000,
};

export function extractionEstimateMs(backend: ExtractBackend | undefined): number {
  return EXTRACTION_ESTIMATE_MS[backend ?? "cursor"];
}

/** Estimated progress while extraction runs; caps at 95% until the server finishes. */
export function extractionProgressPercent(
  startedAt: number | undefined,
  backend: ExtractBackend | undefined,
  now = Date.now(),
): number {
  if (startedAt == null) return 0;
  const elapsed = Math.max(0, now - startedAt);
  const estimate = extractionEstimateMs(backend);
  return Math.min(95, Math.round((elapsed / estimate) * 95));
}
