import { useCallback, useEffect, useState } from "react";
import {
  deleteStoreLocation,
  fetchSettings,
  fetchStoreLocations,
  updateSettings,
  type ExtractBackend,
} from "./api";
import { MapPreview } from "./MapPreview";
import { StoreEditModal } from "./StoreEditModal";
import { StoresMap } from "./StoresMap";
import { hasValidCoords } from "./maps";
import type { StoreLocation } from "./types";

const EXTRACT_BACKEND_OPTIONS: {
  id: ExtractBackend;
  label: string;
  detail: (model: string | null) => string;
}[] = [
  {
    id: "cursor",
    label: "Cursor",
    detail: () => "Routes through the Cursor agent SDK (model: auto).",
  },
  {
    id: "gemini_direct",
    label: "Gemini direct",
    detail: (model) =>
      `Calls Google's API directly${model ? ` (model: ${model})` : ""}.`,
  },
];

export function SettingsPage() {
  const [stores, setStores] = useState<StoreLocation[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [confirmDeleteId, setConfirmDeleteId] = useState<string | null>(null);
  const [editingStore, setEditingStore] = useState<StoreLocation | null>(null);
  const [extractBackend, setExtractBackend] = useState<ExtractBackend | null>(null);
  const [extractModel, setExtractModel] = useState<string | null>(null);
  const [settingsLoading, setSettingsLoading] = useState(true);
  const [settingsBusy, setSettingsBusy] = useState(false);

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

  useEffect(() => {
    setSettingsLoading(true);
    fetchSettings()
      .then((settings) => {
        setExtractBackend(settings.extract_backend);
        setExtractModel(settings.extract_model);
      })
      .catch((err: Error) => setError(err.message))
      .finally(() => setSettingsLoading(false));
  }, []);

  async function handleExtractBackendChange(backend: ExtractBackend) {
    if (backend === extractBackend || settingsBusy) return;
    setSettingsBusy(true);
    setError(null);
    try {
      const settings = await updateSettings({ extract_backend: backend });
      setExtractBackend(settings.extract_backend);
      setExtractModel(settings.extract_model);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not update extraction settings");
    } finally {
      setSettingsBusy(false);
    }
  }

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
          <p className="subtitle">Manage extraction and store preferences.</p>
        </div>
      </div>

      {error && <p className="status error">{error}</p>}

      <section className="settings-section">
        <div className="settings-section-header">
          <h2>Extraction model</h2>
          <p className="subtitle">
            Choose which vision backend processes new uploads and re-extractions.
          </p>
        </div>

        {settingsLoading && <p className="status">Loading settings…</p>}

        {!settingsLoading && (
          <div className="settings-extract-options" role="radiogroup" aria-label="Extraction model">
            {EXTRACT_BACKEND_OPTIONS.map((option) => (
              <label
                key={option.id}
                className={`settings-extract-option${extractBackend === option.id ? " is-selected" : ""}`}
              >
                <input
                  type="radio"
                  name="extract-backend"
                  value={option.id}
                  checked={extractBackend === option.id}
                  disabled={settingsBusy || extractBackend === null}
                  onChange={() => void handleExtractBackendChange(option.id)}
                />
                <span className="settings-extract-option-body">
                  <strong>{option.label}</strong>
                  <span className="settings-extract-option-detail">
                    {option.detail(extractBackend === option.id ? extractModel : null)}
                  </span>
                </span>
              </label>
            ))}
          </div>
        )}
      </section>

      <section className="settings-section">
        <div className="settings-section-header">
          <h2>Store locations</h2>
          <p className="subtitle">
            Saved store labels with map previews. Label photos from Browse with the pin icon.
          </p>
        </div>

        {loading && <p className="status">Loading stores…</p>}

        {!loading && stores.length > 1 && <StoresMap stores={stores} />}

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
    </section>
  );
}
