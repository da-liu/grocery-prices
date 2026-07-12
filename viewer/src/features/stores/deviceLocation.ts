export type DeviceLocationResult =
  | { ok: true; latitude: number; longitude: number }
  | { ok: false; message: string };

/**
 * Request device coordinates. Call only after an explicit user action
 * (and after showing an ahead notice). Never invoke on mount.
 */
export function requestDeviceLocation(
  options: PositionOptions = { enableHighAccuracy: true, timeout: 15_000, maximumAge: 60_000 },
): Promise<DeviceLocationResult> {
  if (typeof navigator === "undefined" || !navigator.geolocation) {
    return Promise.resolve({
      ok: false,
      message: "This device does not support location sharing.",
    });
  }

  return new Promise((resolve) => {
    navigator.geolocation.getCurrentPosition(
      (position) => {
        resolve({
          ok: true,
          latitude: position.coords.latitude,
          longitude: position.coords.longitude,
        });
      },
      (error) => {
        let message = "Could not get your location.";
        if (error.code === error.PERMISSION_DENIED) {
          message = "Location permission was denied. You can search or paste a Maps link instead.";
        } else if (error.code === error.TIMEOUT) {
          message = "Location request timed out. Try again, or search / paste a link.";
        } else if (error.code === error.POSITION_UNAVAILABLE) {
          message = "Location is unavailable right now. Try search or paste a Maps link.";
        }
        resolve({ ok: false, message });
      },
      options,
    );
  });
}
