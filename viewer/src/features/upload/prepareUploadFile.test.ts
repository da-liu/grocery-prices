import { describe, expect, it, vi } from "vitest";
import { prepareUploadFile } from "./prepareUploadFile";

vi.mock("./compressImage", () => ({
  compressImageFile: vi.fn(),
  revokeCompressResult: vi.fn(),
}));

import { compressImageFile, revokeCompressResult } from "./compressImage";

const mockedCompress = vi.mocked(compressImageFile);
const mockedRevoke = vi.mocked(revokeCompressResult);

function compressResult(
  blob: Blob,
  downloadName: string,
  compressed: boolean,
  thumbnailUrl = "blob:thumb",
) {
  return { compressed, blob, downloadName, thumbnailUrl };
}

describe("prepareUploadFile", () => {
  it("passes through small files without re-encoding", async () => {
    mockedCompress.mockClear();
    mockedRevoke.mockClear();
    const file = new File([new Uint8Array([1, 2, 3])], "photo.jpg", {
      type: "image/jpeg",
    });
    mockedCompress.mockResolvedValue(compressResult(file, "photo.jpg", false, ""));

    const result = await prepareUploadFile(file);

    expect(mockedCompress).toHaveBeenCalledWith(file);
    expect(result.file).toBe(file);
    expect(result.compressed).toBe(false);
  });

  it("compresses large files to JPEG", async () => {
    mockedCompress.mockClear();
    mockedRevoke.mockClear();
    const source = new File([new Uint8Array(500_000)], "photo.webp", {
      type: "image/webp",
    });
    const compressedBlob = new Blob([new Uint8Array([1, 2, 3])], { type: "image/jpeg" });
    mockedCompress.mockResolvedValue(compressResult(compressedBlob, "photo.jpg", true));

    const result = await prepareUploadFile(source);

    expect(mockedCompress).toHaveBeenCalledWith(source);
    expect(result.compressed).toBe(true);
    expect(result.file.name).toBe("photo.jpg");
    expect(result.file.type).toBe("image/jpeg");
    expect(mockedRevoke).toHaveBeenCalled();
  });

  it("throws when compression fails", async () => {
    mockedCompress.mockClear();
    mockedRevoke.mockClear();
    const source = new File([new Uint8Array([0xff, 0xd8, 0xff])], "photo.jpg", {
      type: "image/jpeg",
    });
    mockedCompress.mockResolvedValue({
      ...compressResult(source, "photo.jpg", false, ""),
      error: "Could not decode image",
    });

    await expect(prepareUploadFile(source)).rejects.toThrow("Could not decode image");
    expect(mockedRevoke).toHaveBeenCalled();
  });
});
