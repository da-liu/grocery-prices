/**
 * JPEG size heuristics for browser canvas encoding.
 *
 * Original file bytes alone are a weak predictor (same size can be different
 * resolutions or scene complexity). After decode, combine original bytes with
 * pixel count, then refine with one or two probe encodes.
 */

const PROBE_QUALITY = 0.85;
const QUALITY_GAMMA = 3.2;
export const MAX_SCALE_REFINEMENTS = 3;

function clamp(value: number, min: number, max: number): number {
  return Math.min(max, Math.max(min, value));
}

/**
 * Guess starting scale from JPEG file size and pixel count (no encode yet).
 * Uses target/orig ratio and a mild megapixel correction from calibration.
 */
export function initialScaleFromOriginal(
  originalBytes: number,
  targetBytes: number,
  pixels: number,
): number {
  const sizeRatio = targetBytes / originalBytes;
  const megapixels = pixels / 1_000_000;
  const base = Math.sqrt(sizeRatio) * 1.08;
  const megapixelFactor = 1 + 0.06 * Math.max(0, megapixels - 2);
  return clamp(base / megapixelFactor, 0.25, 1);
}

/**
 * When output is already under target, raise quality via power-law extrapolation.
 */
export function qualityForTargetSize(
  outputBytes: number,
  currentQuality: number,
  targetBytes: number,
): number {
  if (outputBytes <= 0) return currentQuality;
  if (outputBytes <= targetBytes) {
    return clamp(
      currentQuality * (targetBytes / outputBytes) ** (1 / QUALITY_GAMMA),
      0.25,
      0.95,
    );
  }
  return currentQuality;
}

/**
 * Shrink scale when output exceeds target. Output bytes ~ scale² at fixed quality.
 */
export function scaleForTargetSize(
  outputBytes: number,
  currentScale: number,
  targetBytes: number,
): number {
  if (outputBytes <= targetBytes) return currentScale;
  return currentScale * Math.sqrt(targetBytes / outputBytes) * 0.96;
}

interface CompressGuess {
  scale: number;
  quality: number;
}

/**
 * Full guess before any encode: scale from file stats, fixed probe quality.
 */
export function guessCompressParams(
  originalBytes: number,
  targetBytes: number,
  width: number,
  height: number,
): CompressGuess {
  return {
    scale: initialScaleFromOriginal(originalBytes, targetBytes, width * height),
    quality: PROBE_QUALITY,
  };
}
