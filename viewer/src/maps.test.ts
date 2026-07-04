import { describe, expect, it } from "vitest";
import {
  geoBoundsFromCoords,
  mapViewportForBounds,
  mapsEmbedUrlForBounds,
  mapsStaticUrlForViewport,
  markerLabelForStore,
  projectCoordsToPercent,
  projectLatLonInViewport,
  staticMapMarkerParam,
  zoomForGeoBounds,
} from "./maps";

const TORONTO_STORES = [
  { latitude: 43.63943, longitude: -79.38029 },
  { latitude: 43.63961, longitude: -79.38039 },
  { latitude: 43.64239, longitude: -79.38118 },
];

describe("mapsEmbedUrlForBounds", () => {
  it("centers and zooms to fit nearby stores", () => {
    const bounds = geoBoundsFromCoords([
      { latitude: 43.63943, longitude: -79.38029 },
      { latitude: 43.64239, longitude: -79.38118 },
    ]);
    expect(bounds).not.toBeNull();

    const url = mapsEmbedUrlForBounds(bounds!);
    expect(url).toContain("43.64091");
    expect(url).toContain("-79.380735");
    expect(url).toMatch(/z=1[4-7]/);
  });

  it("uses a minimum span for a single store", () => {
    const bounds = geoBoundsFromCoords([{ latitude: 43.64, longitude: -79.38 }]);
    expect(bounds).not.toBeNull();
    expect(zoomForGeoBounds(bounds!)).toBeGreaterThanOrEqual(14);
  });
});

describe("mapViewportForBounds", () => {
  it("projects store coords back to their source pixels", () => {
    const bounds = geoBoundsFromCoords(TORONTO_STORES);
    expect(bounds).not.toBeNull();

    const viewport = mapViewportForBounds(bounds!, 640, 220);
    for (const store of TORONTO_STORES) {
      const pixel = projectLatLonInViewport(store.latitude, store.longitude, viewport);
      expect(pixel.x).toBeGreaterThanOrEqual(0);
      expect(pixel.x).toBeLessThanOrEqual(viewport.width);
      expect(pixel.y).toBeGreaterThanOrEqual(0);
      expect(pixel.y).toBeLessThanOrEqual(viewport.height);
    }
  });

  it("keeps northwest store above and left of southeast store", () => {
    const bounds = geoBoundsFromCoords(TORONTO_STORES);
    const viewport = mapViewportForBounds(bounds!, 640, 220);
    const [farmBoy, , longos] = projectCoordsToPercent(TORONTO_STORES, viewport);

    expect(longos.y).toBeLessThan(farmBoy.y);
    expect(longos.x).toBeLessThan(farmBoy.x);
  });
});

describe("mapsStaticUrlForViewport", () => {
  it("builds a static maps URL with center, zoom, size, and key", () => {
    const bounds = geoBoundsFromCoords(TORONTO_STORES);
    const viewport = mapViewportForBounds(bounds!, 640, 220);
    const url = mapsStaticUrlForViewport(viewport, "test-key");

    expect(url).toContain("maps.googleapis.com/maps/api/staticmap");
    expect(url).toContain(`center=${viewport.centerLat}%2C${viewport.centerLon}`);
    expect(url).toContain(`zoom=${viewport.zoom}`);
    expect(url).toContain("size=640x220");
    expect(url).toContain("scale=2");
    expect(url).toContain("key=test-key");
  });

  it("adds static map markers for each store", () => {
    const bounds = geoBoundsFromCoords(TORONTO_STORES);
    const viewport = mapViewportForBounds(bounds!, 640, 220);
    const url = mapsStaticUrlForViewport(viewport, "test-key", [
      { latitude: 43.63943, longitude: -79.38029, label: "F" },
      { latitude: 43.64239, longitude: -79.38118, label: "L" },
    ]);

    expect(url).toContain("markers=color%3Ared%7Clabel%3AF%7C43.63943%2C-79.38029");
    expect(url).toContain("markers=color%3Ared%7Clabel%3AL%7C43.64239%2C-79.38118");
  });
});

describe("staticMapMarkerParam", () => {
  it("uses the first alphanumeric character as the marker label", () => {
    expect(markerLabelForStore("Farm Boy", 0)).toBe("F");
    expect(staticMapMarkerParam({
      latitude: 43.64,
      longitude: -79.38,
      label: "F",
      color: "red",
    })).toBe("color:red|label:F|43.64,-79.38");
  });

  it("builds custom icon markers with anchor", () => {
    expect(staticMapMarkerParam({
      latitude: 43.64,
      longitude: -79.38,
      icon: "https://g.daliu.ca/markers/pin-accent-accent.png",
      anchor: { x: 24, y: 52 },
    })).toBe(
      "icon:https://g.daliu.ca/markers/pin-accent-accent.png|anchor:24,52|43.64,-79.38",
    );
  });

  it("keeps encoded path segments in dynamic icon URLs", () => {
    expect(staticMapMarkerParam({
      latitude: 43.64,
      longitude: -79.38,
      icon: "https://api-g.daliu.ca/markers/pill-badge/accent/Farm%20Boy.png",
      anchor: { x: 38, y: 33 },
    })).toBe(
      "icon:https://api-g.daliu.ca/markers/pill-badge/accent/Farm%20Boy.png|anchor:38,33|43.64,-79.38",
    );
  });
});
