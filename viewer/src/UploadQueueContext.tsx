import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useRef,
  useState,
} from "react";
import {
  completeOnboarding,
  fetchPhotoStatuses,
  uploadPhotosWithProgress,
  type DuplicateAction,
  type UploadResult,
} from "./api";
import { DuplicatePhotoModal } from "./DuplicatePhotoModal";
import { prepareUploadFile } from "./prepareUploadFile";
import {
  createQueueItem,
  MAX_BULK_BATCH,
  productCountFromResult,
  revokeQueueItem,
  UNKNOWN_STORE_HINT_KEY,
  UPLOAD_CONCURRENCY,
  shouldNotifyUnknownStoreHint,
  type PendingDuplicate,
  type UploadQueueItem,
  type UploadSource,
  type UploadToast,
} from "./uploadQueue";

import type { StoreLabelRequest } from "./types";

interface UploadQueueActions {
  enqueueFiles: (files: File[], source: UploadSource) => void;
  pendingLabel: StoreLabelRequest | null;
  requestLabel: (request: StoreLabelRequest) => void;
  dismissLabel: () => void;
  completeLabel: () => void;
}

interface UploadQueueStatus {
  items: UploadQueueItem[];
  toast: UploadToast | null;
  unknownStoreHint: boolean;
  activeCount: number;
  queuedCount: number;
  dismissToast: () => void;
  dismissUnknownStoreHint: () => void;
  clearFinished: () => void;
}

interface UploadQueueState extends UploadQueueActions, UploadQueueStatus {}

const UploadQueueActionsContext = createContext<UploadQueueActions | null>(null);
const UploadQueueStatusContext = createContext<UploadQueueStatus | null>(null);

const POLL_INTERVAL_MS = 1500;
const STATUS_POLL_MAX_FAILURES = 4;
const STATUS_POLL_MAX_DELAY_MS = 10000;
const MISSING_STATUS_MESSAGE =
  "Upload progress was temporarily unavailable. Your photo may still finish processing; refresh in a moment.";

function sleep(ms: number) {
  return new Promise<void>((resolve) => {
    window.setTimeout(resolve, ms);
  });
}

export function statusPollRetryDelayMs(consecutiveFailures: number): number {
  if (consecutiveFailures <= 0) return POLL_INTERVAL_MS;
  return Math.min(
    STATUS_POLL_MAX_DELAY_MS,
    POLL_INTERVAL_MS * 2 ** Math.max(0, consecutiveFailures - 1),
  );
}

function queueItemErrorMessage(err: unknown): string {
  return err instanceof Error ? err.message : "Upload failed";
}

function unknownStoreHintAlreadyShown(): boolean {
  try {
    return sessionStorage.getItem(UNKNOWN_STORE_HINT_KEY) === "1";
  } catch {
    return false;
  }
}

function markUnknownStoreHintShown(): void {
  try {
    sessionStorage.setItem(UNKNOWN_STORE_HINT_KEY, "1");
  } catch {
    // ignore storage errors
  }
}

function applyUploadResult(result: UploadResult): Partial<UploadQueueItem> {
  if (result.action_required) {
    return {
      status: "awaiting_duplicate",
      duplicateOf: result.duplicate_of,
    };
  }

  if (result.skipped) {
    return {
      status: "skipped",
      imageId: result.duplicate_of ?? result.image_id,
      productCount: 0,
    };
  }

  if (result.extraction_status === "failed") {
    return {
      status: "failed",
      imageId: result.image_id,
      error: result.extraction_error ?? "Extraction failed",
    };
  }

  const productCount = productCountFromResult(result);
  return {
    status: "done",
    productCount,
    imageId: result.image_id,
    extractionEmpty: result.extraction_empty,
    detectedReceipt: result.detected_receipt,
  };
}

function claimNextBatch(
  items: UploadQueueItem[],
  processingIds: ReadonlySet<string>,
  pendingDuplicateId: string | undefined,
): UploadQueueItem[] | null {
  const queued = items.filter(
    (item) =>
      item.status === "queued" &&
      !processingIds.has(item.id) &&
      item.id !== pendingDuplicateId,
  );
  if (!queued.length) return null;

  const source = queued[0].source;
  const sameSource = queued.filter((item) => item.source === source);
  if (sameSource.length >= 2) {
    return sameSource.slice(0, MAX_BULK_BATCH);
  }
  return [sameSource[0]];
}

export function UploadQueueProvider({
  children,
  onUploadSuccess,
}: {
  children: React.ReactNode;
  onUploadSuccess?: () => void | Promise<void>;
}) {
  const [items, setItems] = useState<UploadQueueItem[]>([]);
  const [toast, setToast] = useState<UploadToast | null>(null);
  const [unknownStoreHint, setUnknownStoreHint] = useState(false);
  const [labelQueue, setLabelQueue] = useState<StoreLabelRequest[]>([]);
  const [pendingDuplicate, setPendingDuplicate] = useState<PendingDuplicate | null>(null);
  const itemsRef = useRef(items);
  const inFlightRef = useRef(0);
  const processingIdsRef = useRef<Set<string>>(new Set());
  const pendingDuplicateRef = useRef<string | undefined>(undefined);
  const onUploadSuccessRef = useRef(onUploadSuccess);

  useEffect(() => {
    itemsRef.current = items;
  }, [items]);

  useEffect(() => {
    pendingDuplicateRef.current = pendingDuplicate?.itemId;
  }, [pendingDuplicate]);

  useEffect(() => {
    onUploadSuccessRef.current = onUploadSuccess;
  }, [onUploadSuccess]);

  const updateItem = useCallback((id: string, patch: Partial<UploadQueueItem>) => {
    setItems((prev) => prev.map((item) => (item.id === id ? { ...item, ...patch } : item)));
  }, []);

  const finishUpload = useCallback(
    async (item: UploadQueueItem, result: UploadResult) => {
      const patch = applyUploadResult(result);
      updateItem(item.id, patch);

      if (result.skipped || result.action_required) {
        return;
      }

      if (
        shouldNotifyUnknownStoreHint(
          Boolean(result.needs_store_label),
          unknownStoreHintAlreadyShown(),
        )
      ) {
        markUnknownStoreHintShown();
        setUnknownStoreHint(true);
      }

      setToast({
        id: crypto.randomUUID(),
        productCount: productCountFromResult(result),
        imageId: result.image_id,
        extractionEmpty: result.extraction_empty,
      });

      try {
        await completeOnboarding();
      } catch {
        // onboarding may already be complete
      }

      await onUploadSuccessRef.current?.();
    },
    [updateItem],
  );

  const resolveDuplicate = useCallback(
    (item: UploadQueueItem, duplicateOf: string) =>
      new Promise<DuplicateAction>((resolve) => {
        setPendingDuplicate({ itemId: item.id, duplicateOf, resolve });
      }),
    [],
  );

  const waitForExtraction = useCallback(
    async (item: UploadQueueItem, imageId: string) => {
      let consecutiveFailures = 0;
      for (;;) {
        await sleep(statusPollRetryDelayMs(consecutiveFailures));
        try {
          const { results } = await fetchPhotoStatuses([imageId]);
          const status = results[0];
          if (!status) {
            throw new Error(MISSING_STATUS_MESSAGE);
          }
          consecutiveFailures = 0;
          if (
            status.extraction_status === "pending" ||
            status.extraction_status === "processing"
          ) {
            if (status.photo_type === "receipt") {
              updateItem(item.id, { detectedReceipt: true });
            }
            continue;
          }
          await finishUpload(item, status);
          return;
        } catch (err) {
          consecutiveFailures += 1;
          if (consecutiveFailures >= STATUS_POLL_MAX_FAILURES) {
            throw new Error(queueItemErrorMessage(err));
          }
        }
      }
    },
    [finishUpload, updateItem],
  );

  const handleItemResult = useCallback(
    async (item: UploadQueueItem, result: UploadResult) => {
      if (result.action_required && result.duplicate_of) {
        updateItem(item.id, {
          status: "awaiting_duplicate",
          duplicateOf: result.duplicate_of,
        });
        const action = await resolveDuplicate(item, result.duplicate_of);
        setPendingDuplicate(null);
        if (action === "skip") {
          updateItem(item.id, {
            status: "skipped",
            duplicateOf: result.duplicate_of,
            productCount: 0,
            imageId: result.duplicate_of,
          });
          return;
        }
        updateItem(item.id, { status: "uploading", uploadProgress: 0 });
        const retried = await uploadPhotosWithProgress(
          [item.uploadFile ?? item.file],
          item.source,
          (percent) => {
            updateItem(item.id, { status: "uploading", uploadProgress: percent });
          },
          action,
          item.clientExif ? [item.clientExif] : undefined,
        );
        const retriedResult = retried.results[0];
        if (!retriedResult) {
          throw new Error("Upload returned no result");
        }
        await handleItemResult(item, retriedResult);
        return;
      }

      if (
        result.extraction_status === "pending" ||
        result.extraction_status === "processing"
      ) {
        updateItem(item.id, {
          status: "processing",
          uploadProgress: undefined,
          imageId: result.image_id,
          detectedReceipt: result.detected_receipt,
        });
        await waitForExtraction(item, result.image_id);
        return;
      }

      await finishUpload(item, result);
    },
    [finishUpload, resolveDuplicate, updateItem, waitForExtraction],
  );

  const processBatch = useCallback(
    async (batch: UploadQueueItem[]) => {
      const prepared: { file: File; clientExif?: UploadQueueItem["clientExif"] }[] = [];
      for (const item of batch) {
        updateItem(item.id, { status: "compressing" });
        try {
          const result = await prepareUploadFile(item.file);
          prepared.push({ file: result.file, clientExif: result.clientExif });
          updateItem(item.id, {
            uploadFile: result.file,
            clientExif: result.clientExif,
          });
        } catch (err) {
          const message = queueItemErrorMessage(err);
          for (const failed of batch) {
            updateItem(failed.id, { status: "failed", error: message });
          }
          return;
        }
      }

      const setBatchProgress = (percent: number) => {
        for (const item of batch) {
          updateItem(item.id, { status: "uploading", uploadProgress: percent });
        }
      };

      setBatchProgress(0);

      try {
        const bulk = await uploadPhotosWithProgress(
          prepared.map((entry) => entry.file),
          batch[0].source,
          setBatchProgress,
          undefined,
          prepared.map((entry) => entry.clientExif),
        );

        for (const item of batch) {
          updateItem(item.id, { uploadProgress: 100 });
        }

        const backgroundTasks: Promise<void>[] = [];
        for (let index = 0; index < batch.length; index += 1) {
          const item = batch[index];
          const result = bulk.results[index];
          if (!result) {
            updateItem(item.id, {
              status: "failed",
              error: "Upload returned no result",
            });
            continue;
          }

          const runItem = async () => {
            try {
              await handleItemResult(item, result);
            } catch (err) {
              updateItem(item.id, {
                status: "failed",
                error: queueItemErrorMessage(err),
              });
            }
          };

          if (
            result.extraction_status === "pending" ||
            result.extraction_status === "processing"
          ) {
            backgroundTasks.push(runItem());
            continue;
          }

          await runItem();
        }

        await Promise.all(backgroundTasks);
      } catch (err) {
        const message = queueItemErrorMessage(err);
        for (const item of batch) {
          updateItem(item.id, { status: "failed", error: message });
        }
      }
    },
    [handleItemResult, updateItem],
  );

  const pumpQueue = useCallback(() => {
    while (inFlightRef.current < UPLOAD_CONCURRENCY) {
      const batch = claimNextBatch(
        itemsRef.current,
        processingIdsRef.current,
        pendingDuplicateRef.current,
      );
      if (!batch) break;

      for (const item of batch) {
        processingIdsRef.current.add(item.id);
      }
      inFlightRef.current += 1;

      void processBatch(batch).finally(() => {
        for (const item of batch) {
          processingIdsRef.current.delete(item.id);
        }
        inFlightRef.current -= 1;
        pumpQueue();
      });
    }
  }, [processBatch]);

  useEffect(() => {
    pumpQueue();
  }, [items, pumpQueue, pendingDuplicate]);

  const enqueueFiles = useCallback(
    (files: File[], source: UploadSource) => {
      if (!files.length) return;
      const added = files.map((file) => createQueueItem(file, source));
      setItems((prev) => [...prev, ...added]);
    },
    [],
  );

  const dismissToast = useCallback(() => setToast(null), []);

  const dismissUnknownStoreHint = useCallback(() => setUnknownStoreHint(false), []);

  const requestLabel = useCallback((request: StoreLabelRequest) => {
    setLabelQueue((prev) => {
      if (prev.some((item) => item.imageId === request.imageId)) return prev;
      return [...prev, request];
    });
  }, []);

  const dismissLabel = useCallback(() => {
    setLabelQueue((prev) => prev.slice(1));
  }, []);

  const completeLabel = useCallback(() => {
    setLabelQueue((prev) => prev.slice(1));
    void onUploadSuccessRef.current?.();
  }, []);

  const clearFinished = useCallback(() => {
    setItems((prev) => {
      for (const item of prev) {
        if (
          item.status === "done" ||
          item.status === "failed" ||
          item.status === "skipped"
        ) {
          revokeQueueItem(item);
        }
      }
      return prev.filter(
        (item) =>
          item.status === "queued" ||
          item.status === "compressing" ||
          item.status === "uploading" ||
          item.status === "processing" ||
          item.status === "awaiting_duplicate",
      );
    });
  }, []);

  useEffect(() => {
    return () => {
      for (const item of itemsRef.current) {
        revokeQueueItem(item);
      }
    };
  }, []);

  const activeCount = items.filter(
    (item) =>
      item.status === "queued" ||
      item.status === "compressing" ||
      item.status === "uploading" ||
      item.status === "processing" ||
      item.status === "awaiting_duplicate",
  ).length;
  const queuedCount = items.filter((item) => item.status === "queued").length;

  const duplicateItem = pendingDuplicate
    ? items.find((item) => item.id === pendingDuplicate.itemId)
    : null;

  const actionsValue = useMemo(
    () => ({
      enqueueFiles,
      pendingLabel: labelQueue[0] ?? null,
      requestLabel,
      dismissLabel,
      completeLabel,
    }),
    [enqueueFiles, labelQueue, requestLabel, dismissLabel, completeLabel],
  );

  const statusValue = useMemo(
    () => ({
      items,
      toast,
      unknownStoreHint,
      activeCount,
      queuedCount,
      dismissToast,
      dismissUnknownStoreHint,
      clearFinished,
    }),
    [
      items,
      toast,
      unknownStoreHint,
      activeCount,
      queuedCount,
      dismissToast,
      dismissUnknownStoreHint,
      clearFinished,
    ],
  );

  return (
    <UploadQueueActionsContext.Provider value={actionsValue}>
      <UploadQueueStatusContext.Provider value={statusValue}>
        {children}
        {pendingDuplicate && duplicateItem && (
          <DuplicatePhotoModal
            duplicateOf={pendingDuplicate.duplicateOf}
            fileName={duplicateItem.label}
            thumbnailUrl={duplicateItem.thumbnailUrl}
            onChoose={(action) => pendingDuplicate.resolve(action)}
          />
        )}
      </UploadQueueStatusContext.Provider>
    </UploadQueueActionsContext.Provider>
  );
}

export function useUploadQueueActions() {
  const ctx = useContext(UploadQueueActionsContext);
  if (!ctx) throw new Error("useUploadQueueActions must be used within UploadQueueProvider");
  return ctx;
}

export function useUploadQueueStatus() {
  const ctx = useContext(UploadQueueStatusContext);
  if (!ctx) throw new Error("useUploadQueueStatus must be used within UploadQueueProvider");
  return ctx;
}

export function useUploadQueue(): UploadQueueState {
  return { ...useUploadQueueActions(), ...useUploadQueueStatus() };
}

// Exported for unit tests.
export { claimNextBatch, queueItemErrorMessage };
