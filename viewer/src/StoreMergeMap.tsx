import { useEffect, useMemo, useRef, useState } from "react";
import { geoBoundsFromCoords, mapsEmbedUrlForBounds } from "./maps";
import type { StoreLocation } from "./types";

interface StoreMergeMapProps {
  stores: StoreLocation[];
  onMergeRequest: (sourceId: string, targetId: string) => void;
}

interface PinPosition {
  store: StoreLocation;
  x: number;
  y: number;
}

const MERGE_HIT_RADIUS_PX = 36;

function projectPins(stores: StoreLocation[]): PinPosition[] {
  if (!stores.length) return [];

  const lats = stores.map((store) => store.latitude);
  const lons = stores.map((store) => store.longitude);
  const minLat = Math.min(...lats);
  const maxLat = Math.max(...lats);
  const minLon = Math.min(...lons);
  const maxLon = Math.max(...lons);
  const latSpan = Math.max(maxLat - minLat, 0.0005);
  const lonSpan = Math.max(maxLon - minLon, 0.0005);

  return stores.map((store) => ({
    store,
    x: 12 + ((store.longitude - minLon) / lonSpan) * 76,
    y: 88 - ((store.latitude - minLat) / latSpan) * 76,
  }));
}

export function StoreMergeMap({ stores, onMergeRequest }: StoreMergeMapProps) {
  const mapRef = useRef<HTMLDivElement | null>(null);
  const [draggingId, setDraggingId] = useState<string | null>(null);
  const [dragOffset, setDragOffset] = useState({ x: 0, y: 0 });
  const [positions, setPositions] = useState<PinPosition[]>(() => projectPins(stores));

  useEffect(() => {
    setPositions(projectPins(stores));
  }, [stores]);

  const positionsById = useMemo(
    () => new Map(positions.map((entry) => [entry.store.id, entry])),
    [positions],
  );

  const mapEmbedUrl = useMemo(() => {
    const bounds = geoBoundsFromCoords(stores);
    return bounds ? mapsEmbedUrlForBounds(bounds) : null;
  }, [stores]);

  if (stores.length < 2) {
    return (
      <p className="store-merge-map-empty">
        Add at least two stores to merge them on the map.
      </p>
    );
  }

  function beginDrag(storeId: string, clientX: number, clientY: number) {
    const map = mapRef.current;
    const pin = positionsById.get(storeId);
    if (!map || !pin) return;
    const rect = map.getBoundingClientRect();
    const pinX = rect.left + (pin.x / 100) * rect.width;
    const pinY = rect.top + (pin.y / 100) * rect.height;
    setDraggingId(storeId);
    setDragOffset({ x: clientX - pinX, y: clientY - pinY });
  }

  function moveDrag(clientX: number, clientY: number) {
    const map = mapRef.current;
    if (!map || !draggingId) return;
    const rect = map.getBoundingClientRect();
    const x = ((clientX - dragOffset.x - rect.left) / rect.width) * 100;
    const y = ((clientY - dragOffset.y - rect.top) / rect.height) * 100;
    setPositions((prev) =>
      prev.map((entry) =>
        entry.store.id === draggingId
          ? { ...entry, x: Math.min(92, Math.max(8, x)), y: Math.min(92, Math.max(8, y)) }
          : entry,
      ),
    );
  }

  function endDrag() {
    if (!draggingId) return;
    const dragged = positionsById.get(draggingId);
    if (!dragged || !mapRef.current) {
      setDraggingId(null);
      return;
    }

    const rect = mapRef.current.getBoundingClientRect();
    const draggedX = rect.left + (dragged.x / 100) * rect.width;
    const draggedY = rect.top + (dragged.y / 100) * rect.height;

    let closest: StoreLocation | null = null;
    let closestDistance = MERGE_HIT_RADIUS_PX;

    for (const entry of positions) {
      if (entry.store.id === draggingId) continue;
      const targetX = rect.left + (entry.x / 100) * rect.width;
      const targetY = rect.top + (entry.y / 100) * rect.height;
      const distance = Math.hypot(draggedX - targetX, draggedY - targetY);
      if (distance <= closestDistance) {
        closest = entry.store;
        closestDistance = distance;
      }
    }

    if (closest) {
      onMergeRequest(draggingId, closest.id);
    }

    setDraggingId(null);
    setPositions(projectPins(stores));
  }

  return (
    <div className="store-merge-map-wrap">
      <p className="store-merge-map-hint">
        Drag one store pin onto another to merge them. Photos move to the target store.
      </p>
      <div
        ref={mapRef}
        className="store-merge-map"
        onPointerMove={(event) => {
          if (draggingId) moveDrag(event.clientX, event.clientY);
        }}
        onPointerUp={() => endDrag()}
        onPointerLeave={() => endDrag()}
      >
        {mapEmbedUrl && (
          <iframe
            className="store-merge-map-bg"
            title="Store locations map"
            src={mapEmbedUrl}
            loading="lazy"
            tabIndex={-1}
            aria-hidden="true"
          />
        )}
        {positions.map(({ store, x, y }) => (
          <button
            key={store.id}
            type="button"
            className={`store-merge-pin${draggingId === store.id ? " store-merge-pin--dragging" : ""}`}
            style={{ left: `${x}%`, top: `${y}%` }}
            onPointerDown={(event) => {
              event.preventDefault();
              beginDrag(store.id, event.clientX, event.clientY);
            }}
            title={`${store.name} (${store.photo_count ?? 0} photos)`}
          >
            <span>{store.name}</span>
          </button>
        ))}
      </div>
    </div>
  );
}
