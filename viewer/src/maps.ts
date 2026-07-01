export function mapsUrl(lat: number, lon: number) {
  return `https://www.google.com/maps?q=${lat},${lon}`;
}

export function mapsEmbedUrl(lat: number, lon: number, zoom = 15) {
  return `https://maps.google.com/maps?q=${lat},${lon}&z=${zoom}&output=embed`;
}

export function hasValidCoords(lat: number | null | undefined, lon: number | null | undefined) {
  return lat != null && lon != null && !(lat === 0 && lon === 0);
}
