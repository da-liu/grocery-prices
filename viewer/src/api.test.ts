import { describe, expect, it } from "vitest";
import { ApiError, buildUploadForm, describeRequestError, isAuthError } from "./api";

describe("isAuthError", () => {
  it("returns true only for 401 ApiError", () => {
    expect(isAuthError(new ApiError("Sign in required", 401))).toBe(true);
    expect(isAuthError(new ApiError("Server error", 500))).toBe(false);
    expect(isAuthError(new Error("Failed to fetch"))).toBe(false);
  });
});

describe("describeRequestError", () => {
  it("keeps non-network error messages unchanged", () => {
    expect(describeRequestError(new Error("503 from backend"), "status", "https://api.example.com")).toBe(
      "503 from backend",
    );
  });

  it("formats upload fetch failures clearly", () => {
    expect(describeRequestError(new Error("Failed to fetch"), "upload", "https://api.example.com")).toBe(
      "Could not reach API at https://api.example.com. Check network or try again.",
    );
  });

  it("formats status polling fetch failures with recovery hint", () => {
    expect(describeRequestError(new Error("Load failed"), "status", "https://api.example.com")).toBe(
      "Lost connection while checking upload progress at https://api.example.com. Your photo may still finish processing; refresh in a moment.",
    );
  });
});

describe("buildUploadForm", () => {
  it("includes optional client metadata aligned with uploaded files", () => {
    const file = new File(["photo"], "IMG_0001.jpg", { type: "image/jpeg" });
    const form = buildUploadForm(
      [file],
      "shelf",
      undefined,
      [
        {
          GPSLatitude: 43.65,
          GPSLongitude: -79.38,
          captured_at: "2026-07-04T18:30:00-04:00",
          date_folder: "2026_07_04",
        },
      ],
    );

    expect(form.get("source")).toBe("upload");
    expect(form.get("exif_json")).toBe(
      JSON.stringify([
        {
          GPSLatitude: 43.65,
          GPSLongitude: -79.38,
          captured_at: "2026-07-04T18:30:00-04:00",
          date_folder: "2026_07_04",
        },
      ]),
    );
  });

  it("omits exif_json when no client metadata is present", () => {
    const file = new File(["photo"], "photo.jpg", { type: "image/jpeg" });
    const form = buildUploadForm([file], "shelf", undefined, [undefined]);
    expect(form.get("exif_json")).toBeNull();
  });
});
