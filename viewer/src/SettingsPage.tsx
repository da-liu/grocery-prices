import { useCallback, useEffect, useState } from "react";
import { deleteStoreLocation, fetchStoreLocations } from "./api";
import { MapPreview } from "./MapPreview";
import { hasValidCoords } from "./maps";
import type { StoreLocation } from "./types";

export function SettingsPage() {
  const [stores, setStores] = useState<StoreLocation[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [confirmDeleteId, setConfirmDeleteId] = useState<string | null>(null);

  const loadStores = useCallback(() => {
    setLoading(true);
    setError(null);
    return fetchStoreLocations()
      .then(setStores)
      .catch((err: Error) => setError(err.message))
      .finally(() => setLoading(false));
  }, []);

  useEffect(() => {
    void loadStores();
  }, [loadStores]);

  async function handleDelete(storeId: string) {
    setBusy(true);
    setError(null);
    try {
      await deleteStoreLocation(storeId);
      setStores((rows) => rows.filter((s) => s.id !== storeId));
      setConfirmDeleteId(null);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not delete store");
    } finally {
      setBusy(false);
    }
  }

  return (
    <section className="panel settings-page">
      <div className="panel-header">
        <div>
          <h1>Store locations</h1>
          <p className="subtitle">
            Saved store labels with map previews. Label photos from Browse with the pin icon, or
            after upload.
          </p>
        </div>
      </div>

      {error && <p className="status error">{error}</p>}
      {loading && <p className="status">Loading stores…</p>}

      {!loading && stores.length > 0 && (
        <ul className="store-list">
          {stores.map((store) => (
            <li key={store.id} className="store-list-item">
              {hasValidCoords(store.latitude, store.longitude) && (
                <MapPreview
                  lat={store.latitude}
                  lon={store.longitude}
                  label={store.name}
                  className="store-list-map"
                />
              )}
              <div className="store-list-main">
                <strong>{store.name}</strong>
                <span className="store-list-coords">
                  {store.latitude.toFixed(5)}, {store.longitude.toFixed(5)} · {store.match_radius_m}m
                  radius
                </span>
              </div>
              <div className="store-list-actions">
                {confirmDeleteId === store.id ? (
                  <>
                    <button
                      type="button"
                      className="store-delete-confirm"
                      disabled={busy}
                      onClick={() => void handleDelete(store.id)}
                    >
                      Confirm delete
                    </button>
                    <button
                      type="button"
                      className="ghost"
                      onClick={() => setConfirmDeleteId(null)}
                    >
                      Cancel
                    </button>
                  </>
                ) : (
                  <button
                    type="button"
                    className="ghost store-delete"
                    onClick={() => setConfirmDeleteId(store.id)}
                  >
                    Delete
                  </button>
                )}
              </div>
            </li>
          ))}
        </ul>
      )}

      {!loading && stores.length === 0 && (
        <p className="store-label-empty">
          No saved stores yet. Label a photo with GPS from Browse using the pin icon.
        </p>
      )}
    </section>
  );
}
