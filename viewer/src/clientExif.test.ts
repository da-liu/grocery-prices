import { afterEach, describe, expect, it, vi } from "vitest";
import {
  dateFolderFromCapturedAt,
  exifDatetimeToCapturedAt,
  formatIsoWithLocalOffset,
  normalizeExifDatetime,
  photoMetadataToClientExif,
} from "./clientExif";

describe("normalizeExifDatetime", () => {
  it("accepts colon-separated EXIF datetime", () => {
    expect(normalizeExifDatetime("2026:07:04 18:30:00")).toBe("2026:07:04 18:30:00");
  });

  it("accepts ISO datetime", () => {
    expect(normalizeExifDatetime("2026-07-04T18:30:00")).toBe("2026:07:04 18:30:00");
  });

  it("rejects invalid input", () => {
    expect(normalizeExifDatetime("2026-07")).toBeNull();
  });
});

describe("exifDatetimeToCapturedAt", () => {
  afterEach(() => {
    vi.restoreAllMocks();
  });

  it("converts EXIF datetime to ISO with local offset", () => {
    vi.spyOn(Date.prototype, "getTimezoneOffset").mockReturnValue(240);
    expect(exifDatetimeToCapturedAt("2026:07:04 18:30:00")).toBe("2026-07-04T18:30:00-04:00");
  });

  it("accepts ISO input", () => {
    vi.spyOn(Date.prototype, "getTimezoneOffset").mockReturnValue(0);
    expect(exifDatetimeToCapturedAt("2026-07-04T18:30:00")).toBe("2026-07-04T18:30:00+00:00");
  });
});

describe("formatIsoWithLocalOffset", () => {
  it("formats UTC offset", () => {
    const date = new Date(2026, 6, 4, 18, 30, 0);
    vi.spyOn(date, "getTimezoneOffset").mockReturnValue(0);
    expect(formatIsoWithLocalOffset(date)).toBe("2026-07-04T18:30:00+00:00");
    vi.restoreAllMocks();
  });
});

describe("dateFolderFromCapturedAt", () => {
  it("uses the local calendar date", () => {
    expect(dateFolderFromCapturedAt("2026-07-04T18:30:00-04:00")).toBe("2026_07_04");
  });
});

describe("photoMetadataToClientExif", () => {
  afterEach(() => {
    vi.restoreAllMocks();
  });

  it("maps GPS and capture time to upload payload", () => {
    vi.spyOn(Date.prototype, "getTimezoneOffset").mockReturnValue(240);
    expect(
      photoMetadataToClientExif({
        dateTimeOriginal: "2026:07:04 18:30:00",
        gpsLatitude: 43.65,
        gpsLongitude: -79.38,
      }),
    ).toEqual({
      captured_at: "2026-07-04T18:30:00-04:00",
      date_folder: "2026_07_04",
      GPSLatitude: 43.65,
      GPSLongitude: -79.38,
    });
  });

  it("drops out-of-range GPS", () => {
    vi.spyOn(Date.prototype, "getTimezoneOffset").mockReturnValue(0);
    expect(
      photoMetadataToClientExif({
        dateTimeOriginal: "2026:07:04 18:30:00",
        gpsLatitude: 120,
        gpsLongitude: 0,
      }),
    ).toEqual({
      captured_at: "2026-07-04T18:30:00+00:00",
      date_folder: "2026_07_04",
    });
  });

  it("returns undefined when metadata is empty", () => {
    expect(photoMetadataToClientExif({})).toBeUndefined();
  });
});
