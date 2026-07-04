import { useState, type FormEvent } from "react";
import { updateStoreLocation } from "./api";
import type { StoreLocation } from "./types";

interface StoreEditModalProps {
  store: StoreLocation;
  onDone: (updated: StoreLocation) => void;
  onDismiss: () => void;
}

export function StoreEditModal({ store, onDone, onDismiss }: StoreEditModalProps) {
  const [name, setName] = useState(store.name);
  const [latitude, setLatitude] = useState(String(store.latitude));
  const [longitude, setLongitude] = useState(String(store.longitude));
  const [radius, setRadius] = useState(String(store.match_radius_m));
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function handleSubmit(event: FormEvent) {
    event.preventDefault();
    const trimmedName = name.trim();
    if (!trimmedName) {
      setError("Store name is required");
      return;
    }
    const lat = Number(latitude);
    const lon = Number(longitude);
    const matchRadius = Number(radius);
    if (!Number.isFinite(lat) || !Number.isFinite(lon)) {
      setError("Latitude and longitude must be valid numbers");
      return;
    }
    if (!Number.isFinite(matchRadius) || matchRadius <= 0) {
      setError("Radius must be a positive number");
      return;
    }

    setBusy(true);
    setError(null);
    try {
      const updated = await updateStoreLocation(store.id, {
        name: trimmedName,
        latitude: lat,
        longitude: lon,
        match_radius_m: matchRadius,
      });
      onDone(updated);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not update store");
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="onboarding-backdrop" role="dialog" aria-modal="true" aria-labelledby="store-edit-title">
      <div className="onboarding-card store-edit-card">
        <h2 id="store-edit-title">Edit store</h2>
        <p className="onboarding-body">Update the store name, coordinates, or match radius.</p>

        {error && <p className="status error">{error}</p>}

        <form className="store-form" onSubmit={(event) => void handleSubmit(event)}>
          <label>
            Store name
            <input value={name} onChange={(event) => setName(event.target.value)} required />
          </label>
          <div className="store-form-row">
            <label>
              Latitude
              <input
                value={latitude}
                onChange={(event) => setLatitude(event.target.value)}
                inputMode="decimal"
                required
              />
            </label>
            <label>
              Longitude
              <input
                value={longitude}
                onChange={(event) => setLongitude(event.target.value)}
                inputMode="decimal"
                required
              />
            </label>
          </div>
          <label>
            Match radius (meters)
            <input
              value={radius}
              onChange={(event) => setRadius(event.target.value)}
              inputMode="numeric"
              required
            />
          </label>
          <div className="onboarding-actions">
            <button type="button" className="ghost" disabled={busy} onClick={onDismiss}>
              Cancel
            </button>
            <button type="submit" disabled={busy}>
              {busy ? "Saving…" : "Save"}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}
