import { useEffect } from "react";
import { useUploadQueue } from "./UploadQueueContext";
import type { UploadQueueItem } from "./uploadQueue";

function Spinner() {
  return <span className="upload-spinner" aria-hidden="true" />;
}

function statusLabel(item: UploadQueueItem): string {
  switch (item.status) {
    case "queued":
      return "Waiting…";
    case "processing":
      return "Reading prices…";
    case "done":
      return item.productCount != null
        ? `${item.productCount} product${item.productCount === 1 ? "" : "s"}`
        : "Done";
    case "failed":
      return item.error ?? "Failed";
  }
}

export function UploadStatusBar({ onViewBrowse }: { onViewBrowse: () => void }) {
  const {
    items,
    toast,
    activeCount,
    queuedCount,
    dismissToast,
    clearFinished,
    expanded,
    setExpanded,
  } = useUploadQueue();

  const processing = items.some((item) => item.status === "processing");
  const hasPanel = items.length > 0;

  useEffect(() => {
    if (!toast) return;
    const timer = window.setTimeout(dismissToast, 6000);
    return () => window.clearTimeout(timer);
  }, [toast, dismissToast]);

  useEffect(() => {
    if (activeCount === 0 && items.some((item) => item.status === "done" || item.status === "failed")) {
      const timer = window.setTimeout(clearFinished, 15000);
      return () => window.clearTimeout(timer);
    }
  }, [activeCount, items, clearFinished]);

  if (!hasPanel && !toast) return null;

  const pillLabel = processing
    ? queuedCount > 0
      ? `Reading prices · ${queuedCount + 1} in queue`
      : "Reading prices from your photo…"
    : queuedCount > 0
      ? `${queuedCount} photo${queuedCount === 1 ? "" : "s"} queued`
      : "Processing photos…";

  return (
    <>
      {hasPanel && (
        <section className="upload-status" aria-live="polite">
          {activeCount > 0 && <div className="upload-status-progress" aria-hidden="true" />}
          <button
            type="button"
            className="upload-status-pill"
            aria-expanded={expanded}
            onClick={() => setExpanded(!expanded)}
          >
            {activeCount > 0 && <Spinner />}
            <span>{pillLabel}</span>
            <span className="upload-status-chevron" aria-hidden="true">
              {expanded ? "▾" : "▸"}
            </span>
          </button>

          {expanded && (
            <div className="upload-status-sheet">
              <p className="upload-status-hint">
                You can keep browsing. New products appear when each photo finishes.
              </p>
              <ul className="upload-status-list">
                {items.map((item) => (
                  <li
                    key={item.id}
                    className={`upload-status-item upload-status-item--${item.status}`}
                  >
                    <img src={item.thumbnailUrl} alt="" className="upload-status-thumb" />
                    <div className="upload-status-copy">
                      <strong>{item.label}</strong>
                      <span>{statusLabel(item)}</span>
                    </div>
                    {(item.status === "queued" || item.status === "processing") && (
                      <Spinner />
                    )}
                  </li>
                ))}
              </ul>
            </div>
          )}
        </section>
      )}

      {toast && (
        <div className="upload-toast" role="status">
          <span>
            Added {toast.productCount} product{toast.productCount === 1 ? "" : "s"}
          </span>
          <button type="button" onClick={onViewBrowse}>
            View
          </button>
          <button type="button" className="upload-toast-dismiss" aria-label="Dismiss" onClick={dismissToast}>
            ×
          </button>
        </div>
      )}
    </>
  );
}
