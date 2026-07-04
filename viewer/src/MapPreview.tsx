import { mapsEmbedUrl, mapsUrl } from "./maps";

interface MapPreviewProps {
  lat: number;
  lon: number;
  zoom?: number;
  label?: string;
  className?: string;
}

export function MapPreview({ lat, lon, zoom = 13, label, className }: MapPreviewProps) {
  const title = label ?? `${lat.toFixed(5)}, ${lon.toFixed(5)}`;

  return (
    <a
      href={mapsUrl(lat, lon)}
      target="_blank"
      rel="noreferrer"
      className={className ? `map-preview ${className}` : "map-preview"}
      aria-label={`Open ${title} in Google Maps`}
    >
      <iframe title={title} src={mapsEmbedUrl(lat, lon, zoom)} loading="lazy" tabIndex={-1} />
    </a>
  );
}
