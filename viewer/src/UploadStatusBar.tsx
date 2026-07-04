import { useEffect, useRef, useState } from "react";
import { DEV_FORCE_LOADING, DEV_PREVIEW_UPLOAD } from "./devPreview";
import { useUploadQueueStatus } from "./UploadQueueContext";
import type { UploadQueueItem } from "./uploadQueue";

function buildPreviewUploadItems(scenario: {
  done: number;
  processing: number;
  queued: number;
}): UploadQueueItem[] {
  const items: UploadQueueItem[] = [];
  let index = 0;

  for (let i = 0; i < scenario.done; i += 1) {
    items.push({
      id: `preview-done-${i}`,
      label: `IMG_${String(3000 + index)}.jpg`,
      thumbnailUrl: "/onboarding-shelf-sample.jpg",
      status: "done",
      source: "shelf",
      file: new File([], `IMG_${String(3000 + index)}.jpg`),
      productCount: 4 + i,
    });
    index += 1;
  }

  for (let i = 0; i < scenario.processing; i += 1) {
    items.push({
      id: `preview-processing-${i}`,
      label: `IMG_${String(3000 + index)}.jpg`,
      thumbnailUrl: "/onboarding-shelf-sample.jpg",
      status: "processing",
      source: "shelf",
      file: new File([], `IMG_${String(3000 + index)}.jpg`),
    });
    index += 1;
  }

  for (let i = 0; i < scenario.queued; i += 1) {
    items.push({
      id: `preview-queued-${i}`,
      label: `IMG_${String(3000 + index)}.jpg`,
      thumbnailUrl: "/onboarding-shelf-sample.jpg",
      status: "queued",
      source: i % 4 === 0 ? "receipt" : "shelf",
      file: new File([], `IMG_${String(3000 + index)}.jpg`),
    });
    index += 1;
  }

  return items;
}

const PREVIEW_UPLOAD_ITEMS: UploadQueueItem[] =
  DEV_FORCE_LOADING && DEV_PREVIEW_UPLOAD
    ? buildPreviewUploadItems(DEV_PREVIEW_UPLOAD)
    : [];

function Spinner() {
  return <span className="upload-spinner" aria-hidden="true" />;
}

function statusLabel(item: UploadQueueItem): string {
  switch (item.status) {
    case "preparing":
      return "Compressing…";
    case "queued":
      return "Waiting…";
    case "processing":
      return item.detectedReceipt ? "Detected receipt · reading prices…" : "Reading prices…";
    case "awaiting_duplicate":
      return "Duplicate detected";
    case "done":
      if (item.extractionEmpty) return "No products found";
      if (item.productCount != null) {
        return `${item.productCount} product${item.productCount === 1 ? "" : "s"}`;
      }
      return "Done";
    case "skipped":
      return "Skipped duplicate";
    case "failed":
      return item.error ?? "Failed";
  }
}

function ChevronIcon({ expanded }: { expanded: boolean }) {
  return (
    <svg
      className={`upload-status-chevron${expanded ? "" : " upload-status-chevron--collapsed"}`}
      viewBox="0 0 24 24"
      width="20"
      height="20"
      aria-hidden="true"
    >
      <path
        fill="none"
        stroke="currentColor"
        strokeWidth="2"
        strokeLinecap="round"
        strokeLinejoin="round"
        d="M6 9l6 6 6-6"
      />
    </svg>
  );
}

function useUploadStatusDisplay() {
  const { items, activeCount, queuedCount, clearFinished } = useUploadQueueStatus();
  const [expanded, setExpanded] = useState(false);
  const itemCountRef = useRef(items.length);

  const processing = items.some((item) => item.status === "processing");
  const previewActive = DEV_FORCE_LOADING && PREVIEW_UPLOAD_ITEMS.length > 0;
  const displayItems = previewActive ? PREVIEW_UPLOAD_ITEMS : items;
  const hasPanel = displayItems.length > 0;
  const displayActiveCount = previewActive
    ? PREVIEW_UPLOAD_ITEMS.filter(
        (item) => item.status === "queued" || item.status === "processing",
      ).length
    : activeCount;
  const displayQueuedCount = previewActive
    ? PREVIEW_UPLOAD_ITEMS.filter((item) => item.status === "queued").length
    : queuedCount;
  const displayProcessing = previewActive || processing;

  useEffect(() => {
    if (previewActive) setExpanded(true);
  }, [previewActive]);

  useEffect(() => {
    if (items.length > itemCountRef.current) {
      setExpanded(true);
    }
    itemCountRef.current = items.length;
  }, [items.length]);

  useEffect(() => {
    if (
      activeCount === 0 &&
      items.some(
        (item) =>
          item.status === "done" || item.status === "failed" || item.status === "skipped",
      )
    ) {
      const timer = window.setTimeout(clearFinished, 15000);
      return () => window.clearTimeout(timer);
    }
  }, [activeCount, items, clearFinished]);

  const pillLabel = displayProcessing
    ? displayQueuedCount > 0
      ? `Reading prices · ${displayQueuedCount + 1} in queue`
      : "Reading prices from your photo…"
    : displayQueuedCount > 0
      ? `${displayQueuedCount} photo${displayQueuedCount === 1 ? "" : "s"} queued`
      : "Processing photos…";

  return {
    displayItems,
    hasPanel,
    displayActiveCount,
    expanded,
    setExpanded,
    pillLabel,
  };
}

export function UploadStatusPanel() {
  const {
    displayItems,
    hasPanel,
    displayActiveCount,
    expanded,
    setExpanded,
    pillLabel,
  } = useUploadStatusDisplay();

  if (!hasPanel) return null;

  return (
    <section className="upload-status" aria-live="polite">
      <button
        type="button"
        className="upload-status-pill"
        aria-expanded={expanded}
        onClick={() => setExpanded(!expanded)}
      >
        {displayActiveCount > 0 && <Spinner />}
        <span>{pillLabel}</span>
        <ChevronIcon expanded={expanded} />
      </button>

      <div className="upload-status-sheet" hidden={!expanded}>
          <p className="upload-status-hint">
            You can keep browsing. New products appear when each photo finishes.
          </p>
          <ul className="upload-status-list">
            {displayItems.map((item) => (
              <li
                key={item.id}
                className={`upload-status-item upload-status-item--${item.status}`}
              >
                {item.thumbnailUrl ? (
                  <img src={item.thumbnailUrl} alt="" className="upload-status-thumb" />
                ) : (
                  <div className="upload-status-thumb" aria-hidden="true" />
                )}
                <div className="upload-status-copy">
                  <strong>{item.label}</strong>
                  <span>{statusLabel(item)}</span>
                </div>
                {(item.status === "preparing" ||
                  item.status === "queued" ||
                  item.status === "processing") && <Spinner />}
              </li>
            ))}
          </ul>
        </div>
    </section>
  );
}

export function UploadStatusToasts() {
  const { toast, unknownStoreHint, dismissToast, dismissUnknownStoreHint } = useUploadQueueStatus();

  useEffect(() => {
    if (!unknownStoreHint) return;
    const timer = window.setTimeout(dismissUnknownStoreHint, 8000);
    return () => window.clearTimeout(timer);
  }, [unknownStoreHint, dismissUnknownStoreHint]);

  useEffect(() => {
    if (!toast) return;
    const timer = window.setTimeout(dismissToast, 6000);
    return () => window.clearTimeout(timer);
  }, [toast, dismissToast]);

  if (!toast && !unknownStoreHint) return null;

  return (
    <>
      {unknownStoreHint && (
        <div className="upload-toast upload-toast--hint" role="status">
          <span>
            Some photos have an unknown store. Tap the pin on a product card to label.
          </span>
          <button
            type="button"
            className="upload-toast-dismiss"
            aria-label="Dismiss"
            onClick={dismissUnknownStoreHint}
          >
            ×
          </button>
        </div>
      )}

      {toast && (
        <div className="upload-toast" role="status">
          <span>
            {toast.extractionEmpty
              ? "No products extracted"
              : `Added ${toast.productCount} product${toast.productCount === 1 ? "" : "s"}`}
            {toast.note ? ` ${toast.note}` : ""}
          </span>
          <button
            type="button"
            className="upload-toast-dismiss"
            aria-label="Dismiss"
            onClick={dismissToast}
          >
            ×
          </button>
        </div>
      )}
    </>
  );
}

export function UploadStatusBar() {
  return (
    <>
      <UploadStatusPanel />
      <UploadStatusToasts />
    </>
  );
}
