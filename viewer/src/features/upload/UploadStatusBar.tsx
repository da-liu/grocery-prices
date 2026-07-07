import { useEffect, useRef, useState } from "react";
import { useUploadQueueStatus } from "./UploadQueueContext";
import { ExtractionProgressBar } from "./ExtractionProgressBar";
import { extractionProgressPercent } from "./extractionProgress";
import type { UploadQueueItem } from "./uploadQueue";
import "./UploadStatusBar.css";

function Spinner() {
  return <span className="upload-spinner" aria-hidden="true" />;
}

function statusLabel(item: UploadQueueItem): string {
  switch (item.status) {
    case "queued":
      return "Waiting…";
    case "compressing":
      return "Compressing…";
    case "uploading": {
      const percent = item.uploadProgress ?? 0;
      return percent >= 100 ? "Uploaded" : `Uploading… ${percent}%`;
    }
    case "processing": {
      const percent = extractionProgressPercent(item.processingStartedAt, item.extractBackend);
      const phase = item.detectedReceipt ? "reading receipt prices" : "reading prices";
      return percent > 0 ? `Uploaded · ${phase}… ${percent}%` : `Uploaded · ${phase}…`;
    }
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

  const compressing = items.some((item) => item.status === "compressing");
  const uploading = items.some((item) => item.status === "uploading");
  const processing = items.some((item) => item.status === "processing");
  const hasPanel = items.length > 0;

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

  const pillLabel = compressing
    ? queuedCount > 0
      ? `Compressing · ${queuedCount + 1} in queue`
      : "Compressing photo…"
    : uploading
      ? queuedCount > 0
        ? `Uploading · ${queuedCount + 1} in queue`
        : "Uploading photo…"
      : processing
      ? queuedCount > 0
        ? `Reading prices · ${queuedCount + 1} in queue`
        : "Reading prices from your photo…"
      : queuedCount > 0
        ? `${queuedCount} photo${queuedCount === 1 ? "" : "s"} queued`
        : activeCount === 0
          ? "Uploads finished"
          : "Duplicate detected";

  return {
    items,
    hasPanel,
    activeCount,
    expanded,
    setExpanded,
    pillLabel,
  };
}

export function UploadStatusPanel() {
  const {
    items,
    hasPanel,
    activeCount,
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
        {activeCount > 0 && <Spinner />}
        <span>{pillLabel}</span>
        <ChevronIcon expanded={expanded} />
      </button>

      <div className="upload-status-sheet" hidden={!expanded}>
          <p className="upload-status-hint">
            You can keep browsing. New products appear when each photo finishes.
          </p>
          <ul className="upload-status-list">
            {items.map((item) => (
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
                  {item.status === "uploading" && (
                    <div
                      className="upload-status-progress"
                      role="progressbar"
                      aria-valuenow={item.uploadProgress ?? 0}
                      aria-valuemin={0}
                      aria-valuemax={100}
                      aria-label="Upload progress"
                    >
                      <div
                        className="upload-status-progress-bar"
                        style={{ width: `${item.uploadProgress ?? 0}%` }}
                      />
                    </div>
                  )}
                  {item.status === "processing" && item.processingStartedAt != null && (
                    <ExtractionProgressBar
                      startedAt={item.processingStartedAt}
                      backend={item.extractBackend}
                    />
                  )}
                </div>
                {(item.status === "queued" ||
                  item.status === "compressing" ||
                  item.status === "uploading" ||
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
