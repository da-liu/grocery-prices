import { describe, expect, it } from "vitest";
import {
  COMPRESS_TARGET_BYTES,
  FULL_RES_WEBP_QUALITY,
  formatDuration,
  formatEncodeStep,
} from "./compressImage";

describe("full-res WebP upload encoding", () => {
  it("uses a high quality setting without downscaling small photos", () => {
    expect(FULL_RES_WEBP_QUALITY).toBeGreaterThan(0.85);
    expect(COMPRESS_TARGET_BYTES).toBe(450 * 1024);
  });
});

describe("formatDuration", () => {
  it("formats sub-second durations in milliseconds", () => {
    expect(formatDuration(450)).toBe("450 ms");
  });

  it("formats seconds with one decimal", () => {
    expect(formatDuration(2300)).toBe("2.3 s");
  });

  it("formats minutes and seconds", () => {
    expect(formatDuration(65_000)).toBe("1m 5s");
  });
});

describe("formatEncodeStep", () => {
  it("includes loop timing and phase", () => {
    const line = formatEncodeStep({
      phase: "guess",
      pass: 0,
      iteration: 1,
      scale: 1,
      width: 2048,
      height: 1536,
      quality: 0.85,
      outputBytes: 420_000,
      underTarget: true,
      searchLow: 0,
      searchHigh: 0,
      durationMs: 38,
    });

    expect(line).toContain("pass 1");
    expect(line).toContain("initial guess");
    expect(line).toContain("q 85%");
    expect(line).toContain("38 ms");
    expect(line).toContain("under target");
  });
});
