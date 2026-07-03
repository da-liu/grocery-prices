import { describe, expect, it } from "vitest";
import { claimNextBatch } from "./UploadQueueContext";
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
