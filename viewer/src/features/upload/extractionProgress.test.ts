import { describe, expect, it } from "vitest";
import { EXTRACTION_ESTIMATE_MS, extractionProgressPercent } from "./extractionProgress";

describe("extractionProgress", () => {
  it("uses 3s estimate for Gemini extraction", () => {
    expect(EXTRACTION_ESTIMATE_MS).toBe(3_000);
  });

  it("ramps to 95% over the estimate and then caps", () => {
    const startedAt = 1_000;
    expect(extractionProgressPercent(startedAt, startedAt)).toBe(0);
    expect(extractionProgressPercent(startedAt, startedAt + 1_500)).toBe(48);
    expect(extractionProgressPercent(startedAt, startedAt + 3_000)).toBe(95);
    expect(extractionProgressPercent(startedAt, startedAt + 10_000)).toBe(95);
  });

  it("returns 0 when startedAt is missing", () => {
    expect(extractionProgressPercent(undefined, 5_000)).toBe(0);
  });
});
