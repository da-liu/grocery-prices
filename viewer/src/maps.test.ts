import { describe, expect, it } from "vitest";
import { geoBoundsFromCoords, mapsEmbedUrlForBounds, zoomForGeoBounds } from "./maps";

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
