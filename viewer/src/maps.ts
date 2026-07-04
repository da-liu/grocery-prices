export interface GeoBounds {
  minLat: number;
  maxLat: number;
  minLon: number;
  maxLon: number;
}

export interface MapViewport {
  centerLat: number;
  centerLon: number;
  zoom: number;
  width: number;
  height: number;
}

export interface PinPercentPosition {
  x: number;
  y: number;
}

export const STATIC_MAP_MAX_WIDTH = 640;
export const STATIC_MAP_DEFAULT_HEIGHT = 220;

const TILE_SIZE = 256;
const MIN_GEO_SPAN = 0.0005;

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

export function paddedGeoBounds(bounds: GeoBounds, paddingFactor = 1.35): GeoBounds {
  const latSpan = Math.max(bounds.maxLat - bounds.minLat, MIN_GEO_SPAN);
  const lonSpan = Math.max(bounds.maxLon - bounds.minLon, MIN_GEO_SPAN);
  const latPad = (latSpan * (paddingFactor - 1)) / 2;
  const lonPad = (lonSpan * (paddingFactor - 1)) / 2;

  return {
    minLat: bounds.minLat - latPad,
    maxLat: bounds.maxLat + latPad,
    minLon: bounds.minLon - lonPad,
    maxLon: bounds.maxLon + lonPad,
  };
}

export function zoomForGeoBounds(bounds: GeoBounds, paddingFactor = 1.35): number {
  const latSpan = Math.max((bounds.maxLat - bounds.minLat) * paddingFactor, MIN_GEO_SPAN);
  const lonSpan = Math.max((bounds.maxLon - bounds.minLon) * paddingFactor, MIN_GEO_SPAN);
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

export function staticMapDimensions(containerWidth: number, containerHeight: number) {
  const width = Math.max(1, Math.min(Math.round(containerWidth), STATIC_MAP_MAX_WIDTH));
  const height = Math.max(1, Math.round(containerHeight));
  return { width, height };
}

function latLngToWorld(lat: number, lon: number): { x: number; y: number } {
  const sinLat = Math.sin((lat * Math.PI) / 180);
  const x = TILE_SIZE * (0.5 + lon / 360);
  const y = TILE_SIZE * (0.5 - Math.log((1 + sinLat) / (1 - sinLat)) / (4 * Math.PI));
  return { x, y };
}

function worldToLatLng(x: number, y: number): { lat: number; lon: number } {
  const lon = (x / TILE_SIZE - 0.5) * 360;
  const n = Math.PI - (2 * Math.PI * y) / TILE_SIZE;
  const lat = (180 / Math.PI) * Math.atan(0.5 * (Math.exp(n) - Math.exp(-n)));
  return { lat, lon };
}

function fitZoomForWorldBounds(
  minX: number,
  minY: number,
  maxX: number,
  maxY: number,
  width: number,
  height: number,
): number {
  const worldWidth = maxX - minX;
  const worldHeight = maxY - minY;
  if (worldWidth <= 0 || worldHeight <= 0) return 14;

  for (let zoom = 21; zoom >= 0; zoom -= 1) {
    const scale = 2 ** zoom;
    if (worldWidth * scale <= width && worldHeight * scale <= height) {
      return zoom;
    }
  }

  return 0;
}

export function mapViewportForBounds(
  bounds: GeoBounds,
  width: number,
  height: number,
  paddingFactor = 1.35,
  zoomOffset = 0,
): MapViewport {
  const padded = paddedGeoBounds(bounds, paddingFactor);
  const northWest = latLngToWorld(padded.maxLat, padded.minLon);
  const southEast = latLngToWorld(padded.minLat, padded.maxLon);
  const centerWorld = {
    x: northWest.x + (southEast.x - northWest.x) / 2,
    y: northWest.y + (southEast.y - northWest.y) / 2,
  };
  const center = worldToLatLng(centerWorld.x, centerWorld.y);
  const zoom = fitZoomForWorldBounds(northWest.x, northWest.y, southEast.x, southEast.y, width, height);

  return {
    centerLat: center.lat,
    centerLon: center.lon,
    zoom: Math.min(21, Math.max(0, zoom + zoomOffset)),
    width,
    height,
  };
}

export function projectLatLonInViewport(
  lat: number,
  lon: number,
  viewport: MapViewport,
): { x: number; y: number } {
  const scale = 2 ** viewport.zoom;
  const center = latLngToWorld(viewport.centerLat, viewport.centerLon);
  const point = latLngToWorld(lat, lon);
  const centerPx = { x: center.x * scale, y: center.y * scale };
  const pointPx = { x: point.x * scale, y: point.y * scale };

  return {
    x: viewport.width / 2 + (pointPx.x - centerPx.x),
    y: viewport.height / 2 + (pointPx.y - centerPx.y),
  };
}

export function projectLatLonToPercent(
  lat: number,
  lon: number,
  viewport: MapViewport,
): PinPercentPosition {
  const pixel = projectLatLonInViewport(lat, lon, viewport);
  return {
    x: (pixel.x / viewport.width) * 100,
    y: (pixel.y / viewport.height) * 100,
  };
}

export function projectCoordsToPercent(
  coords: ReadonlyArray<{ latitude: number; longitude: number }>,
  viewport: MapViewport,
): PinPercentPosition[] {
  return coords.map((coord) => projectLatLonToPercent(coord.latitude, coord.longitude, viewport));
}

export interface StaticMapMarker {
  latitude: number;
  longitude: number;
  label?: string;
  color?: string;
  icon?: string;
  anchor?: { x: number; y: number };
}

export function markerLabelForStore(name: string, index: number): string {
  const match = name.match(/[A-Za-z0-9]/);
  if (match) return match[0].toUpperCase();
  return String.fromCharCode(65 + (index % 26));
}

export function staticMapMarkerParam(marker: StaticMapMarker): string {
  const parts: string[] = [];
  if (marker.icon) {
    parts.push(`icon:${marker.icon}`);
    if (marker.anchor) parts.push(`anchor:${marker.anchor.x},${marker.anchor.y}`);
  } else {
    parts.push(`color:${marker.color ?? "red"}`);
    if (marker.label) parts.push(`label:${marker.label.slice(0, 1).toUpperCase()}`);
  }
  parts.push(`${marker.latitude},${marker.longitude}`);
  return parts.join("|");
}

export function mapsStaticUrlForViewport(
  viewport: MapViewport,
  apiKey: string,
  markers: ReadonlyArray<StaticMapMarker> = [],
): string {
  const params = new URLSearchParams({
    center: `${viewport.centerLat},${viewport.centerLon}`,
    zoom: String(viewport.zoom),
    size: `${Math.round(viewport.width)}x${Math.round(viewport.height)}`,
    scale: "2",
    maptype: "roadmap",
    key: apiKey,
  });

  const markerParams = markers.map((marker) => encodeURIComponent(staticMapMarkerParam(marker)));
  const markerQuery = markerParams.length ? markerParams.map((value) => `markers=${value}`).join("&") : "";
  const base = `https://maps.googleapis.com/maps/api/staticmap?${params.toString()}`;
  return markerQuery ? `${base}&${markerQuery}` : base;
}

export function configuredGoogleMapsApiKey(): string | null {
  const key = import.meta.env.VITE_GOOGLE_MAPS_API_KEY?.trim();
  return key || null;
}

export const GOOGLE_SLATE_PIN_COLOR = "0x64748B";

/** Public origin where /markers/*.png are hosted (must be reachable by Google Static Maps). */
export const MARKER_ICON_ORIGIN =
  import.meta.env.VITE_PUBLIC_SITE_ORIGIN?.trim().replace(/\/$/, "") || "https://g.daliu.ca";

export function absoluteMarkerIconUrl(relativePath: string): string {
  return `${MARKER_ICON_ORIGIN}${relativePath}`;
}

/** Compact ring-dot icon for store list map previews. */
export const RING_DOT_LIST_ICON = "/markers/ring-dot-list-test24.png";
export const RING_DOT_LIST_ANCHOR = { x: 12, y: 12 } as const;
