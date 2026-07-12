export const EXTRACTION_ESTIMATE_MS = 3_000;

/** Estimated progress while extraction runs; caps at 95% until the server finishes. */
export function extractionProgressPercent(startedAt: number | undefined, now = Date.now()): number {
  if (startedAt == null) return 0;
  const elapsed = Math.max(0, now - startedAt);
  return Math.min(95, Math.round((elapsed / EXTRACTION_ESTIMATE_MS) * 95));
}
