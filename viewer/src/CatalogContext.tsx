import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useState,
  type ReactNode,
} from "react";
import {
  addManualProduct,
  completeOnboarding,
  deleteProduct,
  deleteProductsBulk,
  fetchProducts,
  fetchSettings,
  reextractPhoto,
  updateProduct,
  type ExtractBackend,
  type ManualProductInput,
  type ProductUpdateInput,
} from "./api";
import {
  EMPTY_BROWSE_QUERY,
  countActiveChips,
  filterProducts,
  getPriceExtents,
  loadBrowseQueryFromStorage,
  mergeBrowseQuery,
  parseBrowseQueryFromSearch,
  productsForPriceHistogram,
  saveBrowseQueryToStorage,
  sortProducts,
  syncBrowseQueryToUrl,
  type BrowseQueryState,
} from "./browseQuery";
import { computeBulkDeleteImpact } from "./bulkDelete";
import { formatPrice } from "./formatPrice";
import type { BrowseStats, Product } from "./types";

function initialBrowseQuery(): BrowseQueryState {
  const fromStorage = loadBrowseQueryFromStorage() ?? {};
  const fromUrl = parseBrowseQueryFromSearch(window.location.search);
  return mergeBrowseQuery(EMPTY_BROWSE_QUERY, { ...fromStorage, ...fromUrl });
}

interface CatalogContextValue {
  products: Product[];
  productsLoading: boolean;
  error: string | null;
  setError: (error: string | null) => void;
  extractBackend: ExtractBackend;
  showOnboarding: boolean;
  setShowOnboarding: (show: boolean) => void;
  finishOnboarding: () => Promise<void>;
  refreshProducts: (options?: { silent?: boolean }) => Promise<void>;
  handleUploadSuccess: () => Promise<void>;
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
  navigateToProduct: (productId: string) => void;
  navigateToPhotoGroup: (imageId: string, productId: string) => void;
  highlightProductId: string | null;
  highlightPhotoGroupId: string | null;
  deletingId: string | null;
  savingId: string | null;
  reextractingId: string | null;
  reextractStartedAt: number | null;
  handleDeleteProduct: (productId: string) => void;
  handleDeleteProducts: (productIds: string[]) => Promise<void>;
  handleEditProduct: (productId: string, updates: ProductUpdateInput) => Promise<void>;
  handleReextractPhoto: (imageId: string) => Promise<void>;
  handleAddManualProduct: (imageId: string, product: ManualProductInput) => Promise<void>;
  selectionMode: boolean;
  setSelectionMode: (mode: boolean) => void;
  selectedIds: Set<string>;
  setSelectedIds: (ids: Set<string>) => void;
  toggleProductSelection: (productId: string) => void;
  requestBulkDelete: (ids: string[]) => void;
  bulkDeletePending: string[] | null;
  setBulkDeletePending: (ids: string[] | null) => void;
  bulkDeleteImpact: { productCount: number; photosRemoved: number } | null;
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
  user: { needs_onboarding: boolean } | null;
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
  const [savingId, setSavingId] = useState<string | null>(null);
  const [reextractingId, setReextractingId] = useState<string | null>(null);
  const [reextractStartedAt, setReextractStartedAt] = useState<number | null>(null);
  const [extractBackend, setExtractBackend] = useState<ExtractBackend>("cursor");
  const [selectionMode, setSelectionMode] = useState(false);
  const [selectedIds, setSelectedIds] = useState<Set<string>>(new Set());
  const [bulkDeletePending, setBulkDeletePending] = useState<string[] | null>(null);
  const [bulkDeleting, setBulkDeleting] = useState(false);
  const [highlightProductId, setHighlightProductId] = useState<string | null>(null);
  const [highlightPhotoGroupId, setHighlightPhotoGroupId] = useState<string | null>(null);

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

  const handleUploadSuccess = useCallback(async () => {
    await refreshAuth();
    await refreshProducts({ silent: true });
    setShowOnboarding(false);
  }, [refreshAuth, refreshProducts]);

  useEffect(() => {
    if (user) {
      refreshProducts();
      if (user.needs_onboarding) {
        setShowOnboarding(true);
      }
      fetchSettings()
        .then((settings) => setExtractBackend(settings.extract_backend))
        .catch(() => {});
    } else {
      setProducts([]);
    }
  }, [user, refreshProducts]);

  useEffect(() => {
    saveBrowseQueryToStorage(browseQuery);
    syncBrowseQueryToUrl(browseQuery);
  }, [browseQuery]);

  const resetBrowseUi = useCallback(() => {
    setSortFilterOpen(false);
    setSelectionMode(false);
    setSelectedIds(new Set());
    setBulkDeletePending(null);
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

      setBulkDeleting(true);
      setError(null);
      const idSet = new Set(productIds);
      const previous = products;
      setProducts((rows) => rows.filter((p) => !idSet.has(p.id)));
      setSelectedIds(new Set());
      setSelectionMode(false);
      setBulkDeletePending(null);

      try {
        if (productIds.length === 1) {
          await deleteProduct(productIds[0]);
        } else {
          const result = await deleteProductsBulk(productIds);
          if (result.failed.length > 0) {
            throw new Error(`${result.failed.length} of ${productIds.length} deletes failed`);
          }
        }
        await refreshAuth();
        await refreshProducts({ silent: true });
      } catch (err) {
        setProducts(previous);
        setError(err instanceof Error ? err.message : "Delete failed");
      } finally {
        setBulkDeleting(false);
        setDeletingId(null);
      }
    },
    [products, refreshAuth, refreshProducts],
  );

  const handleDeleteProduct = useCallback(
    (productId: string) => {
      setDeletingId(productId);
      void handleDeleteProducts([productId]);
    },
    [handleDeleteProducts],
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

  const requestBulkDelete = useCallback((ids: string[]) => {
    if (ids.length === 0) return;
    setSortFilterOpen(false);
    setBulkDeletePending(ids);
  }, []);

  const bulkDeleteImpact = useMemo(() => {
    if (!bulkDeletePending) return null;
    return computeBulkDeleteImpact(products, new Set(bulkDeletePending));
  }, [bulkDeletePending, products]);

  const value = useMemo(
    (): CatalogContextValue => ({
      products,
      productsLoading,
      error,
      setError,
      extractBackend,
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
      navigateToProduct,
      navigateToPhotoGroup,
      highlightProductId,
      highlightPhotoGroupId,
      deletingId,
      savingId,
      reextractingId,
      reextractStartedAt,
      handleDeleteProduct,
      handleDeleteProducts,
      handleEditProduct,
      handleReextractPhoto,
      handleAddManualProduct,
      selectionMode,
      setSelectionMode,
      selectedIds,
      setSelectedIds,
      toggleProductSelection,
      requestBulkDelete,
      bulkDeletePending,
      setBulkDeletePending,
      bulkDeleteImpact,
      bulkDeleting,
      resetBrowseUi,
    }),
    [
      products,
      productsLoading,
      error,
      extractBackend,
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
      navigateToProduct,
      navigateToPhotoGroup,
      highlightProductId,
      highlightPhotoGroupId,
      deletingId,
      savingId,
      reextractingId,
      reextractStartedAt,
      handleDeleteProduct,
      handleDeleteProducts,
      handleEditProduct,
      handleReextractPhoto,
      handleAddManualProduct,
      selectionMode,
      selectedIds,
      toggleProductSelection,
      requestBulkDelete,
      bulkDeletePending,
      bulkDeleteImpact,
      bulkDeleting,
      resetBrowseUi,
    ],
  );

  return <CatalogContext.Provider value={value}>{children}</CatalogContext.Provider>;
}
