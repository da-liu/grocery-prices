import type { ClientExifPayload } from "@/shared/api/api";
import type { PhotoMetadata } from "./exifParse";

/** Normalize EXIF ASCII datetime to `YYYY:MM:DD HH:MM:SS`. */
export function normalizeExifDatetime(raw: string): string | null {
  const cleaned = raw.trim().replace("T", " ").split(".", 1)[0];
  if (cleaned.length < 19) return null;
  if (cleaned[4] === "-" && cleaned[7] === "-") {
    return `${cleaned.slice(0, 10).replace(/-/g, ":")} ${cleaned.slice(11)}`;
  }
  if (cleaned[4] === ":" && cleaned[7] === ":") {
    return cleaned;
  }
  return null;
}

/** Format a Date as ISO 8601 with the environment's local timezone offset. */
export function formatIsoWithLocalOffset(date: Date): string {
  const pad = (n: number) => String(n).padStart(2, "0");
  const y = date.getFullYear();
  const mo = pad(date.getMonth() + 1);
  const d = pad(date.getDate());
  const h = pad(date.getHours());
  const mi = pad(date.getMinutes());
  const s = pad(date.getSeconds());
  const offsetMin = -date.getTimezoneOffset();
  const sign = offsetMin >= 0 ? "+" : "-";
  const abs = Math.abs(offsetMin);
  return `${y}-${mo}-${d}T${h}:${mi}:${s}${sign}${pad(Math.floor(abs / 60))}:${pad(abs % 60)}`;
}

/** Parse EXIF capture time (no timezone) as local time and return ISO with offset. */
export function exifDatetimeToCapturedAt(exifDt: string): string | null {
  const normalized = normalizeExifDatetime(exifDt);
  if (!normalized) return null;
  const match = normalized.match(/^(\d{4}):(\d{2}):(\d{2}) (\d{2}):(\d{2}):(\d{2})$/);
  if (!match) return null;
  const [, ys, mos, ds, hs, mis, ss] = match;
  const local = new Date(+ys, +mos - 1, +ds, +hs, +mis, +ss);
  if (Number.isNaN(local.getTime())) return null;
  return formatIsoWithLocalOffset(local);
}

function dateFolderFromLocalDate(date: Date): string {
  const pad = (n: number) => String(n).padStart(2, "0");
  return `${date.getFullYear()}_${pad(date.getMonth() + 1)}_${pad(date.getDate())}`;
}

export function dateFolderFromCapturedAt(capturedAt: string): string | null {
  const date = new Date(capturedAt);
  if (Number.isNaN(date.getTime())) return null;
  return dateFolderFromLocalDate(date);
}

export function photoMetadataToClientExif(
  metadata: PhotoMetadata,
): ClientExifPayload | undefined {
  const payload: ClientExifPayload = {};

  if (metadata.gpsLatitude != null && metadata.gpsLongitude != null) {
    const { gpsLatitude: lat, gpsLongitude: lon } = metadata;
    if (lat >= -90 && lat <= 90 && lon >= -180 && lon <= 180) {
      payload.GPSLatitude = lat;
      payload.GPSLongitude = lon;
    }
  }

  const rawDt = metadata.dateTimeOriginal ?? metadata.dateTime;
  if (rawDt) {
    const capturedAt = exifDatetimeToCapturedAt(rawDt);
    if (capturedAt) {
      payload.captured_at = capturedAt;
      const folder = dateFolderFromCapturedAt(capturedAt);
      if (folder) payload.date_folder = folder;
    }
  }

  return Object.keys(payload).length > 0 ? payload : undefined;
}
