import { useEffect, useState } from "react";
import {
  assignPhotoStore,
  createStoreLocation,
  fetchStoreLocations,
  productImageUrl,
} from "@/shared/api/api";
import { MapPreview } from "./MapPreview";
import type { StoreLabelRequest, StoreLocation } from "@/shared/types/types";
import "./StoreLabelModal.css";

interface StoreLabelModalProps {
  request: StoreLabelRequest;
  onDone: () => void;
  onDismiss: () => void;
}

export function StoreLabelModal({ request, onDone, onDismiss }: StoreLabelModalProps) {
  const [stores, setStores] = useState<StoreLocation[]>([]);
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [mode, setMode] = useState<"pick" | "create">("pick");
  const [name, setName] = useState("");
  const [matchedNote, setMatchedNote] = useState<string | null>(null);

  useEffect(() => {
    fetchStoreLocations()
      .then(setStores)
      .catch((err: Error) => setError(err.message))
      .finally(() => setLoading(false));
  }, []);

  async function handleAssign(storeId: string) {
    setBusy(true);
    setError(null);
    try {
      await assignPhotoStore(request.imageId, storeId);
      onDone();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not assign store");
    } finally {
      setBusy(false);
    }
  }

  async function handleCreate() {
    if (!name.trim()) {
      setError("Store name is required");
      return;
    }
    if (request.latitude == null || request.longitude == null) {
      setError("This photo has no GPS. Pick a saved store instead.");
      return;
    }
    setBusy(true);
    setError(null);
    try {
      const store = await createStoreLocation({
        name: name.trim(),
        latitude: request.latitude,
        longitude: request.longitude,
      });
      await assignPhotoStore(request.imageId, store.id);
      if (store.matched_existing) {
        setMatchedNote(`Matched to existing store "${store.name}".`);
        window.setTimeout(() => onDone(), 1200);
        return;
      }
      onDone();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not save store");
    } finally {
      setBusy(false);
    }
  }

  const hasGps = request.latitude != null && request.longitude != null;

  return (
    <div className="onboarding-backdrop" role="dialog" aria-modal="true" aria-labelledby="store-label-title">
      <div className="onboarding-card store-label-card">
        <header className="store-label-header">
          <p className="onboarding-eyebrow">Label location</p>
          <h2 id="store-label-title">Where was this photo taken?</h2>
          <p className="onboarding-body">
            {mode === "pick"
              ? hasGps
                ? "Pick a saved store or create one at the photo location."
                : "This photo has no GPS. Pick one of your saved stores."
              : "Name this store. Products from the photo will use this location."}
          </p>
        </header>

        <div className={hasGps ? "store-label-context" : "store-label-context store-label-context--solo"}>
          <figure className="store-label-preview">
            <img
              src={request.thumbnailUrl || productImageUrl(request.imageId)}
              alt="Uploaded photo preview"
            />
            <figcaption>{request.imageId}</figcaption>
          </figure>
          {hasGps && (
            <figure className="store-label-preview">
              <MapPreview
                lat={request.latitude!}
                lon={request.longitude!}
                label="Photo location"
                className="store-label-map"
              />
              <figcaption>Photo location</figcaption>
            </figure>
          )}
        </div>

        <div className="store-label-content">
          {loading && <p className="status">Loading your stores…</p>}
          {error && <p className="status error">{error}</p>}
          {matchedNote && <p className="status">{matchedNote}</p>}

          {!loading && mode === "pick" && (
            <div className="store-label-actions">
              {stores.length > 0 ? (
                <ul className="store-pick-list">
                  {stores.map((store) => (
                    <li key={store.id}>
                      <button type="button" disabled={busy} onClick={() => void handleAssign(store.id)}>
                        <strong>{store.name}</strong>
                        <span>
                          {`${store.latitude.toFixed(5)}, ${store.longitude.toFixed(5)}`}
                        </span>
                      </button>
                    </li>
                  ))}
                </ul>
              ) : (
                <p className="store-label-empty">No saved stores yet.</p>
              )}
              {hasGps && (
                <button
                  type="button"
                  className="ghost store-label-create-btn"
                  disabled={busy}
                  onClick={() => {
                    setError(null);
                    setMode("create");
                  }}
                >
                  Create new store at photo location
                </button>
              )}
            </div>
          )}

          {!loading && mode === "create" && (
            <form
              className="store-form store-label-form"
              onSubmit={(e) => {
                e.preventDefault();
                void handleCreate();
              }}
            >
              <label>
                Store name
                <input name="store-name" value={name} onChange={(e) => setName(e.target.value)} required />
              </label>
              <div className="store-form-actions">
                <button
                  type="button"
                  className="ghost"
                  onClick={() => {
                    setError(null);
                    setMode("pick");
                  }}
                >
                  Back
                </button>
                <button type="submit" disabled={busy}>
                  {busy ? "Saving…" : "Save & assign"}
                </button>
              </div>
            </form>
          )}
        </div>

        <footer className="store-label-footer onboarding-actions">
          <button type="button" className="ghost" onClick={onDismiss}>
            Cancel
          </button>
        </footer>
      </div>
    </div>
  );
}
