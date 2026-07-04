import { useCallback, useEffect, useState } from "react";
import {
  deleteStoreLocation,
  fetchStoreLocations,
  mergeStoreLocations,
} from "./api";
import { MapPreview } from "./MapPreview";
import { StoreEditModal } from "./StoreEditModal";
import { StoreMergeMap } from "./StoreMergeMap";
import { hasValidCoords } from "./maps";
import { DEV_FORCE_LOADING } from "./devPreview";
import type { StoreLocation } from "./types";

export function SettingsPage() {
  const [stores, setStores] = useState<StoreLocation[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [confirmDeleteId, setConfirmDeleteId] = useState<string | null>(null);
  const [editingStore, setEditingStore] = useState<StoreLocation | null>(null);
  const [mergeRequest, setMergeRequest] = useState<{
    sourceId: string;
    targetId: string;
  } | null>(null);

  const loadStores = useCallback(() => {
    if (DEV_FORCE_LOADING) return Promise.resolve();
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

  async function handleMerge(sourceId: string, targetId: string) {
    setMergeRequest({ sourceId, targetId });
  }

  async function confirmMerge() {
    if (!mergeRequest) return;
    const source = stores.find((store) => store.id === mergeRequest.sourceId);
    const target = stores.find((store) => store.id === mergeRequest.targetId);
    if (!source || !target) return;

    setBusy(true);
    setError(null);
    try {
      await mergeStoreLocations(mergeRequest.sourceId, mergeRequest.targetId);
      setMergeRequest(null);
      await loadStores();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not merge stores");
    } finally {
      setBusy(false);
    }
  }

  const mergeSource = mergeRequest
    ? stores.find((store) => store.id === mergeRequest.sourceId)
    : null;
  const mergeTarget = mergeRequest
    ? stores.find((store) => store.id === mergeRequest.targetId)
    : null;

  return (
    <section className="panel settings-page">
      <div className="panel-header">
        <div>
          <h1>Settings</h1>
          <p className="subtitle">Manage saved store labels.</p>
        </div>
      </div>

      {error && <p className="status error">{error}</p>}

      <section className="settings-section">
        <div className="settings-section-header">
          <h2>Store locations</h2>
          <p className="subtitle">
            Saved store labels with map previews. Label photos from Browse with the pin icon.
          </p>
        </div>

        {loading && <p className="status">Loading stores…</p>}

        {!loading && stores.length > 1 && (
          <StoreMergeMap stores={stores} onMergeRequest={handleMerge} />
        )}

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
                    {store.latitude.toFixed(5)}, {store.longitude.toFixed(5)}
                  </span>
                  <span className="store-list-coords">
                    {store.match_radius_m}m radius
                    {store.photo_count != null ? ` · ${store.photo_count} photos` : ""}
                  </span>
                </div>
                <div className="store-list-actions">
                  {confirmDeleteId === store.id ? (
                    <>
                      <button
                        type="button"
                        className="danger-outline"
                        disabled={busy}
                        onClick={() => void handleDelete(store.id)}
                      >
                        Confirm
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
                    <>
                      <button
                        type="button"
                        className="ghost"
                        onClick={() => setEditingStore(store)}
                      >
                        Edit
                      </button>
                      <button
                        type="button"
                        className="ghost store-delete"
                        onClick={() => setConfirmDeleteId(store.id)}
                      >
                        Delete
                      </button>
                    </>
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

      {editingStore && (
        <StoreEditModal
          store={editingStore}
          onDone={(updated) => {
            setStores((rows) => rows.map((row) => (row.id === updated.id ? updated : row)));
            setEditingStore(null);
          }}
          onDismiss={() => setEditingStore(null)}
        />
      )}

      {mergeRequest && mergeSource && mergeTarget && (
        <div className="onboarding-backdrop" role="dialog" aria-modal="true">
          <div className="onboarding-card store-merge-confirm">
            <h2>Merge stores?</h2>
            <p className="onboarding-body">
              Move {mergeSource.photo_count ?? 0} photo
              {mergeSource.photo_count === 1 ? "" : "s"} from <strong>{mergeSource.name}</strong> into{" "}
              <strong>{mergeTarget.name}</strong>?
            </p>
            <div className="onboarding-actions">
              <button type="button" className="ghost" disabled={busy} onClick={() => setMergeRequest(null)}>
                Cancel
              </button>
              <button type="button" disabled={busy} onClick={() => void confirmMerge()}>
                {busy ? "Merging…" : "Merge"}
              </button>
            </div>
          </div>
        </div>
      )}
    </section>
  );
}
