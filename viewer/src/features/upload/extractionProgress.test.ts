import { describe, expect, it } from "vitest";
import {
  EXTRACTION_ESTIMATE_MS,
  extractionEstimateMs,
  extractionProgressPercent,
} from "./extractionProgress";

describe("extractionProgress", () => {
  it("uses 25s for cursor and 3s for gemini direct", () => {
    expect(EXTRACTION_ESTIMATE_MS.cursor).toBe(25_000);
    expect(EXTRACTION_ESTIMATE_MS.gemini_direct).toBe(3_000);
    expect(extractionEstimateMs("cursor")).toBe(25_000);
    expect(extractionEstimateMs("gemini_direct")).toBe(3_000);
    expect(extractionEstimateMs(undefined)).toBe(25_000);
  });

  it("ramps toward 95% over the estimate", () => {
    const startedAt = 1_000;
    expect(extractionProgressPercent(startedAt, "gemini_direct", startedAt)).toBe(0);
    expect(extractionProgressPercent(startedAt, "gemini_direct", startedAt + 1_500)).toBe(48);
    expect(extractionProgressPercent(startedAt, "gemini_direct", startedAt + 3_000)).toBe(95);
    expect(extractionProgressPercent(startedAt, "gemini_direct", startedAt + 10_000)).toBe(95);
  });
});
