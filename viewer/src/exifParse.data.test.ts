import { execSync } from "node:child_process";
import { existsSync, readFileSync, readdirSync, statSync } from "node:fs";
import { basename, dirname, extname, join } from "node:path";
import { fileURLToPath } from "node:url";
import { describe, expect, it } from "vitest";
import { parseExifMetadata } from "./exifParse";

const DATA_ROOT = join(fileURLToPath(new URL(".", import.meta.url)), "../../data");
const IMAGE_EXT = new Set([".jpg", ".jpeg", ".png", ".webp"]);

interface ExpectedMetadata {
  gpsLatitude?: number;
  gpsLongitude?: number;
  capturedAt?: string;
}

function walkImages(dir: string, out: string[] = []): string[] {
  if (!existsSync(dir)) return out;
  for (const name of readdirSync(dir)) {
    const path = join(dir, name);
    const st = statSync(path);
    if (st.isDirectory()) walkImages(path, out);
    else if (IMAGE_EXT.has(extname(name).toLowerCase())) out.push(path);
  }
  return out;
}

function loadJsonMeta(jsonPath: string): ExpectedMetadata | null {
  if (!existsSync(jsonPath)) return null;
  const raw = JSON.parse(readFileSync(jsonPath, "utf8")) as {
    meta?: ExpectedMetadata & {
      gps_latitude?: number;
      gps_longitude?: number;
      captured_at?: string;
    };
    gps_latitude?: number;
    gps_longitude?: number;
    captured_at?: string;
  };
  const meta = raw.meta ?? raw;
  return {
    gpsLatitude: meta.gps_latitude,
    gpsLongitude: meta.gps_longitude,
    capturedAt: meta.captured_at,
  };
}

function capturedAtToExif(capturedAt: string): string {
  const [date, time] = capturedAt.split("T");
  return `${date.replace(/-/g, ":")} ${time}`;
}

function parseImageMetadata(imagePath: string) {
  const buf = readFileSync(imagePath);
  return parseExifMetadata(buf.buffer.slice(buf.byteOffset, buf.byteOffset + buf.byteLength));
}

function expectMatchesMetadata(imagePath: string, expected: ExpectedMetadata) {
  const parsed = parseImageMetadata(imagePath);
  const rel = imagePath.replace(`${DATA_ROOT}/`, "");

  if (expected.capturedAt) {
    const want = capturedAtToExif(expected.capturedAt);
    expect(parsed.dateTimeOriginal ?? parsed.dateTime, `${rel} datetime`).toBe(want);
  }

  if (expected.gpsLatitude != null && expected.gpsLongitude != null) {
    expect(parsed.gpsLatitude, `${rel} latitude`).toBeCloseTo(expected.gpsLatitude, 4);
    expect(parsed.gpsLongitude, `${rel} longitude`).toBeCloseTo(expected.gpsLongitude, 4);
  }
}

function exiftoolAvailable(): boolean {
  try {
    execSync("exiftool -ver", { stdio: "ignore" });
    return true;
  } catch {
    return false;
  }
}

function loadExiftoolMetadata(imagePath: string): ExpectedMetadata {
  const rows = JSON.parse(
    execSync(
      `exiftool -n -json -GPSLatitude -GPSLongitude -DateTimeOriginal "${imagePath}"`,
      { encoding: "utf8" },
    ),
  ) as Array<{
    GPSLatitude?: number;
    GPSLongitude?: number;
    DateTimeOriginal?: string;
  }>;
  const row = rows[0] ?? {};
  return {
    gpsLatitude: row.GPSLatitude,
    gpsLongitude: row.GPSLongitude,
    capturedAt: row.DateTimeOriginal
      ? row.DateTimeOriginal.replace(" ", "T").replace(/^(\d{4}):(\d{2}):(\d{2})/, "$1-$2-$3")
      : undefined,
  };
}

const dataImages = walkImages(DATA_ROOT).sort();
const jsonBackedImages = dataImages.filter((imagePath) => {
  const stem = basename(imagePath, extname(imagePath));
  const expected = loadJsonMeta(join(dirname(imagePath), `${stem}.json`));
  return expected?.capturedAt != null || expected?.gpsLatitude != null;
});
const unlabeledImages = dataImages.filter((imagePath) => !jsonBackedImages.includes(imagePath));

describe.skipIf(!existsSync(DATA_ROOT))("parseExifMetadata against grocery-prices/data", () => {
  it("finds image fixtures in data/", () => {
    expect(dataImages.length).toBeGreaterThan(0);
  });

  describe("JSON sidecar metadata", () => {
    it.each(jsonBackedImages)("%s", (imagePath) => {
      const stem = basename(imagePath, extname(imagePath));
      const expected = loadJsonMeta(join(dirname(imagePath), `${stem}.json`));
      expect(expected).not.toBeNull();
      expectMatchesMetadata(imagePath, expected!);
    });
  });

  describe.skipIf(!exiftoolAvailable())("images without JSON sidecars", () => {
    it.each(unlabeledImages)("%s", (imagePath) => {
      const expected = loadExiftoolMetadata(imagePath);
      if (!expected.capturedAt && expected.gpsLatitude == null) {
        expect(parseImageMetadata(imagePath)).toEqual({});
        return;
      }
      expectMatchesMetadata(imagePath, expected);
    });
  });
});
