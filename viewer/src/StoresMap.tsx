import { useEffect, useMemo, useRef, useState } from "react";
import {
  configuredGoogleMapsApiKey,
  geoBoundsFromCoords,
  GOOGLE_SLATE_PIN_COLOR,
  mapViewportForBounds,
  mapsStaticUrlForViewport,
  markerLabelForStore,
  STATIC_MAP_DEFAULT_HEIGHT,
  STATIC_MAP_MAX_WIDTH,
  staticMapDimensions,
} from "./maps";
import type { StoreLocation } from "./types";

interface StoresMapProps {
  stores: StoreLocation[];
}

export function StoresMap({ stores }: StoresMapProps) {
  const mapRef = useRef<HTMLDivElement | null>(null);
  const [mapSize, setMapSize] = useState({
    width: STATIC_MAP_MAX_WIDTH,
    height: STATIC_MAP_DEFAULT_HEIGHT,
  });

  const mapsApiKey = configuredGoogleMapsApiKey();

  useEffect(() => {
    const map = mapRef.current;
    if (!map) return;

    const updateSize = () => {
      const rect = map.getBoundingClientRect();
      setMapSize(staticMapDimensions(rect.width, rect.height));
    };

    updateSize();
    const observer = new ResizeObserver(updateSize);
    observer.observe(map);
    return () => observer.disconnect();
  }, []);

  const staticMapUrl = useMemo(() => {
    if (!mapsApiKey || stores.length < 2) return null;

    const bounds = geoBoundsFromCoords(stores);
    if (!bounds) return null;

    const viewport = mapViewportForBounds(bounds, mapSize.width, mapSize.height);
    const markers = stores.map((store, index) => ({
      latitude: store.latitude,
      longitude: store.longitude,
      color: GOOGLE_SLATE_PIN_COLOR,
      label: markerLabelForStore(store.name, index),
    }));

    return mapsStaticUrlForViewport(viewport, mapsApiKey, markers);
  }, [stores, mapSize.width, mapSize.height, mapsApiKey]);

  if (stores.length < 2) {
    return (
      <p className="stores-map-empty">
        Add at least two stores to see them on the map.
      </p>
    );
  }

  return (
    <div className="stores-map-wrap">
      {!mapsApiKey && (
        <p className="stores-map-empty">
          Set <code>VITE_GOOGLE_MAPS_API_KEY</code> in <code>viewer/.env.local</code> to show the
          map.
        </p>
      )}
      <div ref={mapRef} className="stores-map">
        {staticMapUrl ? (
          <img
            className="stores-map-img"
            alt={`Map of ${stores.length} saved stores`}
            src={staticMapUrl}
            loading="lazy"
            draggable={false}
          />
        ) : (
          mapsApiKey && <p className="stores-map-empty">Could not build map for these stores.</p>
        )}
      </div>
      <ul className="stores-map-legend" aria-label="Store markers">
        {stores.map((store, index) => (
          <li key={store.id}>
            <span className="stores-map-legend-label">
              {markerLabelForStore(store.name, index)}
            </span>
            {store.name}
          </li>
        ))}
      </ul>
    </div>
  );
}
