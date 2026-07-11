import { describe, expect, it } from "vitest";
import { COMPRESS_TARGET_BYTES } from "./compressImage";

describe("compressImage constants", () => {
  it("targets 450KB before compressing to JPEG", () => {
    expect(COMPRESS_TARGET_BYTES).toBe(450 * 1024);
  });
});
