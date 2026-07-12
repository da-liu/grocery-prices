export interface ParsedCoords {
  latitude: number;
  longitude: number;
}

function isValidCoord(lat: number, lon: number): boolean {
  return Number.isFinite(lat) && Number.isFinite(lon) && lat >= -90 && lat <= 90 && lon >= -180 && lon <= 180;
}

function coords(lat: number, lon: number): ParsedCoords | null {
  if (!isValidCoord(lat, lon)) return null;
  return { latitude: lat, longitude: lon };
}

const PLAIN_COORDS = /^(-?\d+(?:\.\d+)?)\s*,\s*(-?\d+(?:\.\d+)?)$/;
const AT_COORDS = /@(-?\d+(?:\.\d+)?),(-?\d+(?:\.\d+)?)/;

/**
 * Parse plain "lat, lon" or a Google Maps URL into coordinates.
 * Supports @lat,lon, ?q=lat,lon, ?query=, and !3dlat!4dlon (data params).
 */
export function parseLocationInput(raw: string): ParsedCoords | null {
  const text = raw.trim();
  if (!text) return null;

  const plain = text.match(PLAIN_COORDS);
  if (plain) {
    return coords(Number(plain[1]), Number(plain[2]));
  }

  const atMatch = text.match(AT_COORDS);
  if (atMatch) {
    return coords(Number(atMatch[1]), Number(atMatch[2]));
  }

  try {
    const url = new URL(text);
    for (const key of ["q", "query", "ll"]) {
      const value = url.searchParams.get(key);
      if (!value) continue;
      const match = value.trim().match(PLAIN_COORDS);
      if (match) {
        return coords(Number(match[1]), Number(match[2]));
      }
    }

    // Google place data blob: !3d43.65!4d-79.38
    const dataMatch = text.match(/!3d(-?\d+(?:\.\d+)?)!4d(-?\d+(?:\.\d+)?)/);
    if (dataMatch) {
      return coords(Number(dataMatch[1]), Number(dataMatch[2]));
    }
  } catch {
    // Not a URL; already tried plain / @ patterns.
  }

  return null;
}

export function canCreateStoreFromDraft(draft: {
  name: string;
  latitude: number | null;
  longitude: number | null;
}): boolean {
  return Boolean(
    draft.name.trim() &&
      draft.latitude != null &&
      draft.longitude != null &&
      isValidCoord(draft.latitude, draft.longitude),
  );
}
