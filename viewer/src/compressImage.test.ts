import { describe, expect, it } from "vitest";
import { COMPRESS_TARGET_BYTES, FULL_RES_WEBP_QUALITY } from "./compressImage";

describe("compressImage constants", () => {
  it("uses full quality without downscaling small non-WebP photos", () => {
    expect(FULL_RES_WEBP_QUALITY).toBe(1);
    expect(COMPRESS_TARGET_BYTES).toBe(450 * 1024);
  });
});
