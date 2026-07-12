import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useRef,
  useState,
  type ReactNode,
} from "react";
import {
  addManualProduct,
  completeOnboarding,
  deleteProduct,
  deletePhoto,
  deleteProductsBulk,
  fetchProducts,
  needsWelcomeOnboarding,
  reextractPhoto,
  updateProduct,
  type ManualProductInput,
  type ProductUpdateInput,
} from "@/shared/api/api";
import {
  EMPTY_BROWSE_QUERY,
  countActiveChips,
  filterProducts,
  getPriceExtents,
  loadBrowseQueryFromStorage,
  loadBrowseViewPrefsFromStorage,
  mergeBrowseQuery,
  parseBrowseQueryFromSearch,
  productsForPriceHistogram,
  saveBrowseQueryToStorage,
  sortProducts,
  syncBrowseQueryToUrl,
  type BrowseQueryState,
} from "./browseQuery";
import { computeBulkDeleteImpact, type BulkDeleteImpact } from "./bulkDelete";
import { formatPrice } from "@/shared/lib/formatPrice";
import type { BrowseStats, Product } from "@/shared/types/types";

function initialBrowseQuery(): BrowseQueryState {
  const fromViewPrefs = loadBrowseViewPrefsFromStorage() ?? {};
  const fromStorage = loadBrowseQueryFromStorage() ?? {};
  const fromUrl = parseBrowseQueryFromSearch(window.location.search);
  return mergeBrowseQuery(EMPTY_BROWSE_QUERY, { ...fromViewPrefs, ...fromStorage, ...fromUrl });
}

interface CatalogContextValue {
  products: Product[];
  productsLoading: boolean;
  error: string | null;
  setError: (error: string | null) => void;
  showOnboarding: boolean;
  setShowOnboarding: (show: boolean) => void;
  finishOnboarding: () => Promise<void>;
  refreshProducts: (options?: { silent?: boolean }) => Promise<void>;
  handleUploadSuccess: (info?: { imageId?: string; productCount?: number }) => Promise<void>;
  browseSearch: string;
  setBrowseSearch: (search: string) => void;
  browseQuery: BrowseQueryState;
  setBrowseQuery: (query: BrowseQueryState) => void;
  sortFilterOpen: boolean;
  setSortFilterOpen: (open: boolean) => void;
  activeChipCount: number;
  priceExtentsForChips: ReturnType<typeof getPriceExtents>;
  stores: string[];
  categories: string[];
  browseDisplayed: Product[];
  browseStats: BrowseStats;
  photoGroupSizes: Map<string, number>;
  multiProductTipImageId: string | null;
  productsById: Map<string, Product>;
  navigateToProduct: (productId: string) => void;
  navigateToPhotoGroup: (imageId: string, productId: string) => void;
  highlightProductId: string | null;
  highlightPhotoGroupId: string | null;
  deletingId: string | null;
  deletingPhotoId: string | null;
  savingId: string | null;
  reextractingId: string | null;
  reextractStartedAt: number | null;
  handleDeleteProduct: (productId: string) => void;
  handleDeletePhoto: (imageId: string) => void;
  handleEditProduct: (productId: string, updates: ProductUpdateInput) => Promise<void>;
  handleReextractPhoto: (imageId: string) => Promise<void>;
  handleAddManualProduct: (imageId: string, product: ManualProductInput) => Promise<void>;
  selectionMode: boolean;
  setSelectionMode: (mode: boolean) => void;
  selectedIds: Set<string>;
  setSelectedIds: (ids: Set<string>) => void;
  toggleProductSelection: (productId: string) => void;
  requestBulkDelete: (ids: string[]) => void;
  confirmBulkDelete: () => void;
  cancelBulkDelete: () => void;
  bulkDeleteImpact: BulkDeleteImpact | null;
  bulkDeleting: boolean;
  resetBrowseUi: () => void;
}

const CatalogContext = createContext<CatalogContextValue | null>(null);

export function useCatalog() {
  const value = useContext(CatalogContext);
  if (!value) {
    throw new Error("useCatalog must be used within CatalogProvider");
  }
  return value;
}

interface CatalogProviderProps {
  user: { onboarding_completed: string[] } | null;
  refreshAuth: () => Promise<void>;
  children: ReactNode;
}

export function CatalogProvider({ user, refreshAuth, children }: CatalogProviderProps) {
  const [products, setProducts] = useState<Product[]>([]);
  const [productsLoading, setProductsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [showOnboarding, setShowOnboarding] = useState(false);
  const [browseSearch, setBrowseSearch] = useState("");
  const [browseQuery, setBrowseQuery] = useState<BrowseQueryState>(initialBrowseQuery);
  const [sortFilterOpen, setSortFilterOpen] = useState(false);
  const [deletingId, setDeletingId] = useState<string | null>(null);
  const [deletingPhotoId, setDeletingPhotoId] = useState<string | null>(null);
  const [savingId, setSavingId] = useState<string | null>(null);
  const [reextractingId, setReextractingId] = useState<string | null>(null);
  const [reextractStartedAt, setReextractStartedAt] = useState<number | null>(null);
  const [selectionMode, setSelectionMode] = useState(false);
  const [selectedIds, setSelectedIds] = useState<Set<string>>(new Set());
  const [bulkDeleteImpact, setBulkDeleteImpact] = useState<BulkDeleteImpact | null>(null);
  const [bulkDeleting, setBulkDeleting] = useState(false);
  const [highlightProductId, setHighlightProductId] = useState<string | null>(null);
  const [highlightPhotoGroupId, setHighlightPhotoGroupId] = useState<string | null>(null);
  const [multiProductTipImageId, setMultiProductTipImageId] = useState<string | null>(null);

  const refreshProducts = useCallback(
    (options?: { silent?: boolean }) => {
      if (!user) return Promise.resolve();
      if (!options?.silent) setProductsLoading(true);
      setError(null);
      return fetchProducts()
        .then((rows) => setProducts(rows))
        .catch((e: Error) => setError(e.message))
        .finally(() => setProductsLoading(false));
    },
    [user],
  );

  const handleUploadSuccess = useCallback(
    async (info?: { imageId?: string; productCount?: number }) => {
      if (info?.imageId && (info.productCount ?? 0) >= 2) {
        setMultiProductTipImageId(info.imageId);
      }
      await refreshAuth();
      await refreshProducts({ silent: true });
      setShowOnboarding(false);
    },
    [refreshAuth, refreshProducts],
  );

  useEffect(() => {
    if (user) {
      refreshProducts();
      if (needsWelcomeOnboarding(user.onboarding_completed)) {
        setShowOnboarding(true);
      }
    } else {
      setProducts([]);
    }
  }, [user, refreshProducts]);

  const browseQueryRef = useRef(browseQuery);
  browseQueryRef.current = browseQuery;

  useEffect(() => {
    const id = window.setTimeout(() => {
      saveBrowseQueryToStorage(browseQuery);
      syncBrowseQueryToUrl(browseQuery);
    }, 400);
    return () => clearTimeout(id);
  }, [browseQuery]);

  useEffect(() => {
    const flush = () => {
      saveBrowseQueryToStorage(browseQueryRef.current);
      syncBrowseQueryToUrl(browseQueryRef.current);
    };
    window.addEventListener("pagehide", flush);
    return () => window.removeEventListener("pagehide", flush);
  }, []);

  const resetBrowseUi = useCallback(() => {
    setSortFilterOpen(false);
    setSelectionMode(false);
    setSelectedIds(new Set());
    setBulkDeleteImpact(null);
  }, []);

  const stores = useMemo(
    () => [...new Set(products.map((p) => p.location.store))].sort(),
    [products],
  );

  const categories = useMemo(
    () => [...new Set(products.map((p) => p.category).filter(Boolean))].sort(),
    [products],
  );

  const priceExtentsForChips = useMemo(
    () => getPriceExtents(productsForPriceHistogram(products, browseQuery, browseSearch)),
    [products, browseQuery, browseSearch],
  );

  const browseDisplayed = useMemo(() => {
    const extents = getPriceExtents(products);
    const filtered = filterProducts(products, browseQuery, browseSearch, { extents });
    return sortProducts(filtered, browseQuery.sort);
  }, [products, browseQuery, browseSearch]);

  const activeChipCount = useMemo(
    () => countActiveChips(browseQuery, priceExtentsForChips),
    [browseQuery, priceExtentsForChips],
  );

  const navigateToProduct = useCallback(
    (productId: string) => {
      const target = products.find((product) => product.id === productId);
      if (!target) return;

      const visible = filterProducts(products, browseQuery, browseSearch, {
        extents: getPriceExtents(products),
      }).some((product) => product.id === productId);

      if (!visible) {
        setBrowseSearch("");
        setBrowseQuery({ ...EMPTY_BROWSE_QUERY, viewMode: "products" });
      } else if (browseQuery.viewMode === "photos") {
        setBrowseQuery({ ...browseQuery, viewMode: "products" });
      }

      window.setTimeout(() => {
        document.getElementById(`product-${productId}`)?.scrollIntoView({
          behavior: "smooth",
          block: "center",
        });
        setHighlightProductId(productId);
        window.setTimeout(() => setHighlightProductId(null), 2000);
      }, visible ? 0 : 50);
    },
    [products, browseQuery, browseSearch],
  );

  const navigateToPhotoGroup = useCallback(
    (imageId: string, productId: string) => {
      const visible = filterProducts(products, browseQuery, browseSearch, {
        extents: getPriceExtents(products),
      }).some((product) => product.image_id === imageId);

      if (!visible) {
        setBrowseSearch("");
        setBrowseQuery({ ...EMPTY_BROWSE_QUERY, viewMode: "photos" });
      } else if (browseQuery.viewMode !== "photos") {
        setBrowseQuery({ ...browseQuery, viewMode: "photos" });
      }

      window.setTimeout(() => {
        document.getElementById(`photo-${imageId}`)?.scrollIntoView({
          behavior: "smooth",
          block: "center",
        });
        setHighlightPhotoGroupId(imageId);
        setHighlightProductId(productId);
        window.setTimeout(() => {
          setHighlightPhotoGroupId(null);
          setHighlightProductId(null);
        }, 2000);
      }, visible ? 0 : 50);
    },
    [products, browseQuery, browseSearch],
  );

  const photoGroupSizes = useMemo(() => {
    const counts = new Map<string, number>();
    for (const product of products) {
      counts.set(product.image_id, (counts.get(product.image_id) ?? 0) + 1);
    }
    return counts;
  }, [products]);

  const productsById = useMemo(
    () => new Map(products.map((product) => [product.id, product])),
    [products],
  );

  const browseStats = useMemo((): BrowseStats => {
    const priced = browseDisplayed.filter((p) => p.price != null);
    const avgPrice =
      priced.length > 0
        ? priced.reduce((s, p) => s + (p.price ?? 0), 0) / priced.length
        : 0;

    return {
      shown: browseDisplayed.length,
      total: products.length,
      photoCount: new Set(products.map((p) => p.image_id)).size,
      storeCount: stores.length,
      avgPriceLabel: priced.length > 0 ? formatPrice(avgPrice) : "—",
    };
  }, [browseDisplayed, products, stores.length]);

  const finishOnboarding = useCallback(async () => {
    setShowOnboarding(false);
    try {
      await completeOnboarding();
      await refreshAuth();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not save onboarding status");
    }
  }, [refreshAuth]);

  const handleEditProduct = useCallback(async (productId: string, updates: ProductUpdateInput) => {
    setSavingId(productId);
    setError(null);
    try {
      const updated = await updateProduct(productId, updates);
      setProducts((rows) => rows.map((row) => (row.id === productId ? updated : row)));
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not save product");
      throw err;
    } finally {
      setSavingId(null);
    }
  }, []);

  const handleReextractPhoto = useCallback(
    async (imageId: string) => {
      setReextractingId(imageId);
      setReextractStartedAt(Date.now());
      setError(null);
      try {
        await reextractPhoto(imageId);
        await refreshProducts({ silent: true });
      } catch (err) {
        setError(err instanceof Error ? err.message : "Re-extract failed");
      } finally {
        setReextractingId(null);
        setReextractStartedAt(null);
      }
    },
    [refreshProducts],
  );

  const handleAddManualProduct = useCallback(
    async (imageId: string, product: ManualProductInput) => {
      setSavingId(`${imageId}-empty`);
      setError(null);
      try {
        await addManualProduct(imageId, product);
        await refreshProducts({ silent: true });
      } catch (err) {
        setError(err instanceof Error ? err.message : "Could not add product");
        throw err;
      } finally {
        setSavingId(null);
      }
    },
    [refreshProducts],
  );

  const handleDeleteProducts = useCallback(
    async (productIds: string[]) => {
      if (productIds.length === 0) return;

      const fromModal = bulkDeleteImpact !== null;
      setBulkDeleting(true);
      setError(null);
      const idSet = new Set(productIds);
      const previous = products;
      setProducts((rows) => rows.filter((p) => !idSet.has(p.id)));
      if (!fromModal) {
        setSelectedIds(new Set());
        setSelectionMode(false);
      }

      try {
        if (productIds.length === 1) {
          await deleteProduct(productIds[0]);
        } else {
          const result = await deleteProductsBulk(productIds);
          if (result.failed.length > 0) {
            await refreshProducts({ silent: true });
            throw new Error(
              `${result.deleted} deleted, ${result.failed.length} failed. Catalog refreshed.`,
            );
          }
        }
        await refreshAuth();
        await refreshProducts({ silent: true });
      } catch (err) {
        if (productIds.length > 1) {
          await refreshProducts({ silent: true });
        } else {
          setProducts(previous);
        }
        setError(err instanceof Error ? err.message : "Delete failed");
      } finally {
        setBulkDeleting(false);
        setBulkDeleteImpact(null);
        if (fromModal) {
          setSelectionMode(false);
          setSelectedIds(new Set());
        }
        setDeletingId(null);
      }
    },
    [bulkDeleteImpact, products, refreshAuth, refreshProducts],
  );

  const handleDeleteProduct = useCallback(
    (productId: string) => {
      setDeletingId(productId);
      void handleDeleteProducts([productId]);
    },
    [handleDeleteProducts],
  );

  const handleDeletePhoto = useCallback(
    async (imageId: string) => {
      setDeletingPhotoId(imageId);
      setError(null);
      const previous = products;
      setProducts((rows) => rows.filter((product) => product.image_id !== imageId));

      try {
        await deletePhoto(imageId);
        await refreshAuth();
        await refreshProducts({ silent: true });
      } catch (err) {
        setProducts(previous);
        setError(err instanceof Error ? err.message : "Delete failed");
      } finally {
        setDeletingPhotoId(null);
      }
    },
    [products, refreshAuth, refreshProducts],
  );

  const toggleProductSelection = useCallback((productId: string) => {
    setSelectedIds((prev) => {
      const next = new Set(prev);
      if (next.has(productId)) {
        next.delete(productId);
      } else {
        next.add(productId);
      }
      return next;
    });
  }, []);

  const requestBulkDelete = useCallback(
    (ids: string[]) => {
      const impact = computeBulkDeleteImpact(products, new Set(ids));
      if (impact.validIds.length === 0) return;
      setSortFilterOpen(false);
      setBulkDeleteImpact(impact);
    },
    [products],
  );

  const confirmBulkDelete = useCallback(() => {
    if (!bulkDeleteImpact || bulkDeleting) return;
    void handleDeleteProducts(bulkDeleteImpact.validIds);
  }, [bulkDeleteImpact, bulkDeleting, handleDeleteProducts]);

  const cancelBulkDelete = useCallback(() => {
    if (bulkDeleting) return;
    setBulkDeleteImpact(null);
  }, [bulkDeleting]);

  const value = useMemo(
    (): CatalogContextValue => ({
      products,
      productsLoading,
      error,
      setError,
      showOnboarding,
      setShowOnboarding,
      finishOnboarding,
      refreshProducts,
      handleUploadSuccess,
      browseSearch,
      setBrowseSearch,
      browseQuery,
      setBrowseQuery,
      sortFilterOpen,
      setSortFilterOpen,
      activeChipCount,
      priceExtentsForChips,
      stores,
      categories,
      browseDisplayed,
      browseStats,
      photoGroupSizes,
      multiProductTipImageId,
      productsById,
      navigateToProduct,
      navigateToPhotoGroup,
      highlightProductId,
      highlightPhotoGroupId,
      deletingId,
      deletingPhotoId,
      savingId,
      reextractingId,
      reextractStartedAt,
      handleDeleteProduct,
      handleDeletePhoto,
      handleEditProduct,
      handleReextractPhoto,
      handleAddManualProduct,
      selectionMode,
      setSelectionMode,
      selectedIds,
      setSelectedIds,
      toggleProductSelection,
      requestBulkDelete,
      confirmBulkDelete,
      cancelBulkDelete,
      bulkDeleteImpact,
      bulkDeleting,
      resetBrowseUi,
    }),
    [
      products,
      productsLoading,
      error,
      showOnboarding,
      finishOnboarding,
      refreshProducts,
      handleUploadSuccess,
      browseSearch,
      browseQuery,
      sortFilterOpen,
      activeChipCount,
      priceExtentsForChips,
      stores,
      categories,
      browseDisplayed,
      browseStats,
      photoGroupSizes,
      multiProductTipImageId,
      productsById,
      navigateToProduct,
      navigateToPhotoGroup,
      highlightProductId,
      highlightPhotoGroupId,
      deletingId,
      deletingPhotoId,
      savingId,
      reextractingId,
      reextractStartedAt,
      handleDeleteProduct,
      handleDeletePhoto,
      handleEditProduct,
      handleReextractPhoto,
      handleAddManualProduct,
      selectionMode,
      selectedIds,
      toggleProductSelection,
      requestBulkDelete,
      confirmBulkDelete,
      cancelBulkDelete,
      bulkDeleteImpact,
      bulkDeleting,
      resetBrowseUi,
    ],
  );

  return <CatalogContext.Provider value={value}>{children}</CatalogContext.Provider>;
}
