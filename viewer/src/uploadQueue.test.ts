import { describe, expect, it } from "vitest";
import {
  claimNextBatch,
  queueItemErrorMessage,
  statusPollRetryDelayMs,
} from "./UploadQueueContext";
import { shouldNotifyUnknownStoreHint } from "./uploadQueue";
import type { UploadQueueItem } from "./uploadQueue";

function item(id: string, status: UploadQueueItem["status"], source: UploadQueueItem["source"] = "shelf") {
  return {
    id,
    label: `${id}.jpg`,
    thumbnailUrl: "blob:test",
    status,
    source,
    file: new File([], `${id}.jpg`),
  } satisfies UploadQueueItem;
}

describe("claimNextBatch", () => {
  it("returns a single queued item when only one is waiting", () => {
    const batch = claimNextBatch(
      [item("a", "queued"), item("b", "processing")],
      new Set(),
      undefined,
    );
    expect(batch?.map((entry) => entry.id)).toEqual(["a"]);
  });

  it("batches multiple queued items with the same source", () => {
    const batch = claimNextBatch(
      [item("a", "queued"), item("b", "queued"), item("c", "queued", "receipt")],
      new Set(),
      undefined,
    );
    expect(batch?.map((entry) => entry.id)).toEqual(["a", "b"]);
  });

  it("skips items already marked in-flight", () => {
    const batch = claimNextBatch(
      [item("a", "queued"), item("b", "queued")],
      new Set(["a"]),
      undefined,
    );
    expect(batch?.map((entry) => entry.id)).toEqual(["b"]);
  });

  it("skips the item awaiting duplicate resolution", () => {
    const batch = claimNextBatch(
      [item("a", "queued"), item("b", "queued")],
      new Set(),
      "a",
    );
    expect(batch?.map((entry) => entry.id)).toEqual(["b"]);
  });
});

describe("statusPollRetryDelayMs", () => {
  it("uses the base poll interval before any failures", () => {
    expect(statusPollRetryDelayMs(0)).toBe(1500);
  });

  it("backs off after consecutive failures", () => {
    expect(statusPollRetryDelayMs(1)).toBe(1500);
    expect(statusPollRetryDelayMs(2)).toBe(3000);
    expect(statusPollRetryDelayMs(3)).toBe(6000);
  });

  it("caps the retry delay", () => {
    expect(statusPollRetryDelayMs(10)).toBe(10000);
  });
});

describe("queueItemErrorMessage", () => {
  it("returns the thrown error message when available", () => {
    expect(queueItemErrorMessage(new Error("Lost connection while checking upload progress"))).toBe(
      "Lost connection while checking upload progress",
    );
  });

  it("falls back for non-Error values", () => {
    expect(queueItemErrorMessage("oops")).toBe("Upload failed");
  });
});

describe("shouldNotifyUnknownStoreHint", () => {
  it("shows hint when store label is needed and not yet shown", () => {
    expect(shouldNotifyUnknownStoreHint(true, false)).toBe(true);
  });

  it("skips hint when already shown this session", () => {
    expect(shouldNotifyUnknownStoreHint(true, true)).toBe(false);
  });

  it("skips hint when store label is not needed", () => {
    expect(shouldNotifyUnknownStoreHint(false, false)).toBe(false);
  });
});
