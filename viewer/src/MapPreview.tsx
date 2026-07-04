import { useMemo } from "react";
import {
  absoluteMarkerIconUrl,
  configuredGoogleMapsApiKey,
  mapsStaticUrlForViewport,
  mapsUrl,
  mapsEmbedUrl,
  RING_DOT_LIST_ANCHOR,
  RING_DOT_LIST_ICON,
} from "./maps";

interface MapPreviewProps {
  lat: number;
  lon: number;
  zoom?: number;
  label?: string;
  className?: string;
  width?: number;
  height?: number;
  /** When true, use the compact ring-dot marker (store list). Otherwise fall back to embed. */
  ringDot?: boolean;
}

export function MapPreview({
  lat,
  lon,
  zoom = 13,
  label,
  className,
  ringDot = false,
  width = 112,
  height = 76,
}: MapPreviewProps) {
  const title = label ?? `${lat.toFixed(5)}, ${lon.toFixed(5)}`;
  const mapsApiKey = configuredGoogleMapsApiKey();

  const staticMapUrl = useMemo(() => {
    if (!ringDot || !mapsApiKey) return null;

    const marker = {
      latitude: lat,
      longitude: lon,
      icon: absoluteMarkerIconUrl(RING_DOT_LIST_ICON),
      anchor: RING_DOT_LIST_ANCHOR,
    };

    return mapsStaticUrlForViewport(
      { centerLat: lat, centerLon: lon, zoom, width, height },
      mapsApiKey,
      [marker],
    );
  }, [lat, lon, zoom, ringDot, mapsApiKey, width, height]);

  return (
    <a
      href={mapsUrl(lat, lon)}
      target="_blank"
      rel="noreferrer"
      className={className ? `map-preview ${className}` : "map-preview"}
      aria-label={`Open ${title} in Google Maps`}
    >
      {staticMapUrl ? (
        <img
          className="map-preview-img"
          alt=""
          src={staticMapUrl}
          loading="lazy"
          draggable={false}
        />
      ) : (
        <iframe title={title} src={mapsEmbedUrl(lat, lon, zoom)} loading="lazy" tabIndex={-1} />
      )}
    </a>
  );
}
