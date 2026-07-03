import { useCallback, useEffect, useState } from "react";
import { deleteStoreLocation, fetchStoreLocations } from "./api";
import { MapPreview } from "./MapPreview";
import { hasValidCoords } from "./maps";
import {
  TOP_BAR_STYLE_OPTIONS,
  type TopBarStyle,
} from "./topBarStyle";
import { DEV_FORCE_LOADING } from "./devPreview";
import type { StoreLocation } from "./types";

interface SettingsPageProps {
  topBarStyle: TopBarStyle;
  onTopBarStyleChange: (style: TopBarStyle) => void;
}

export function SettingsPage({ topBarStyle, onTopBarStyleChange }: SettingsPageProps) {
  const [stores, setStores] = useState<StoreLocation[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [confirmDeleteId, setConfirmDeleteId] = useState<string | null>(null);

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

  return (
    <section className="panel settings-page">
      <div className="panel-header">
        <div>
          <h1>Settings</h1>
          <p className="subtitle">
            Compare header styles and manage saved store labels.
          </p>
        </div>
      </div>

      {error && <p className="status error">{error}</p>}

      <section className="settings-section">
        <div className="settings-section-header">
          <h2>Header style</h2>
          <p className="subtitle">Try a few sticky header separators live.</p>
        </div>
        <div className="settings-choice-grid" role="list" aria-label="Header style options">
          {TOP_BAR_STYLE_OPTIONS.map((option) => {
            const active = topBarStyle === option.id;
            return (
              <button
                key={option.id}
                type="button"
                role="listitem"
                className={`settings-choice${active ? " active" : ""}`}
                aria-pressed={active}
                onClick={() => onTopBarStyleChange(option.id)}
              >
                <strong>{option.label}</strong>
                <span>{option.description}</span>
              </button>
            );
          })}
        </div>
      </section>

      <section className="settings-section">
        <div className="settings-section-header">
          <h2>Store locations</h2>
          <p className="subtitle">
            Saved store labels with map previews. Label photos from Browse with the pin icon, or
            after upload.
          </p>
        </div>

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
    </section>
  );
}
