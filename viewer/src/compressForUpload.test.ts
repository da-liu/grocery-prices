import { describe, expect, it } from "vitest";
import { scaledDimensions, uploadFileName } from "./compressForUpload";

describe("scaledDimensions", () => {
  it("keeps size when already within max dimension", () => {
    expect(scaledDimensions(800, 600, 1920)).toEqual({ width: 800, height: 600 });
  });

  it("scales down preserving aspect ratio", () => {
    const result = scaledDimensions(5712, 4284, 1920);
    expect(result.width).toBe(1920);
    expect(result.height).toBe(1440);
  });
});

describe("uploadFileName", () => {
  it("replaces extension with .webp", () => {
    expect(uploadFileName("IMG_2027.HEIC")).toBe("IMG_2027.webp");
  });
});
