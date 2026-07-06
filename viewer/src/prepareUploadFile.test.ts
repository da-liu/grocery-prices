import { describe, expect, it, vi } from "vitest";
import { photoMetadataToClientExif, prepareUploadFile } from "./prepareUploadFile";

vi.mock("./compressImage", () => ({
  compressImageFile: vi.fn(),
  revokeCompressResult: vi.fn(),
}));

import { compressImageFile, revokeCompressResult } from "./compressImage";

const mockedCompress = vi.mocked(compressImageFile);
const mockedRevoke = vi.mocked(revokeCompressResult);

describe("prepareUploadFile", () => {
  it("passes through small WebP files without re-encoding", async () => {
    mockedCompress.mockClear();
    mockedRevoke.mockClear();
    const file = new File([new Uint8Array([1, 2, 3])], "photo.webp", {
      type: "image/webp",
    });

    const result = await prepareUploadFile(file);

    expect(result.file).toBe(file);
    expect(result.compressed).toBe(false);
    expect(mockedCompress).not.toHaveBeenCalled();
  });

  it("encodes small JPEG files to full-resolution WebP", async () => {
    mockedCompress.mockClear();
    mockedRevoke.mockClear();
    const source = new File([new Uint8Array([0xff, 0xd8, 0xff])], "photo.jpg", {
      type: "image/jpeg",
    });
    const webpBlob = new Blob([new Uint8Array([1, 2, 3])], { type: "image/webp" });
    mockedCompress.mockResolvedValue({
      id: "id",
      fileName: "photo.jpg",
      originalSize: source.size,
      compressedSize: webpBlob.size,
      compressed: true,
      blob: webpBlob,
      thumbnailUrl: "blob:thumb",
      downloadName: "photo.webp",
      durationMs: 1,
      encodeSteps: [],
    });

    const result = await prepareUploadFile(source);

    expect(mockedCompress).toHaveBeenCalledWith(source, { encodeWebp: true });
    expect(result.compressed).toBe(true);
    expect(result.file.name).toBe("photo.webp");
    expect(result.file.type).toBe("image/webp");
    expect(mockedRevoke).toHaveBeenCalled();
  });

  it("throws when WebP encoding fails", async () => {
    mockedCompress.mockClear();
    mockedRevoke.mockClear();
    const source = new File([new Uint8Array([0xff, 0xd8, 0xff])], "photo.jpg", {
      type: "image/jpeg",
    });
    mockedCompress.mockResolvedValue({
      id: "id",
      fileName: "photo.jpg",
      originalSize: source.size,
      compressedSize: source.size,
      compressed: false,
      blob: source,
      thumbnailUrl: "",
      downloadName: "photo.jpg",
      durationMs: 1,
      encodeSteps: [],
      error: "Could not decode image",
    });

    await expect(prepareUploadFile(source)).rejects.toThrow("Could not decode image");
    expect(mockedRevoke).toHaveBeenCalled();
  });
});

describe("photoMetadataToClientExif", () => {
  it("maps GPS and capture time to server payload", () => {
    expect(
      photoMetadataToClientExif({
        dateTimeOriginal: "2026:07:04 18:30:00",
        gpsLatitude: 43.65,
        gpsLongitude: -79.38,
      }),
    ).toEqual({
      DateTimeOriginal: "2026:07:04 18:30:00",
      GPSLatitude: 43.65,
      GPSLongitude: -79.38,
    });
  });

  it("returns undefined when metadata is empty", () => {
    expect(photoMetadataToClientExif({})).toBeUndefined();
  });
});
