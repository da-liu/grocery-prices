import { useCallback, useEffect, useMemo, useState } from "react";
import { AuthProvider, useAuth } from "./AuthContext";
import { fetchProducts, deleteProduct, completeOnboarding, productImageUrl } from "./api";
import { BrowsePage } from "./BrowsePage";
import { ComparePage } from "./ComparePage";
import { OnboardingGuide } from "./OnboardingGuide";
import { SettingsPage } from "./SettingsPage";
import { SignInPage } from "./SignInPage";
import { StoreLabelModal } from "./StoreLabelModal";
import { TopBar } from "./TopBar";
import { UploadPage } from "./UploadPage";
import { UploadQueueProvider, useUploadQueue } from "./UploadQueueContext";
import { UploadStatusBar } from "./UploadStatusBar";
import type { Product } from "./types";
import "./App.css";

type Page = "browse" | "upload" | "compare" | "settings";

function pageFromHash(): Page {
  const hash = window.location.hash.replace(/^#\/?/, "");
  if (hash === "upload" || hash === "compare" || hash === "settings") return hash;
  return "browse";
}

function formatPrice(price: number) {
  return new Intl.NumberFormat("en-CA", {
    style: "currency",
    currency: "CAD",
  }).format(price);
}

function AppShell() {
  const { user, loading: authLoading, logout, refresh } = useAuth();
  const [page, setPage] = useState<Page>(pageFromHash);
  const [products, setProducts] = useState<Product[]>([]);
  const [productsLoading, setProductsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [showOnboarding, setShowOnboarding] = useState(false);
  const [browseSearch, setBrowseSearch] = useState("");
  const [browseStore, setBrowseStore] = useState("all");
  const [compareQuery, setCompareQuery] = useState("");
  const [deletingId, setDeletingId] = useState<string | null>(null);

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

  function navigate(next: Page) {
    window.location.hash = next === "browse" ? "" : `#/${next}`;
    setPage(next);
  }

  const stores = useMemo(
    () => [...new Set(products.map((p) => p.location.store))].sort(),
    [products],
  );

  const browseStats = useMemo(() => {
    const q = browseSearch.trim().toLowerCase();
    const filtered = products.filter((p) => {
      if (browseStore !== "all" && p.location.store !== browseStore) return false;
      if (!q) return true;
      const hay = [
        p.product_name,
        p.product_name_zh,
        p.brand,
        p.location.store,
        p.category,
        p.barcode,
      ]
        .filter(Boolean)
        .join(" ")
        .toLowerCase();
      return hay.includes(q);
    });
    const priced = filtered.filter((p) => p.price != null);
    const avgPrice =
      priced.length > 0
        ? priced.reduce((s, p) => s + (p.price ?? 0), 0) / priced.length
        : 0;

    return {
      shown: filtered.length,
      total: products.length,
      photoCount: new Set(products.map((p) => p.image_id)).size,
      storeCount: stores.length,
      avgPriceLabel: priced.length > 0 ? formatPrice(avgPrice) : "—",
    };
  }, [products, browseSearch, browseStore, stores.length]);

  async function finishOnboarding() {
    setShowOnboarding(false);
    try {
      await completeOnboarding();
      await refresh();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not save onboarding status");
    }
  }

  async function handleDeleteProduct(productId: string) {
    setDeletingId(productId);
    setError(null);
    const previous = products;
    setProducts((rows) => rows.filter((p) => p.id !== productId));
    try {
      await deleteProduct(productId);
      await refresh();
      await refreshProducts({ silent: true });
    } catch (err) {
      setProducts(previous);
      setError(err instanceof Error ? err.message : "Delete failed");
    } finally {
      setDeletingId(null);
    }
  }

  if (authLoading) {
    return (
      <div className="app auth-page">
        <p className="status auth-loading">Loading…</p>
      </div>
    );
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
        browseStore={browseStore}
        setBrowseStore={setBrowseStore}
        compareQuery={compareQuery}
        setCompareQuery={setCompareQuery}
        products={products}
        productsLoading={productsLoading}
        stores={stores}
        browseStats={browseStats}
        error={error}
        setError={setError}
        deletingId={deletingId}
        handleDeleteProduct={handleDeleteProduct}
        showOnboarding={showOnboarding}
        setShowOnboarding={setShowOnboarding}
        finishOnboarding={finishOnboarding}
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
  browseStore,
  setBrowseStore,
  compareQuery,
  setCompareQuery,
  products,
  productsLoading,
  stores,
  browseStats,
  error,
  setError,
  deletingId,
  handleDeleteProduct,
  showOnboarding,
  setShowOnboarding,
  finishOnboarding,
}: {
  page: Page;
  navigate: (next: Page) => void;
  user: { username: string; needs_onboarding: boolean };
  logout: () => Promise<void>;
  browseSearch: string;
  setBrowseSearch: (v: string) => void;
  browseStore: string;
  setBrowseStore: (v: string) => void;
  compareQuery: string;
  setCompareQuery: (v: string) => void;
  products: Product[];
  productsLoading: boolean;
  stores: string[];
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
  showOnboarding: boolean;
  setShowOnboarding: (v: boolean) => void;
  finishOnboarding: () => Promise<void>;
}) {
  const { enqueueFiles, activeCount, pendingLabel, requestLabel, dismissLabel, completeLabel } =
    useUploadQueue();

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
      <TopBar
        page={page}
        {...searchProps}
        user={user}
        onLogout={() => void logout()}
        onNavigate={navigate}
        onPhotoSelected={(file) => enqueueFiles([file], "shelf")}
        uploadActive={activeCount > 0}
        stores={stores}
        store={browseStore}
        onStoreChange={setBrowseStore}
        browseStats={products.length > 0 ? browseStats : undefined}
        onShowOnboarding={() => setShowOnboarding(true)}
      />

      <UploadStatusBar onViewBrowse={() => navigate("browse")} />

      {error && (
        <p className="status error app-error">
          {error}
          <button type="button" className="app-error-dismiss" onClick={() => setError(null)}>
            Dismiss
          </button>
        </p>
      )}
      {productsLoading && products.length === 0 && page !== "upload" && (
        <p className="status">Loading products…</p>
      )}

      {page === "browse" && (products.length > 0 || !productsLoading) && (
        <BrowsePage
          products={products}
          search={browseSearch}
          store={browseStore}
          onStartUpload={() => navigate("upload")}
          onDeleteProduct={(id) => void handleDeleteProduct(id)}
          deletingId={deletingId}
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
      {page === "upload" && <UploadPage />}
      {page === "settings" && <SettingsPage />}
      {page === "compare" && (products.length > 0 || !productsLoading) && (
        <ComparePage
          products={products}
          query={compareQuery}
          onDeleteProduct={(id) => void handleDeleteProduct(id)}
          deletingId={deletingId}
        />
      )}

      {showOnboarding && (
        <OnboardingGuide
          onStartUpload={() => {
            void finishOnboarding();
            navigate("upload");
          }}
          onDismiss={() => void finishOnboarding()}
        />
      )}

      {pendingLabel && (
        <StoreLabelModal
          request={pendingLabel}
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
