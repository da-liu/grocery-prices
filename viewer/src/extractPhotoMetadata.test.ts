import { describe, expect, it } from "vitest";
import { parseExifMetadata } from "./exifParse";
import { formatMetadataValue, hasPhotoMetadata } from "./extractPhotoMetadata";

const TAG_DATETIME = 0x0132;
const TAG_EXIF_IFD = 0x8769;
const TAG_GPS_IFD = 0x8825;
const TAG_DATETIME_ORIGINAL = 0x9003;
const TAG_GPS_LAT_REF = 0x0001;
const TAG_GPS_LAT = 0x0002;
const TAG_GPS_LON_REF = 0x0003;
const TAG_GPS_LON = 0x0004;

function writeAscii(buffer: Uint8Array, offset: number, text: string) {
  for (let i = 0; i < text.length; i++) {
    buffer[offset + i] = text.charCodeAt(i);
  }
}

function writeU16(buffer: Uint8Array, offset: number, value: number, little = true) {
  const view = new DataView(buffer.buffer, buffer.byteOffset, buffer.byteLength);
  view.setUint16(offset, value, little);
}

function writeU32(buffer: Uint8Array, offset: number, value: number, little = true) {
  const view = new DataView(buffer.buffer, buffer.byteOffset, buffer.byteLength);
  view.setUint32(offset, value, little);
}

function writeRational(buffer: Uint8Array, offset: number, numerator: number, denominator: number) {
  writeU32(buffer, offset, numerator);
  writeU32(buffer, offset + 4, denominator);
}

function buildMinimalExifBuffer(): ArrayBuffer {
  const payload = new Uint8Array(400);
  const tiffStart = 0;

  writeAscii(payload, tiffStart, "II");
  writeU16(payload, tiffStart + 2, 42);
  writeU32(payload, tiffStart + 4, 8);

  const ifd0 = tiffStart + 8;
  writeU16(payload, ifd0, 3);

  const dateTime = "2026:07:04 12:00:00";
  writeU16(payload, ifd0 + 2, TAG_DATETIME);
  writeU16(payload, ifd0 + 4, 2);
  writeU32(payload, ifd0 + 6, dateTime.length + 1);
  writeU32(payload, ifd0 + 10, 350);
  writeAscii(payload, 350, dateTime);

  writeU16(payload, ifd0 + 14, TAG_EXIF_IFD);
  writeU16(payload, ifd0 + 16, 4);
  writeU32(payload, ifd0 + 18, 1);
  writeU32(payload, ifd0 + 22, 120);

  writeU16(payload, ifd0 + 26, TAG_GPS_IFD);
  writeU16(payload, ifd0 + 28, 4);
  writeU32(payload, ifd0 + 30, 1);
  writeU32(payload, ifd0 + 34, 180);

  writeU32(payload, ifd0 + 38, 0);

  const exifIfd = tiffStart + 120;
  const dateTimeOriginal = "2026:07:04 11:30:00";
  writeU16(payload, exifIfd, 1);
  writeU16(payload, exifIfd + 2, TAG_DATETIME_ORIGINAL);
  writeU16(payload, exifIfd + 4, 2);
  writeU32(payload, exifIfd + 6, dateTimeOriginal.length + 1);
  writeU32(payload, exifIfd + 10, 380);
  writeAscii(payload, 380, dateTimeOriginal);
  writeU32(payload, exifIfd + 14, 0);

  const gpsIfd = tiffStart + 180;
  writeU16(payload, gpsIfd, 4);

  writeU16(payload, gpsIfd + 2, TAG_GPS_LAT_REF);
  writeU16(payload, gpsIfd + 4, 2);
  writeU32(payload, gpsIfd + 6, 2);
  writeAscii(payload, gpsIfd + 10, "N");

  writeU16(payload, gpsIfd + 14, TAG_GPS_LAT);
  writeU16(payload, gpsIfd + 16, 5);
  writeU32(payload, gpsIfd + 18, 3);
  writeU32(payload, gpsIfd + 22, 300);
  writeRational(payload, 300, 43, 1);
  writeRational(payload, 308, 39, 1);
  writeRational(payload, 316, 12, 1);

  writeU16(payload, gpsIfd + 26, TAG_GPS_LON_REF);
  writeU16(payload, gpsIfd + 28, 2);
  writeU32(payload, gpsIfd + 30, 2);
  writeAscii(payload, gpsIfd + 34, "W");

  writeU16(payload, gpsIfd + 38, TAG_GPS_LON);
  writeU16(payload, gpsIfd + 40, 5);
  writeU32(payload, gpsIfd + 42, 3);
  writeU32(payload, gpsIfd + 46, 324);
  writeRational(payload, 324, 79, 1);
  writeRational(payload, 332, 22, 1);
  writeRational(payload, 340, 59, 1);

  writeU32(payload, gpsIfd + 50, 0);

  const exifPayload = new Uint8Array(6 + payload.length);
  writeAscii(exifPayload, 0, "Exif");
  exifPayload[4] = 0;
  exifPayload[5] = 0;
  exifPayload.set(payload, 6);

  const segmentLength = exifPayload.length + 2;
  const jpeg = new Uint8Array(6 + exifPayload.length);
  jpeg[0] = 0xff;
  jpeg[1] = 0xd8;
  jpeg[2] = 0xff;
  jpeg[3] = 0xe1;
  jpeg[4] = (segmentLength >> 8) & 0xff;
  jpeg[5] = segmentLength & 0xff;
  jpeg.set(exifPayload, 6);

  return jpeg.buffer;
}

describe("parseExifMetadata", () => {
  it("reads datetime and GPS from a minimal JPEG EXIF block", () => {
    const metadata = parseExifMetadata(buildMinimalExifBuffer());
    expect(metadata.dateTime).toBe("2026:07:04 12:00:00");
    expect(metadata.dateTimeOriginal).toBe("2026:07:04 11:30:00");
    expect(metadata.gpsLatitude).toBeCloseTo(43.653333, 5);
    expect(metadata.gpsLongitude).toBeCloseTo(-79.383056, 5);
  });

  it("returns empty metadata when no EXIF block is present", () => {
    expect(parseExifMetadata(new ArrayBuffer(8))).toEqual({});
  });
});

describe("formatMetadataValue", () => {
  it("formats missing and numeric values", () => {
    expect(formatMetadataValue(undefined)).toBe("—");
    expect(formatMetadataValue(43.6532)).toBe("43.6532");
    expect(formatMetadataValue("2026:07:04 11:30:00")).toBe("2026:07:04 11:30:00");
  });
});

describe("hasPhotoMetadata", () => {
  it("detects when any metadata field is present", () => {
    expect(hasPhotoMetadata({})).toBe(false);
    expect(hasPhotoMetadata({ gpsLatitude: 1 })).toBe(true);
    expect(hasPhotoMetadata({ dateTimeOriginal: "2026:07:04 11:30:00" })).toBe(true);
  });
});
