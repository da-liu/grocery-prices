import { afterEach, describe, expect, it, vi } from "vitest";
import { requestDeviceLocation } from "./deviceLocation";

describe("requestDeviceLocation", () => {
  afterEach(() => {
    vi.unstubAllGlobals();
    vi.restoreAllMocks();
  });

  it("returns coords when the user grants permission", async () => {
    vi.stubGlobal("navigator", {
      geolocation: {
        getCurrentPosition: (
          success: (position: GeolocationPosition) => void,
        ) => {
          success({
            coords: {
              latitude: 43.65,
              longitude: -79.38,
              accuracy: 10,
              altitude: null,
              altitudeAccuracy: null,
              heading: null,
              speed: null,
              toJSON: () => ({}),
            },
            timestamp: Date.now(),
            toJSON: () => ({}),
          });
        },
      },
    });

    await expect(requestDeviceLocation()).resolves.toEqual({
      ok: true,
      latitude: 43.65,
      longitude: -79.38,
    });
  });

  it("returns a calm message when permission is denied", async () => {
    vi.stubGlobal("navigator", {
      geolocation: {
        getCurrentPosition: (
          _success: unknown,
          error: (err: GeolocationPositionError) => void,
        ) => {
          error({
            code: 1,
            PERMISSION_DENIED: 1,
            POSITION_UNAVAILABLE: 2,
            TIMEOUT: 3,
            message: "denied",
          } as GeolocationPositionError);
        },
      },
    });

    const result = await requestDeviceLocation();
    expect(result.ok).toBe(false);
    if (!result.ok) {
      expect(result.message).toMatch(/denied/i);
    }
  });

  it("handles missing geolocation API", async () => {
    vi.stubGlobal("navigator", {});
    const result = await requestDeviceLocation();
    expect(result.ok).toBe(false);
    if (!result.ok) {
      expect(result.message).toMatch(/does not support/i);
    }
  });
});
