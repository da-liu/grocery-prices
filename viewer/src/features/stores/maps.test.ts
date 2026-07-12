import { describe, expect, it } from "vitest";
import {
  geoBoundsFromCoords,
  mapViewportForBounds,
  mapsStaticUrlForViewport,
  markerLabelForStore,
  staticMapMarkerParam,
} from "./maps";

const SAMPLE_STORES = [
  { latitude: 43.63943, longitude: -79.38029 },
  { latitude: 43.63961, longitude: -79.38039 },
  { latitude: 43.64239, longitude: -79.38118 },
];

describe("mapViewportForBounds", () => {
  it("fits nearby stores within the viewport dimensions", () => {
    const bounds = geoBoundsFromCoords(SAMPLE_STORES);
    expect(bounds).not.toBeNull();

    const viewport = mapViewportForBounds(bounds!, 640, 220);
    expect(viewport.width).toBe(640);
    expect(viewport.height).toBe(220);
    expect(viewport.zoom).toBeGreaterThanOrEqual(0);
    expect(viewport.centerLat).toBeGreaterThan(43.63);
    expect(viewport.centerLat).toBeLessThan(43.65);
  });

  it("uses a minimum span for a single store", () => {
    const bounds = geoBoundsFromCoords([{ latitude: 43.64, longitude: -79.38 }]);
    expect(bounds).not.toBeNull();

    const viewport = mapViewportForBounds(bounds!, 640, 220);
    expect(viewport.zoom).toBeGreaterThanOrEqual(10);
  });
});

describe("mapsStaticUrlForViewport", () => {
  it("builds a static maps URL with center, zoom, size, and key", () => {
    const bounds = geoBoundsFromCoords(SAMPLE_STORES);
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
    const bounds = geoBoundsFromCoords(SAMPLE_STORES);
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
      icon: "https://g.daliu.ca/markers/ring-dot-list-test24.png",
      anchor: { x: 12, y: 12 },
    })).toBe(
      "icon:https://g.daliu.ca/markers/ring-dot-list-test24.png|anchor:12,12|43.64,-79.38",
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
