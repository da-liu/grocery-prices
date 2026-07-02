/** Set to true to preview loading and upload UI states locally. */
export const DEV_FORCE_LOADING = false;

/** Simulated upload queue when DEV_FORCE_LOADING is on (null to disable). */
export const DEV_PREVIEW_UPLOAD: {
  done: number;
  processing: number;
  queued: number;
} | null = null;
