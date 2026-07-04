export interface GeoBounds {
  minLat: number;
  maxLat: number;
  minLon: number;
  maxLon: number;
}

export function mapsUrl(lat: number, lon: number) {
  return `https://www.google.com/maps?q=${lat},${lon}`;
}

export function mapsEmbedUrl(lat: number, lon: number, zoom = 15) {
  return `https://maps.google.com/maps?q=${lat},${lon}&z=${zoom}&output=embed`;
}

export function hasValidCoords(lat: number | null | undefined, lon: number | null | undefined) {
  return lat != null && lon != null && !(lat === 0 && lon === 0);
}

export function geoBoundsFromCoords(
  coords: ReadonlyArray<{ latitude: number; longitude: number }>,
): GeoBounds | null {
  if (!coords.length) return null;

  const lats = coords.map((coord) => coord.latitude);
  const lons = coords.map((coord) => coord.longitude);

  return {
    minLat: Math.min(...lats),
    maxLat: Math.max(...lats),
    minLon: Math.min(...lons),
    maxLon: Math.max(...lons),
  };
}

export function zoomForGeoBounds(bounds: GeoBounds, paddingFactor = 1.35): number {
  const latSpan = Math.max((bounds.maxLat - bounds.minLat) * paddingFactor, 0.0005);
  const lonSpan = Math.max((bounds.maxLon - bounds.minLon) * paddingFactor, 0.0005);
  const span = Math.max(latSpan, lonSpan);
  const zoom = Math.round(Math.log2(360 / span)) - 1;
  return Math.min(18, Math.max(10, zoom));
}

export function mapsEmbedUrlForBounds(bounds: GeoBounds, paddingFactor = 1.35): string {
  const centerLat = (bounds.minLat + bounds.maxLat) / 2;
  const centerLon = (bounds.minLon + bounds.maxLon) / 2;
  const zoom = zoomForGeoBounds(bounds, paddingFactor);
  return mapsEmbedUrl(centerLat, centerLon, zoom);
}
