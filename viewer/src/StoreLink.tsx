import type { Location } from "./types";

function storeMapsUrl(location: Location): string | null {
  if (location.maps_url) return location.maps_url;
  if (location.store.startsWith("http://") || location.store.startsWith("https://")) {
    return location.store;
  }
  const { latitude, longitude } = location;
  if (latitude != null && longitude != null) {
    return `https://www.google.com/maps?q=${latitude},${longitude}`;
  }
  return null;
}

export function StoreLink({ location }: { location: Location }) {
  const mapsUrl = storeMapsUrl(location);
  const name =
    location.store.startsWith("http://") || location.store.startsWith("https://")
      ? location.address
      : location.store;

  if (mapsUrl) {
    return (
      <a href={mapsUrl} target="_blank" rel="noreferrer">
        {name}
      </a>
    );
  }

  return <>{name}</>;
}
