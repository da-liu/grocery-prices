import { useState } from "react";
import { deleteStoreLocation } from "@/shared/api/api";
import { useStores } from "./StoresContext";
import { MapPreview } from "./MapPreview";
import { StoreEditModal } from "./StoreEditModal";
import { StoresMap } from "./StoresMap";
import { hasValidCoords } from "./maps";
import type { StoreLocation } from "@/shared/types/types";
import "./SettingsPage.css";

export function SettingsPage() {
  const {
    storeLocations: stores,
    storeLocationsLoading: loading,
    setStoreLocations,
  } = useStores();
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [confirmDeleteId, setConfirmDeleteId] = useState<string | null>(null);
  const [editingStore, setEditingStore] = useState<StoreLocation | null>(null);

  async function handleDelete(storeId: string) {
    setBusy(true);
    setError(null);
    try {
      await deleteStoreLocation(storeId);
      setStoreLocations((rows) => rows.filter((s) => s.id !== storeId));
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
          <h1>Settings</h1>
          <p className="subtitle">Manage store preferences.</p>
        </div>
      </div>

      {error && <p className="status error">{error}</p>}

      {(loading || stores.length > 0) && (
        <section className="settings-section">
          <div className="settings-section-header">
            <h2>Store locations</h2>
            <p className="subtitle">
              Saved store labels with map previews. Label photos from Catalog with the pin icon.
            </p>
          </div>

          {loading && <p className="status">Loading stores…</p>}

          {!loading && stores.length > 0 && <StoresMap stores={stores} />}

          {!loading && stores.length > 0 && (
            <ul className="store-list">
              {stores.map((store) => (
                <li key={store.id} className="store-list-item">
                  {hasValidCoords(store.latitude, store.longitude) && (
                    <MapPreview
                      lat={store.latitude}
                      lon={store.longitude}
                      label={store.name}
                      ringDot
                      zoom={13}
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
        </section>
      )}

      {editingStore && (
        <StoreEditModal
          store={editingStore}
          onDone={(updated) => {
            setStoreLocations((rows) => rows.map((row) => (row.id === updated.id ? updated : row)));
            setEditingStore(null);
          }}
          onDismiss={() => setEditingStore(null)}
        />
      )}
    </section>
  );
}
