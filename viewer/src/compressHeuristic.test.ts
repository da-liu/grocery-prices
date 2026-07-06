import { describe, expect, it } from "vitest";
import {
  guessCompressParams,
  initialScaleFromOriginal,
  qualityForTargetSize,
  scaleForTargetSize,
} from "./compressHeuristic";

describe("compressHeuristic", () => {
  it("starts below full scale for large originals", () => {
    const scale = initialScaleFromOriginal(5_000_000, 450 * 1024, 12_000_000);
    expect(scale).toBeLessThan(1);
    expect(scale).toBeGreaterThan(0.2);
  });

  it("keeps full scale for modest originals", () => {
    const scale = initialScaleFromOriginal(900_000, 450 * 1024, 3_000_000);
    expect(scale).toBeGreaterThan(0.7);
  });

  it("raises quality when probe is under target", () => {
    const q = qualityForTargetSize(300 * 1024, 0.85, 450 * 1024);
    expect(q).toBeGreaterThan(0.85);
    expect(q).toBeLessThanOrEqual(0.95);
  });

  it("shrinks scale when probe is over target", () => {
    const scale = scaleForTargetSize(900 * 1024, 1, 450 * 1024);
    expect(scale).toBeLessThan(0.75);
    expect(scale).toBeGreaterThan(0.4);
  });

  it("returns a guess with probe quality", () => {
    const guess = guessCompressParams(2_000_000, 450 * 1024, 4000, 3000);
    expect(guess.quality).toBe(0.85);
    expect(guess.scale).toBeGreaterThan(0);
    expect(guess.scale).toBeLessThanOrEqual(1);
  });
});
