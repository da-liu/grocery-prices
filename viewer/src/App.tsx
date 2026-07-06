import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { AuthProvider, useAuth } from "./AuthContext";
import { fetchProducts, deleteProduct, deleteProductsBulk, completeOnboarding, productImageUrl, updateProduct, addManualProduct, reextractPhoto } from "./api";
import { BrowsePage } from "./BrowsePage";
import { BrowseQueryChips } from "./BrowseQueryChips";
import { BrowseSelectionBar } from "./BrowseSelectionBar";
import { BrowseSortFilterPanel } from "./BrowseSortFilterPanel";
import { BulkDeleteConfirmModal } from "./BulkDeleteConfirmModal";
import { computeBulkDeleteImpact } from "./bulkDelete";
import {
  EMPTY_BROWSE_QUERY,
  filterProducts,
  getPriceExtents,
  loadBrowseQueryFromStorage,
  mergeBrowseQuery,
  parseBrowseQueryFromSearch,
  productsForPriceHistogram,
  saveBrowseQueryToStorage,
  sortProducts,
  syncBrowseQueryToUrl,
  countActiveChips,
  type BrowseQueryState,
} from "./browseQuery";
import { ComparePage, hasComparableProducts } from "./ComparePage";
import { CompressPage } from "./CompressPage";
import { MetadataPage } from "./MetadataPage";
import { OnboardingGuide } from "./OnboardingGuide";
import { SettingsPage } from "./SettingsPage";
import { AuthLoadingScreen } from "./AuthLoadingScreen";
import { SignInPage } from "./SignInPage";
import { StoreLabelModal } from "./StoreLabelModal";
import { TopBar } from "./TopBar";
import { AppHeader } from "./AppHeader";
import { UploadQueueProvider, useUploadQueueActions } from "./UploadQueueContext";
import { UploadStatusPanel, UploadStatusToasts } from "./UploadStatusBar";
import type { Product } from "./types";
import type { ManualProductInput, ProductUpdateInput } from "./api";
import "./App.css";

type Page = "browse" | "compare" | "settings" | "metadata" | "compress";

function pageFromHash(): Page {
  const hash = window.location.hash.replace(/^#\/?/, "");
  if (hash === "compare" || hash === "settings" || hash === "metadata" || hash === "compress") {
    return hash;
  }
  if (hash === "exif") return "metadata";
  return "browse";
}

function formatPrice(price: number) {
  return new Intl.NumberFormat("en-CA", {
    style: "currency",
    currency: "CAD",
  }).format(price);
}

function initialBrowseQuery(): BrowseQueryState {
  const fromStorage = loadBrowseQueryFromStorage() ?? {};
  const fromUrl = parseBrowseQueryFromSearch(window.location.search);
  return mergeBrowseQuery(EMPTY_BROWSE_QUERY, { ...fromStorage, ...fromUrl });
}

function AppShell() {
  const { user, loading: authLoading, logout, refresh } = useAuth();
  const [page, setPage] = useState<Page>(pageFromHash);
  const [products, setProducts] = useState<Product[]>([]);
  const [productsLoading, setProductsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [showOnboarding, setShowOnboarding] = useState(false);
  const [browseSearch, setBrowseSearch] = useState("");
  const [browseQuery, setBrowseQuery] = useState<BrowseQueryState>(initialBrowseQuery);
  const [sortFilterOpen, setSortFilterOpen] = useState(false);
  const [compareQuery, setCompareQuery] = useState("");
  const [deletingId, setDeletingId] = useState<string | null>(null);
  const [savingId, setSavingId] = useState<string | null>(null);
  const [reextractingId, setReextractingId] = useState<string | null>(null);
  const [selectionMode, setSelectionMode] = useState(false);
  const [selectedIds, setSelectedIds] = useState<Set<string>>(new Set());
  const [bulkDeletePending, setBulkDeletePending] = useState<string[] | null>(null);
  const [bulkDeleting, setBulkDeleting] = useState(false);
  const [highlightProductId, setHighlightProductId] = useState<string | null>(null);
  const [highlightPhotoGroupId, setHighlightPhotoGroupId] = useState<string | null>(null);

  const refreshProducts = useCallback((options?: { silent?: boolean }) => {
    if (!user) return Promise.resolve();
    if (!options?.silent) setProductsLoading(true);
    setError(null);
    return fetchProducts()
      .then((rows) => {
        setProducts(rows);
      })
      .catch((e: Error) => setError(e.message))
      .finally(() => setProductsLoading(false));
  }, [user]);

  const handleUploadSuccess = useCallback(async () => {
    await refresh();
    await refreshProducts({ silent: true });
    setShowOnboarding(false);
  }, [refresh, refreshProducts]);

  useEffect(() => {
    if (user) {
      refreshProducts();
      if (user.needs_onboarding) {
        setShowOnboarding(true);
      }
    } else {
      setProducts([]);
    }
  }, [user, refreshProducts]);

  useEffect(() => {
    const onHash = () => setPage(pageFromHash());
    window.addEventListener("hashchange", onHash);
    return () => window.removeEventListener("hashchange", onHash);
  }, []);

  useEffect(() => {
    saveBrowseQueryToStorage(browseQuery);
    syncBrowseQueryToUrl(browseQuery);
  }, [browseQuery]);

  function navigate(next: Page) {
    window.location.hash = next === "browse" ? "" : `#/${next}`;
    setPage(next);
    setSortFilterOpen(false);
    if (next !== "browse") {
      setSelectionMode(false);
      setSelectedIds(new Set());
      setBulkDeletePending(null);
    }
  }

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

  const compareAvailable = useMemo(() => hasComparableProducts(products), [products]);

  const browseStats = useMemo(() => {
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

  async function finishOnboarding() {
    setShowOnboarding(false);
    try {
      await completeOnboarding();
      await refresh();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not save onboarding status");
    }
  }

  async function handleEditProduct(productId: string, updates: ProductUpdateInput) {
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
  }

  async function handleReextractPhoto(imageId: string) {
    setReextractingId(imageId);
    setError(null);
    try {
      await reextractPhoto(imageId);
      await refreshProducts({ silent: true });
    } catch (err) {
      setError(err instanceof Error ? err.message : "Re-extract failed");
    } finally {
      setReextractingId(null);
    }
  }

  async function handleAddManualProduct(imageId: string, product: ManualProductInput) {
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
  }

  async function handleDeleteProduct(productId: string) {
    setDeletingId(productId);
    await handleDeleteProducts([productId]);
  }

  async function handleDeleteProducts(productIds: string[]) {
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
      await refresh();
      await refreshProducts({ silent: true });
    } catch (err) {
      setProducts(previous);
      setError(err instanceof Error ? err.message : "Delete failed");
    } finally {
      setBulkDeleting(false);
      setDeletingId(null);
    }
  }

  function toggleProductSelection(productId: string) {
    setSelectedIds((prev) => {
      const next = new Set(prev);
      if (next.has(productId)) {
        next.delete(productId);
      } else {
        next.add(productId);
      }
      return next;
    });
  }

  function requestBulkDelete(ids: string[]) {
    if (ids.length === 0) return;
    setSortFilterOpen(false);
    setBulkDeletePending(ids);
  }

  const bulkDeleteImpact = useMemo(() => {
    if (!bulkDeletePending) return null;
    return computeBulkDeleteImpact(products, new Set(bulkDeletePending));
  }, [bulkDeletePending, products]);

  if (authLoading) {
    return <AuthLoadingScreen />;
  }

  if (!user) {
    return <SignInPage />;
  }

  return (
    <UploadQueueProvider onUploadSuccess={handleUploadSuccess}>
      <AuthenticatedApp
        page={page}
        navigate={navigate}
        user={user}
        logout={logout}
        browseSearch={browseSearch}
        setBrowseSearch={setBrowseSearch}
        browseQuery={browseQuery}
        setBrowseQuery={setBrowseQuery}
        sortFilterOpen={sortFilterOpen}
        setSortFilterOpen={setSortFilterOpen}
        activeChipCount={activeChipCount}
        priceExtentsForChips={priceExtentsForChips}
        compareQuery={compareQuery}
        setCompareQuery={setCompareQuery}
        products={products}
        productsLoading={productsLoading}
        stores={stores}
        categories={categories}
        browseDisplayed={browseDisplayed}
        browseStats={browseStats}
        error={error}
        setError={setError}
        deletingId={deletingId}
        handleDeleteProduct={handleDeleteProduct}
        handleEditProduct={handleEditProduct}
        handleReextractPhoto={handleReextractPhoto}
        handleAddManualProduct={handleAddManualProduct}
        savingId={savingId}
        reextractingId={reextractingId}
        showOnboarding={showOnboarding}
        setShowOnboarding={setShowOnboarding}
        finishOnboarding={finishOnboarding}
        selectionMode={selectionMode}
        setSelectionMode={setSelectionMode}
        selectedIds={selectedIds}
        setSelectedIds={setSelectedIds}
        toggleProductSelection={toggleProductSelection}
        requestBulkDelete={requestBulkDelete}
        bulkDeletePending={bulkDeletePending}
        setBulkDeletePending={setBulkDeletePending}
        bulkDeleteImpact={bulkDeleteImpact}
        bulkDeleting={bulkDeleting}
        handleDeleteProducts={handleDeleteProducts}
        navigateToProduct={navigateToProduct}
        navigateToPhotoGroup={navigateToPhotoGroup}
        highlightProductId={highlightProductId}
        highlightPhotoGroupId={highlightPhotoGroupId}
        photoGroupSizes={photoGroupSizes}
        compareAvailable={compareAvailable}
      />
    </UploadQueueProvider>
  );
}

function AuthenticatedApp({
  page,
  navigate,
  user,
  logout,
  browseSearch,
  setBrowseSearch,
  browseQuery,
  setBrowseQuery,
  sortFilterOpen,
  setSortFilterOpen,
  activeChipCount,
  priceExtentsForChips,
  compareQuery,
  setCompareQuery,
  products,
  productsLoading,
  stores,
  categories,
  browseDisplayed,
  browseStats,
  error,
  setError,
  deletingId,
  handleDeleteProduct,
  handleEditProduct,
  handleReextractPhoto,
  handleAddManualProduct,
  savingId,
  reextractingId,
  showOnboarding,
  setShowOnboarding,
  finishOnboarding,
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
  handleDeleteProducts,
  navigateToProduct,
  navigateToPhotoGroup,
  highlightProductId,
  highlightPhotoGroupId,
  photoGroupSizes,
  compareAvailable,
}: {
  page: Page;
  navigate: (next: Page) => void;
  user: { username: string; needs_onboarding: boolean };
  logout: () => Promise<void>;
  browseSearch: string;
  setBrowseSearch: (v: string) => void;
  browseQuery: BrowseQueryState;
  setBrowseQuery: (v: BrowseQueryState) => void;
  sortFilterOpen: boolean;
  setSortFilterOpen: (v: boolean) => void;
  activeChipCount: number;
  priceExtentsForChips: ReturnType<typeof getPriceExtents>;
  compareQuery: string;
  setCompareQuery: (v: string) => void;
  products: Product[];
  productsLoading: boolean;
  stores: string[];
  categories: string[];
  browseDisplayed: Product[];
  browseStats: {
    shown: number;
    total: number;
    photoCount: number;
    storeCount: number;
    avgPriceLabel: string;
  };
  error: string | null;
  setError: (v: string | null) => void;
  deletingId: string | null;
  handleDeleteProduct: (id: string) => void;
  handleEditProduct: (productId: string, updates: ProductUpdateInput) => Promise<void>;
  handleReextractPhoto: (imageId: string) => Promise<void>;
  handleAddManualProduct: (imageId: string, product: ManualProductInput) => Promise<void>;
  savingId: string | null;
  reextractingId: string | null;
  showOnboarding: boolean;
  setShowOnboarding: (v: boolean) => void;
  finishOnboarding: () => Promise<void>;
  selectionMode: boolean;
  setSelectionMode: (v: boolean) => void;
  selectedIds: Set<string>;
  setSelectedIds: (v: Set<string>) => void;
  toggleProductSelection: (productId: string) => void;
  requestBulkDelete: (ids: string[]) => void;
  bulkDeletePending: string[] | null;
  setBulkDeletePending: (v: string[] | null) => void;
  bulkDeleteImpact: { productCount: number; photosRemoved: number } | null;
  bulkDeleting: boolean;
  handleDeleteProducts: (ids: string[]) => Promise<void>;
  navigateToProduct: (productId: string) => void;
  navigateToPhotoGroup: (imageId: string, productId: string) => void;
  highlightProductId: string | null;
  highlightPhotoGroupId: string | null;
  photoGroupSizes: Map<string, number>;
  compareAvailable: boolean;
}) {
  const { enqueueFiles, pendingLabel, requestLabel, dismissLabel, completeLabel } =
    useUploadQueueActions();
  const photoInputRef = useRef<HTMLInputElement>(null);

  function openPhotoPicker() {
    photoInputRef.current?.click();
  }

  const labelRequest = pendingLabel;

  const searchProps =
    page === "compare"
      ? {
          search: compareQuery,
          onSearchChange: setCompareQuery,
          searchPlaceholder: "Search comparisons…",
        }
      : {
          search: browseSearch,
          onSearchChange: setBrowseSearch,
          searchPlaceholder: "Search products, brands, barcodes…",
        };

  return (
    <div className="app">
      <AppHeader>
        <TopBar
          page={page}
          {...searchProps}
          user={user}
          onLogout={() => void logout()}
          onNavigate={navigate}
          photoInputRef={photoInputRef}
          onPhotosSelected={(files) => enqueueFiles(files, "shelf")}
          showSortFilter={page === "browse"}
          sortFilterOpen={sortFilterOpen}
          activeChipCount={activeChipCount}
          onToggleSortFilter={() => setSortFilterOpen(!sortFilterOpen)}
          browseStats={products.length > 0 ? browseStats : undefined}
          showCompareNav={compareAvailable}
          onShowOnboarding={() => setShowOnboarding(true)}
        />
        <UploadStatusPanel />
      </AppHeader>

      <UploadStatusToasts />

      {page === "browse" && !selectionMode && (
        <BrowseQueryChips
          query={browseQuery}
          extents={priceExtentsForChips}
          onChange={setBrowseQuery}
        />
      )}

      {page === "browse" && selectionMode && (
        <BrowseSelectionBar
          selectedCount={selectedIds.size}
          shownCount={browseDisplayed.length}
          allShownSelected={
            browseDisplayed.length > 0 &&
            browseDisplayed.every((product) => selectedIds.has(product.id))
          }
          deleting={bulkDeleting}
          onSelectAllShown={() =>
            setSelectedIds(new Set(browseDisplayed.map((product) => product.id)))
          }
          onDeleteSelected={() => requestBulkDelete([...selectedIds])}
          onCancel={() => {
            setSelectionMode(false);
            setSelectedIds(new Set());
          }}
        />
      )}

      {error && (
        <p className="status error app-error">
          {error}
          <button type="button" className="app-error-dismiss" onClick={() => setError(null)}>
            Dismiss
          </button>
        </p>
      )}
      {productsLoading && (
        <p className="status">Loading products…</p>
      )}

      {page === "browse" && (products.length > 0 || !productsLoading) && (
        <BrowsePage
          products={browseDisplayed}
          catalogEmpty={products.length === 0}
          viewMode={browseQuery.viewMode}
          onStartUpload={openPhotoPicker}
          onDeleteProduct={(id) => void handleDeleteProduct(id)}
          deletingId={deletingId}
          onEditProduct={handleEditProduct}
          onReextractPhoto={handleReextractPhoto}
          onAddManualProduct={handleAddManualProduct}
          savingId={savingId}
          reextractingId={reextractingId}
          selectionMode={selectionMode}
          selectedIds={selectedIds}
          onToggleSelect={toggleProductSelection}
          gridColumns={browseQuery.gridColumns}
          onNavigateToProduct={navigateToProduct}
          onNavigateToPhotoGroup={selectionMode ? undefined : navigateToPhotoGroup}
          photoGroupSizes={photoGroupSizes}
          highlightProductId={highlightProductId}
          highlightPhotoGroupId={highlightPhotoGroupId}
          onLabelLocation={(product) => {
            const { latitude, longitude } = product.location;
            requestLabel({
              imageId: product.image_id,
              thumbnailUrl: productImageUrl(product.image_id),
              latitude: latitude ?? null,
              longitude: longitude ?? null,
            });
          }}
        />
      )}
      {page === "settings" && <SettingsPage />}
      {page === "metadata" && <MetadataPage />}
      {page === "compress" && <CompressPage />}
      {page === "compare" && (products.length > 0 || !productsLoading) && (
        <ComparePage
          products={products}
          query={compareQuery}
          onDeleteProduct={(id) => void handleDeleteProduct(id)}
          deletingId={deletingId}
        />
      )}

      {page === "browse" && (
        <BrowseSortFilterPanel
          open={sortFilterOpen}
          query={browseQuery}
          onChange={setBrowseQuery}
          onClose={() => setSortFilterOpen(false)}
          products={products}
          search={browseSearch}
          stores={stores}
          categories={categories}
          stats={{
            shown: browseStats.shown,
            total: browseStats.total,
            avgPriceLabel: browseStats.avgPriceLabel,
          }}
          selectionMode={selectionMode}
          onEnterSelection={() => setSelectionMode(true)}
          onExitSelection={() => {
            setSelectionMode(false);
            setSelectedIds(new Set());
          }}
          onDeleteAllProducts={
            products.length > 0
              ? () => void handleDeleteProducts(products.map((product) => product.id))
              : undefined
          }
          deletingAll={bulkDeleting}
        />
      )}

      {bulkDeletePending && bulkDeleteImpact && (
        <BulkDeleteConfirmModal
          productCount={bulkDeleteImpact.productCount}
          photosRemoved={bulkDeleteImpact.photosRemoved}
          deleting={bulkDeleting}
          onCancel={() => setBulkDeletePending(null)}
          onConfirm={() => void handleDeleteProducts(bulkDeletePending)}
        />
      )}

      {showOnboarding && (
        <OnboardingGuide
          onStartUpload={() => {
            void finishOnboarding();
            openPhotoPicker();
          }}
          onDismiss={() => void finishOnboarding()}
        />
      )}

      {labelRequest && (
        <StoreLabelModal
          request={labelRequest}
          onDone={() => completeLabel()}
          onDismiss={() => dismissLabel()}
        />
      )}
    </div>
  );
}

export default function App() {
  return (
    <AuthProvider>
      <AppShell />
    </AuthProvider>
  );
}
