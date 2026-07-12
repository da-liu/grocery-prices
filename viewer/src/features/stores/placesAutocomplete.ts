import { configuredGoogleMapsApiKey } from "./maps";

export interface PlacePrediction {
  placeId: string;
  description: string;
  primaryText: string;
  secondaryText: string;
}

export interface PlaceDetails {
  name: string;
  latitude: number;
  longitude: number;
}

type AutocompleteSessionToken = object;

type PlacePredictionHandle = {
  placeId: string;
  text?: { toString: () => string; text?: string };
  mainText?: { toString: () => string; text?: string };
  secondaryText?: { toString: () => string; text?: string };
  toPlace: () => PlaceHandle;
};

type PlaceHandle = {
  displayName?: string | null;
  location?: { lat: () => number; lng: () => number } | null;
  fetchFields: (options: { fields: string[] }) => Promise<void>;
};

type PlacesLibrary = {
  AutocompleteSessionToken: new () => AutocompleteSessionToken;
  AutocompleteSuggestion: {
    fetchAutocompleteSuggestions: (request: Record<string, unknown>) => Promise<{
      suggestions: Array<{ placePrediction?: PlacePredictionHandle | null }>;
    }>;
  };
};

type GoogleMapsWindow = Window & {
  google?: {
    maps?: {
      importLibrary?: (name: string, ...rest: unknown[]) => Promise<unknown>;
    };
  };
};

let loadPromise: Promise<PlacesLibrary | null> | null = null;
let sessionToken: AutocompleteSessionToken | null = null;
/** Keep prediction handles so Place Details can use toPlace() (Places API New). */
const predictionById = new Map<string, PlacePredictionHandle>();

function mapsWindow(): GoogleMapsWindow {
  return window as GoogleMapsWindow;
}

export function placesApiConfigured(): boolean {
  return Boolean(configuredGoogleMapsApiKey());
}

/**
 * Google's async bootstrap so `google.maps.importLibrary` is available before the
 * full Maps script finishes loading (`loading=async` requires this pattern).
 */
function ensureMapsBootstrap(key: string): void {
  const w = mapsWindow();
  w.google = w.google || {};
  w.google.maps = w.google.maps || {};
  const maps = w.google.maps;
  if (typeof maps.importLibrary === "function") return;

  const pending = new Set<string>();
  let scriptPromise: Promise<void> | null = null;

  const stubImport = (name: string, ...rest: unknown[]): Promise<unknown> => {
    pending.add(name);
    scriptPromise ??= new Promise<void>((resolve, reject) => {
      const script = document.createElement("script");
      const params = new URLSearchParams({
        key,
        v: "weekly",
        loading: "async",
        libraries: [...pending].join(","),
      });
      script.src = `https://maps.googleapis.com/maps/api/js?${params.toString()}`;
      script.async = true;
      script.dataset.gpPlaces = "1";
      script.onload = () => resolve();
      script.onerror = () => reject(new Error("Failed to load Google Maps"));
      document.head.appendChild(script);
    });

    // After load, Google replaces importLibrary; call the real implementation.
    return scriptPromise.then(() => {
      const realImport = mapsWindow().google?.maps?.importLibrary;
      if (!realImport || realImport === stubImport) {
        throw new Error("Google Maps importLibrary unavailable after load");
      }
      return realImport(name, ...rest);
    });
  };

  maps.importLibrary = stubImport;
}

async function loadPlacesLibrary(): Promise<PlacesLibrary | null> {
  const key = configuredGoogleMapsApiKey();
  if (!key) return null;
  if (loadPromise) return loadPromise;

  loadPromise = (async () => {
    try {
      ensureMapsBootstrap(key);
      const importLibrary = mapsWindow().google?.maps?.importLibrary;
      if (!importLibrary) return null;
      return (await importLibrary("places")) as PlacesLibrary;
    } catch {
      loadPromise = null;
      return null;
    }
  })();

  return loadPromise;
}

function ensureSessionToken(places: PlacesLibrary): AutocompleteSessionToken {
  if (!sessionToken) {
    sessionToken = new places.AutocompleteSessionToken();
  }
  return sessionToken;
}

export function resetPlacesSession(): void {
  sessionToken = null;
  predictionById.clear();
}

function textOf(value: { toString: () => string; text?: string } | undefined): string {
  if (!value) return "";
  if (typeof value.text === "string" && value.text) return value.text;
  return value.toString();
}

function friendlyPlacesError(err: unknown): string {
  const message = err instanceof Error ? err.message : String(err ?? "");
  if (/blocked|not enabled|REQUEST_DENIED|LegacyApiNotActivated/i.test(message)) {
    return "Place search is unavailable (enable Places API New on your Maps key). You can still use device location or paste a Maps link.";
  }
  return "Place search failed. Try again, or use device location / paste a link.";
}

export async function fetchPlacePredictions(
  input: string,
  bias?: { latitude: number; longitude: number } | null,
): Promise<{ predictions: PlacePrediction[]; error?: string }> {
  const trimmed = input.trim();
  if (trimmed.length < 2) return { predictions: [] };

  const places = await loadPlacesLibrary();
  if (!places) {
    return {
      predictions: [],
      error: "Place search could not load. You can still use device location or paste a Maps link.",
    };
  }

  const request: Record<string, unknown> = {
    input: trimmed,
    sessionToken: ensureSessionToken(places),
  };
  if (bias) {
    request.locationBias = {
      circle: {
        center: { lat: bias.latitude, lng: bias.longitude },
        radius: 50_000,
      },
    };
  }

  try {
    const { suggestions } = await places.AutocompleteSuggestion.fetchAutocompleteSuggestions(request);
    const results: PlacePrediction[] = [];
    predictionById.clear();

    for (const suggestion of suggestions) {
      const prediction = suggestion.placePrediction;
      if (!prediction?.placeId) continue;
      predictionById.set(prediction.placeId, prediction);
      const description = textOf(prediction.text);
      const primaryText = textOf(prediction.mainText) || description;
      const secondaryText = textOf(prediction.secondaryText);
      results.push({
        placeId: prediction.placeId,
        description,
        primaryText,
        secondaryText,
      });
    }
    return { predictions: results };
  } catch (err) {
    return { predictions: [], error: friendlyPlacesError(err) };
  }
}

export async function fetchPlaceDetails(placeId: string): Promise<PlaceDetails | null> {
  const places = await loadPlacesLibrary();
  if (!places) return null;

  const prediction = predictionById.get(placeId);
  if (!prediction) return null;

  try {
    // Session token from autocomplete is attached automatically via toPlace().
    const place = prediction.toPlace();
    await place.fetchFields({ fields: ["displayName", "location"] });
    resetPlacesSession();

    const location = place.location;
    if (!location) return null;

    return {
      name: place.displayName?.trim() || "Store",
      latitude: location.lat(),
      longitude: location.lng(),
    };
  } catch {
    resetPlacesSession();
    return null;
  }
}
