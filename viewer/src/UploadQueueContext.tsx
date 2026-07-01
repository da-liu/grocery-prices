import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useRef,
  useState,
} from "react";
import { completeOnboarding, uploadPhoto, uploadReceiptBulk } from "./api";
import {
  createQueueItem,
  productCountFromResult,
  revokeQueueItem,
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
  const itemsRef = useRef(items);
  const processingRef = useRef(false);
  const onUploadSuccessRef = useRef(onUploadSuccess);

  useEffect(() => {
    itemsRef.current = items;
  }, [items]);

  useEffect(() => {
    onUploadSuccessRef.current = onUploadSuccess;
  }, [onUploadSuccess]);

  const updateItem = useCallback((id: string, patch: Partial<UploadQueueItem>) => {
    setItems((prev) => prev.map((item) => (item.id === id ? { ...item, ...patch } : item)));
  }, []);

  const processQueue = useCallback(async () => {
    if (processingRef.current) return;
    processingRef.current = true;

    try {
      while (true) {
        const next = itemsRef.current.find((item) => item.status === "queued");
        if (!next) break;

        updateItem(next.id, { status: "processing" });

        try {
          const result =
            next.source === "receipt"
              ? (await uploadReceiptBulk([next.file])).results[0]
              : await uploadPhoto(next.file);

          if (!result) {
            throw new Error("Upload returned no result");
          }

          const productCount = productCountFromResult(result);
          updateItem(next.id, {
            status: "done",
            productCount,
            imageId: result.image_id,
          });

          if (result.needs_store_label) {
            setLabelQueue((prev) => [
              ...prev,
              {
                imageId: result.image_id,
                thumbnailUrl: next.thumbnailUrl,
                latitude: result.meta?.gps_latitude ?? null,
                longitude: result.meta?.gps_longitude ?? null,
              },
            ]);
          }

          setToast({
            id: crypto.randomUUID(),
            productCount,
            imageId: result.image_id,
          });

          try {
            await completeOnboarding();
          } catch {
            // onboarding may already be complete
          }

          await onUploadSuccessRef.current?.();
        } catch (err) {
          updateItem(next.id, {
            status: "failed",
            error: err instanceof Error ? err.message : "Upload failed",
          });
        }
      }
    } finally {
      processingRef.current = false;
      if (itemsRef.current.some((item) => item.status === "queued")) {
        void processQueue();
      }
    }
  }, [updateItem]);

  const enqueueFiles = useCallback(
    (files: File[], source: UploadSource) => {
      if (!files.length) return;
      const added = files.map((file) => createQueueItem(file, source));
      setItems((prev) => [...prev, ...added]);
      setExpanded(true);
      queueMicrotask(() => void processQueue());
    },
    [processQueue],
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
        if (item.status === "done" || item.status === "failed") {
          revokeQueueItem(item);
        }
      }
      return prev.filter((item) => item.status === "queued" || item.status === "processing");
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
    (item) => item.status === "queued" || item.status === "processing",
  ).length;
  const queuedCount = items.filter((item) => item.status === "queued").length;

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

  return <UploadQueueContext.Provider value={value}>{children}</UploadQueueContext.Provider>;
}

export function useUploadQueue() {
  const ctx = useContext(UploadQueueContext);
  if (!ctx) throw new Error("useUploadQueue must be used within UploadQueueProvider");
  return ctx;
}
