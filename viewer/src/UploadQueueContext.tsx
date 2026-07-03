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
  uploadPhotosBulk,
  type DuplicateAction,
  type UploadResult,
} from "./api";
import { DuplicatePhotoModal } from "./DuplicatePhotoModal";
import { prepareUploadFile } from "./compressForUpload";
import {
  createQueueItem,
  MAX_BULK_BATCH,
  productCountFromResult,
  revokeQueueItem,
  UPLOAD_CONCURRENCY,
  type PendingDuplicate,
  type UploadQueueItem,
  type UploadSource,
  type UploadToast,
} from "./uploadQueue";

import type { StoreLabelRequest } from "./types";

interface UploadQueueState {
  items: UploadQueueItem[];
  toast: UploadToast | null;
  activeCount: number;
  queuedCount: number;
  enqueueFiles: (files: File[], source: UploadSource) => void;
  dismissToast: () => void;
  clearFinished: () => void;
  expanded: boolean;
  setExpanded: (open: boolean) => void;
  pendingLabel: StoreLabelRequest | null;
  requestLabel: (request: StoreLabelRequest) => void;
  dismissLabel: () => void;
  completeLabel: () => void;
}

const UploadQueueContext = createContext<UploadQueueState | null>(null);

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

  const productCount = productCountFromResult(result);
  return {
    status: "done",
    productCount,
    imageId: result.image_id,
    extractionEmpty: result.extraction_empty,
    overlappingCount: result.overlapping_products?.length ?? 0,
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
  const [expanded, setExpanded] = useState(false);
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

      if (result.needs_store_label) {
        setLabelQueue((prev) => [
          ...prev,
          {
            imageId: result.image_id,
            thumbnailUrl: item.thumbnailUrl,
            latitude: result.meta?.gps_latitude ?? null,
            longitude: result.meta?.gps_longitude ?? null,
          },
        ]);
      }

      setToast({
        id: crypto.randomUUID(),
        productCount: productCountFromResult(result),
        imageId: result.image_id,
        extractionEmpty: result.extraction_empty,
        overlappingCount: result.overlapping_products?.length ?? 0,
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
        const retried = await uploadPhotosBulk(
          [item.uploadFile ?? item.file],
          item.source,
          action,
        );
        const retriedResult = retried.results[0];
        if (!retriedResult) {
          throw new Error("Upload returned no result");
        }
        await handleItemResult(item, retriedResult);
        return;
      }

      await finishUpload(item, result);
    },
    [finishUpload, resolveDuplicate, updateItem],
  );

  const processBatch = useCallback(
    async (batch: UploadQueueItem[]) => {
      for (const item of batch) {
        updateItem(item.id, { status: "processing" });
      }

      try {
        const bulk = await uploadPhotosBulk(
          batch.map((item) => item.uploadFile ?? item.file),
          batch[0].source,
        );

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
          await handleItemResult(item, result);
        }
      } catch (err) {
        const message = err instanceof Error ? err.message : "Upload failed";
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
      setExpanded(true);

      for (const item of added) {
        void prepareUploadFile(item.file)
          .then(({ uploadFile, thumbnailUrl }) => {
            updateItem(item.id, { uploadFile, thumbnailUrl, status: "queued" });
          })
          .catch((err) => {
            const message = err instanceof Error ? err.message : "Compression failed";
            updateItem(item.id, { status: "failed", error: message });
          });
      }
    },
    [updateItem],
  );

  const dismissToast = useCallback(() => setToast(null), []);

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
          item.status === "preparing" ||
          item.status === "queued" ||
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
      item.status === "preparing" ||
      item.status === "queued" ||
      item.status === "processing" ||
      item.status === "awaiting_duplicate",
  ).length;
  const queuedCount = items.filter((item) => item.status === "queued").length;

  const duplicateItem = pendingDuplicate
    ? items.find((item) => item.id === pendingDuplicate.itemId)
    : null;

  const value = useMemo(
    () => ({
      items,
      toast,
      activeCount,
      queuedCount,
      enqueueFiles,
      dismissToast,
      clearFinished,
      expanded,
      setExpanded,
      pendingLabel: labelQueue[0] ?? null,
      requestLabel,
      dismissLabel,
      completeLabel,
    }),
    [
      items,
      toast,
      activeCount,
      queuedCount,
      enqueueFiles,
      dismissToast,
      clearFinished,
      expanded,
      labelQueue,
      requestLabel,
      dismissLabel,
      completeLabel,
    ],
  );

  return (
    <UploadQueueContext.Provider value={value}>
      {children}
      {pendingDuplicate && duplicateItem && (
        <DuplicatePhotoModal
          duplicateOf={pendingDuplicate.duplicateOf}
          fileName={duplicateItem.label}
          thumbnailUrl={duplicateItem.thumbnailUrl}
          onChoose={(action) => pendingDuplicate.resolve(action)}
        />
      )}
    </UploadQueueContext.Provider>
  );
}

export function useUploadQueue() {
  const ctx = useContext(UploadQueueContext);
  if (!ctx) throw new Error("useUploadQueue must be used within UploadQueueProvider");
  return ctx;
}

// Exported for unit tests.
export { claimNextBatch };
