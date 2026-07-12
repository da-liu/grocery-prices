import { useEffect, useId, useRef, useState } from "react";
import {
  assignPhotoStore,
  createStoreLocation,
  fetchStoreLocations,
  productImageUrl,
} from "@/shared/api/api";
import { requestDeviceLocation } from "./deviceLocation";
import { MapPreview } from "./MapPreview";
import { canCreateStoreFromDraft, parseLocationInput } from "./parseLocationInput";
import {
  fetchPlaceDetails,
  fetchPlacePredictions,
  placesApiConfigured,
  resetPlacesSession,
  type PlacePrediction,
} from "./placesAutocomplete";
import type { StoreLabelRequest, StoreLocation } from "@/shared/types/types";
import "./StoreLabelModal.css";

interface StoreLabelModalProps {
  request: StoreLabelRequest;
  onDone: () => void;
  onDismiss: () => void;
}

type CreateSource = "photo" | "place" | "device" | "paste";
/** Active tab for setting coords when the photo has no GPS. */
type LocateMethod = "search" | "paste" | "device";

function defaultLocateMethod(placesEnabled: boolean): LocateMethod {
  return placesEnabled ? "search" : "paste";
}

export function StoreLabelModal({ request, onDone, onDismiss }: StoreLabelModalProps) {
  const [stores, setStores] = useState<StoreLocation[]>([]);
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [mode, setMode] = useState<"pick" | "create">("pick");
  const [name, setName] = useState("");
  const [matchedNote, setMatchedNote] = useState<string | null>(null);

  const [draftLat, setDraftLat] = useState<number | null>(request.latitude);
  const [draftLon, setDraftLon] = useState<number | null>(request.longitude);
  const [createSource, setCreateSource] = useState<CreateSource | null>(
    request.latitude != null && request.longitude != null ? "photo" : null,
  );
  const [sessionBias, setSessionBias] = useState<{ latitude: number; longitude: number } | null>(
    null,
  );
  const [locateMethod, setLocateMethod] = useState<LocateMethod>(() =>
    defaultLocateMethod(placesApiConfigured()),
  );

  const [searchQuery, setSearchQuery] = useState("");
  const [predictions, setPredictions] = useState<PlacePrediction[]>([]);
  const [searching, setSearching] = useState(false);
  const [placesReady, setPlacesReady] = useState(false);

  const [pasteValue, setPasteValue] = useState("");
  const [locating, setLocating] = useState(false);

  const searchListId = useId();
  const searchTimer = useRef<number | null>(null);

  const hasGps = request.latitude != null && request.longitude != null;
  const hasDraftCoords = draftLat != null && draftLon != null;
  const placesEnabled = placesApiConfigured();
  const needsLocate = !hasGps || createSource !== "photo";
  const showPredictions = locateMethod === "search" && (searching || predictions.length > 0);

  useEffect(() => {
    fetchStoreLocations()
      .then(setStores)
      .catch((err: Error) => setError(err.message))
      .finally(() => setLoading(false));
  }, []);

  useEffect(() => {
    return () => {
      if (searchTimer.current != null) window.clearTimeout(searchTimer.current);
      resetPlacesSession();
    };
  }, []);

  function clearSearchState() {
    setSearchQuery("");
    setPredictions([]);
    setSearching(false);
    if (searchTimer.current != null) {
      window.clearTimeout(searchTimer.current);
      searchTimer.current = null;
    }
  }

  function resetCreateDraft() {
    setName("");
    setError(null);
    setMatchedNote(null);
    clearSearchState();
    setPasteValue("");
    setSessionBias(null);
    setLocateMethod(defaultLocateMethod(placesEnabled));
    if (hasGps) {
      setDraftLat(request.latitude);
      setDraftLon(request.longitude);
      setCreateSource("photo");
    } else {
      setDraftLat(null);
      setDraftLon(null);
      setCreateSource(null);
    }
  }

  function enterCreate() {
    resetCreateDraft();
    setMode("create");
  }

  function selectLocateTab(method: LocateMethod) {
    if (method === locateMethod) return;
    setError(null);
    clearSearchState();
    setPasteValue("");
    setLocateMethod(method);
  }

  function clearLocatedCoords() {
    setError(null);
    clearSearchState();
    setPasteValue("");
    setDraftLat(null);
    setDraftLon(null);
    setCreateSource(null);
    setLocateMethod(defaultLocateMethod(placesEnabled));
  }

  function applyCoords(
    latitude: number,
    longitude: number,
    source: CreateSource,
    suggestedName?: string,
  ) {
    setDraftLat(latitude);
    setDraftLon(longitude);
    setCreateSource(source);
    setError(null);
    clearSearchState();
    if (suggestedName && !name.trim()) {
      setName(suggestedName);
    }
    if (source === "device") {
      setSessionBias({ latitude, longitude });
    }
  }

  function scheduleSearch(
    value: string,
    biasOverride?: { latitude: number; longitude: number } | null,
  ) {
    setSearchQuery(value);
    if (searchTimer.current != null) window.clearTimeout(searchTimer.current);
    if (!placesEnabled || value.trim().length < 2) {
      setPredictions([]);
      setSearching(false);
      return;
    }
    const bias = biasOverride !== undefined ? biasOverride : sessionBias;
    setSearching(true);
    searchTimer.current = window.setTimeout(() => {
      void (async () => {
        const { predictions: results, error: searchError } = await fetchPlacePredictions(
          value,
          bias,
        );
        setPlacesReady(true);
        setPredictions(results);
        if (searchError) setError(searchError);
        setSearching(false);
      })();
    }, 280);
  }

  async function handleSearchNearbyBias() {
    setLocating(true);
    setError(null);
    const result = await requestDeviceLocation();
    setLocating(false);
    if (!result.ok) {
      setError(result.message);
      return;
    }
    const bias = { latitude: result.latitude, longitude: result.longitude };
    setSessionBias(bias);
    if (searchQuery.trim().length >= 2) {
      scheduleSearch(searchQuery, bias);
    }
  }

  function clearSearchNearbyBias() {
    setSessionBias(null);
    if (searchQuery.trim().length >= 2) {
      scheduleSearch(searchQuery, null);
    }
  }

  async function handlePickPrediction(prediction: PlacePrediction) {
    setBusy(true);
    setError(null);
    setPredictions([]);
    setSearchQuery(prediction.primaryText);
    try {
      const details = await fetchPlaceDetails(prediction.placeId);
      if (!details) {
        setError("Could not load that place. Try another result, or paste a Maps link instead.");
        return;
      }
      applyCoords(details.latitude, details.longitude, "place", details.name);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not load place details");
    } finally {
      setBusy(false);
    }
  }

  async function handleUseMyLocation() {
    setLocating(true);
    setError(null);
    const result = await requestDeviceLocation();
    setLocating(false);
    if (!result.ok) {
      setError(result.message);
      return;
    }
    applyCoords(result.latitude, result.longitude, "device");
  }

  function handlePasteApply() {
    const parsed = parseLocationInput(pasteValue);
    if (!parsed) {
      setError("Could not read coordinates. Paste a Google Maps link or lat, lon.");
      return;
    }
    applyCoords(parsed.latitude, parsed.longitude, "paste");
  }

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
    if (!canCreateStoreFromDraft({ name, latitude: draftLat, longitude: draftLon })) {
      if (!name.trim()) {
        setError("Store name is required");
        return;
      }
      setError("Choose how to set the store location first.");
      return;
    }
    setBusy(true);
    setError(null);
    try {
      const store = await createStoreLocation({
        name: name.trim(),
        latitude: draftLat!,
        longitude: draftLon!,
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

  const showMap = hasDraftCoords;
  const contextClass = showMap
    ? "store-label-context"
    : "store-label-context store-label-context--solo";

  const createBodyCopy =
    mode === "pick"
      ? hasGps
        ? "Pick a saved store or create one at the photo location."
        : "This photo has no GPS. Pick a saved store, or create one by finding the place."
      : hasGps && createSource === "photo"
        ? "Name this store. Products from the photo will use this location."
        : hasDraftCoords
          ? "Confirm the map pin, name the store, then save."
          : "Set the store location, then name and save it.";

  return (
    <div className="onboarding-backdrop" role="dialog" aria-modal="true" aria-labelledby="store-label-title">
      <div className="onboarding-card store-label-card">
        <header className="store-label-header">
          <p className="onboarding-eyebrow">Label location</p>
          <h2 id="store-label-title">Where was this photo taken?</h2>
          <p className="onboarding-body">{createBodyCopy}</p>
        </header>

        <div className={contextClass}>
          <figure className="store-label-preview">
            <img
              src={request.thumbnailUrl || productImageUrl(request.imageId)}
              alt="Uploaded photo preview"
            />
          </figure>
          {showMap && (
            <figure className="store-label-preview">
              <MapPreview
                lat={draftLat!}
                lon={draftLon!}
                label="Store location"
                className="store-label-map"
              />
              <figcaption>
                {createSource === "photo"
                  ? "Photo location"
                  : createSource === "device"
                    ? "Device location"
                    : createSource === "paste"
                      ? "Pasted location"
                      : "Selected place"}
              </figcaption>
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
              <button
                type="button"
                className="ghost store-label-create-btn"
                disabled={busy}
                onClick={enterCreate}
              >
                {hasGps ? "Create new store at photo location" : "Create new store…"}
              </button>
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
              {needsLocate && !hasDraftCoords && (
                <div className="store-label-locate-tabs">
                  <div className="store-label-tabs" role="tablist" aria-label="Location method">
                    {placesEnabled && (
                      <button
                        type="button"
                        role="tab"
                        id="store-locate-tab-search"
                        aria-selected={locateMethod === "search"}
                        aria-controls="store-locate-panel-search"
                        className={
                          locateMethod === "search"
                            ? "store-label-tab store-label-tab--active"
                            : "store-label-tab"
                        }
                        disabled={busy}
                        onClick={() => selectLocateTab("search")}
                      >
                        Search
                      </button>
                    )}
                    <button
                      type="button"
                      role="tab"
                      id="store-locate-tab-paste"
                      aria-selected={locateMethod === "paste"}
                      aria-controls="store-locate-panel-paste"
                      className={
                        locateMethod === "paste"
                          ? "store-label-tab store-label-tab--active"
                          : "store-label-tab"
                      }
                      disabled={busy}
                      onClick={() => selectLocateTab("paste")}
                    >
                      Paste link
                    </button>
                    <button
                      type="button"
                      role="tab"
                      id="store-locate-tab-device"
                      aria-selected={locateMethod === "device"}
                      aria-controls="store-locate-panel-device"
                      className={
                        locateMethod === "device"
                          ? "store-label-tab store-label-tab--active"
                          : "store-label-tab"
                      }
                      disabled={busy}
                      onClick={() => selectLocateTab("device")}
                    >
                      My location
                    </button>
                  </div>

                  {locateMethod === "search" && placesEnabled && (
                    <div
                      className="store-label-tab-panel"
                      role="tabpanel"
                      id="store-locate-panel-search"
                      aria-labelledby="store-locate-tab-search"
                    >
                      <div className="store-label-search">
                        <label>
                          Store or address
                          <input
                            name="store-search"
                            value={searchQuery}
                            onChange={(e) => scheduleSearch(e.target.value)}
                            onKeyDown={(e) => {
                              if (e.key === "Escape") clearSearchState();
                            }}
                            autoComplete="off"
                            aria-autocomplete="list"
                            aria-controls={searchListId}
                            aria-expanded={showPredictions}
                            placeholder="Store name or address"
                            disabled={busy}
                            autoFocus
                          />
                        </label>
                        <div className="store-label-search-bias">
                          {sessionBias ? (
                            <p className="store-label-geo-notice">
                              Preferring nearby places.{" "}
                              <button
                                type="button"
                                className="store-label-geo-link"
                                disabled={busy || locating}
                                onClick={clearSearchNearbyBias}
                              >
                                Clear
                              </button>
                            </p>
                          ) : (
                            <>
                              <p className="store-label-geo-notice">
                                To prefer nearby places, share this device’s location. Your browser
                                will ask for permission.
                              </p>
                              <button
                                type="button"
                                className="ghost store-label-search-bias-btn"
                                disabled={busy || locating}
                                onClick={() => void handleSearchNearbyBias()}
                              >
                                {locating ? "Getting location…" : "Use nearby results"}
                              </button>
                            </>
                          )}
                        </div>
                      </div>
                      {showPredictions && (
                        <ul
                          id={searchListId}
                          className="store-label-predictions store-label-predictions--panel"
                          role="listbox"
                        >
                          {searching && predictions.length === 0 && (
                            <li className="store-label-prediction-status">Searching…</li>
                          )}
                          {predictions.map((prediction) => (
                            <li key={prediction.placeId}>
                              <button
                                type="button"
                                role="option"
                                disabled={busy}
                                onClick={() => void handlePickPrediction(prediction)}
                              >
                                <strong>{prediction.primaryText}</strong>
                                {prediction.secondaryText ? (
                                  <span>{prediction.secondaryText}</span>
                                ) : null}
                              </button>
                            </li>
                          ))}
                          {!searching &&
                            placesReady &&
                            predictions.length === 0 &&
                            searchQuery.trim().length >= 2 && (
                              <li className="store-label-prediction-status">No places found.</li>
                            )}
                        </ul>
                      )}
                    </div>
                  )}

                  {locateMethod === "paste" && (
                    <div
                      className="store-label-tab-panel"
                      role="tabpanel"
                      id="store-locate-panel-paste"
                      aria-labelledby="store-locate-tab-paste"
                    >
                      <div className="store-label-paste">
                        <label>
                          Google Maps link or lat, lon
                          <input
                            name="store-paste"
                            value={pasteValue}
                            onChange={(e) => setPasteValue(e.target.value)}
                            placeholder="Paste a Maps link or coordinates"
                            disabled={busy}
                            autoFocus
                          />
                        </label>
                        <button
                          type="button"
                          disabled={busy || !pasteValue.trim()}
                          onClick={handlePasteApply}
                        >
                          Apply location
                        </button>
                      </div>
                    </div>
                  )}

                  {locateMethod === "device" && (
                    <div
                      className="store-label-tab-panel"
                      role="tabpanel"
                      id="store-locate-panel-device"
                      aria-labelledby="store-locate-tab-device"
                    >
                      <div className="store-label-device">
                        <p className="store-label-geo-notice">
                          If you are at the store now, you can share this device’s location. Your
                          browser will ask for permission.
                        </p>
                        <button
                          type="button"
                          disabled={busy || locating}
                          onClick={() => void handleUseMyLocation()}
                        >
                          {locating ? "Getting location…" : "Share location"}
                        </button>
                      </div>
                    </div>
                  )}
                </div>
              )}

              {(!needsLocate || hasDraftCoords) && (
                <>
                  {needsLocate && hasDraftCoords && (
                    <button
                      type="button"
                      className="ghost store-label-method-switch store-label-method-switch--inline"
                      disabled={busy}
                      onClick={clearLocatedCoords}
                    >
                      Change location
                    </button>
                  )}

                  <label>
                    Store name
                    <input
                      name="store-name"
                      value={name}
                      onChange={(e) => setName(e.target.value)}
                      required
                      disabled={busy}
                    />
                  </label>

                  {hasDraftCoords && (
                    <p className="store-label-gps">
                      {draftLat!.toFixed(5)}, {draftLon!.toFixed(5)}
                    </p>
                  )}

                  <div className="store-form-actions">
                    <button
                      type="submit"
                      disabled={
                        busy ||
                        !canCreateStoreFromDraft({
                          name,
                          latitude: draftLat,
                          longitude: draftLon,
                        })
                      }
                    >
                      {busy ? "Saving…" : "Save & assign"}
                    </button>
                  </div>
                </>
              )}
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
