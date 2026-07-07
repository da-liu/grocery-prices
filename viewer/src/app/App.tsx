import { useEffect, useRef } from "react";
import {
  Navigate,
  Outlet,
  Route,
  Routes,
  useLocation,
  useNavigate,
  useOutletContext,
} from "react-router";
import { AuthProvider, useAuth } from "@/features/auth/AuthContext";
import { AuthLoadingScreen } from "@/features/auth/AuthLoadingScreen";
import { SignInPage } from "@/features/auth/SignInPage";
import { BrowsePage } from "@/features/browse/BrowsePage";
import { BrowseQueryChips } from "@/features/browse/BrowseQueryChips";
import { BrowseSelectionBar } from "@/features/browse/BrowseSelectionBar";
import { BrowseSortFilterPanel } from "@/features/browse/BrowseSortFilterPanel";
import { BulkDeleteConfirmModal } from "@/features/browse/BulkDeleteConfirmModal";
import { CatalogProvider, useCatalog } from "@/features/browse/CatalogContext";
import { OnboardingGuide } from "@/features/browse/OnboardingGuide";
import { SettingsPage } from "@/features/stores/SettingsPage";
import { StoreLabelModal } from "@/features/stores/StoreLabelModal";
import { StoresProvider, useStores } from "@/features/stores/StoresContext";
import {
  UploadQueueProvider,
  useUploadQueueActions,
} from "@/features/upload/UploadQueueContext";
import {
  UploadStatusPanel,
  UploadStatusToasts,
} from "@/features/upload/UploadStatusBar";
import { AppHeader } from "@/app/components/AppHeader";
import { TopBar } from "@/app/components/TopBar";
import { productImageUrl } from "@/shared/api/api";
import "@/shared/styles/modal.css";
import "@/shared/styles/panel.css";
import "@/shared/styles/status.css";
import "@/shared/styles/buttons.css";
import "./App.css";

function BrowseRoute() {
  const catalog = useCatalog();
  const { requestLabel } = useUploadQueueActions();
  const { openPhotoPicker } = useOutletContext<{ openPhotoPicker: () => void }>();

  return (
    <>
      {!catalog.selectionMode && (
        <BrowseQueryChips
          query={catalog.browseQuery}
          extents={catalog.priceExtentsForChips}
          onChange={catalog.setBrowseQuery}
        />
      )}

      {catalog.selectionMode && (
        <BrowseSelectionBar
          selectedCount={catalog.selectedIds.size}
          shownCount={catalog.browseDisplayed.length}
          allShownSelected={
            catalog.browseDisplayed.length > 0 &&
            catalog.browseDisplayed.every((product) => catalog.selectedIds.has(product.id))
          }
          deleting={catalog.bulkDeleting}
          onSelectAllShown={() =>
            catalog.setSelectedIds(new Set(catalog.browseDisplayed.map((product) => product.id)))
          }
          onDeleteSelected={() => catalog.requestBulkDelete([...catalog.selectedIds])}
          onCancel={() => {
            catalog.setSelectionMode(false);
            catalog.setSelectedIds(new Set());
          }}
        />
      )}

      {(catalog.products.length > 0 || !catalog.productsLoading) && (
        <BrowsePage
          products={catalog.browseDisplayed}
          catalogEmpty={catalog.products.length === 0}
          viewMode={catalog.browseQuery.viewMode}
          onStartUpload={openPhotoPicker}
          onDeleteProduct={(id) => void catalog.handleDeleteProduct(id)}
          onDeletePhoto={(imageId) => void catalog.handleDeletePhoto(imageId)}
          deletingId={catalog.deletingId}
          deletingPhotoId={catalog.deletingPhotoId}
          onEditProduct={catalog.handleEditProduct}
          onReextractPhoto={catalog.handleReextractPhoto}
          onAddManualProduct={catalog.handleAddManualProduct}
          savingId={catalog.savingId}
          reextractingId={catalog.reextractingId}
          reextractStartedAt={catalog.reextractStartedAt}
          extractBackend={catalog.extractBackend}
          selectionMode={catalog.selectionMode}
          selectedIds={catalog.selectedIds}
          onToggleSelect={catalog.toggleProductSelection}
          gridColumns={catalog.browseQuery.gridColumns}
          onNavigateToProduct={catalog.navigateToProduct}
          onNavigateToPhotoGroup={
            catalog.selectionMode ? undefined : catalog.navigateToPhotoGroup
          }
          photoGroupSizes={catalog.photoGroupSizes}
          highlightProductId={catalog.highlightProductId}
          highlightPhotoGroupId={catalog.highlightPhotoGroupId}
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

      <BrowseSortFilterPanel
        open={catalog.sortFilterOpen}
        query={catalog.browseQuery}
        onChange={catalog.setBrowseQuery}
        onClose={() => catalog.setSortFilterOpen(false)}
        products={catalog.products}
        search={catalog.browseSearch}
        stores={catalog.stores}
        categories={catalog.categories}
        stats={{
          shown: catalog.browseStats.shown,
          total: catalog.browseStats.total,
          avgPriceLabel: catalog.browseStats.avgPriceLabel,
        }}
        selectionMode={catalog.selectionMode}
        onEnterSelection={() => catalog.setSelectionMode(true)}
        onExitSelection={() => {
          catalog.setSelectionMode(false);
          catalog.setSelectedIds(new Set());
        }}
        onDeleteAllProducts={
          catalog.products.length > 0
            ? () =>
                void catalog.handleDeleteProducts(
                  catalog.products.map((product) => product.id),
                )
            : undefined
        }
        deletingAll={catalog.bulkDeleting}
      />
    </>
  );
}

function SettingsRoute() {
  const stores = useStores();
  return stores.showSettings ? <SettingsPage /> : null;
}

function AuthenticatedLayout() {
  const { user, logout } = useAuth();
  const location = useLocation();
  const navigate = useNavigate();
  const catalog = useCatalog();
  const stores = useStores();
  const { enqueueFiles, pendingLabel, dismissLabel, completeLabel } =
    useUploadQueueActions();
  const photoInputRef = useRef<HTMLInputElement>(null);

  const isBrowse = location.pathname === "/";

  const { resetBrowseUi, setSortFilterOpen } = catalog;

  useEffect(() => {
    if (location.pathname === "/settings") {
      resetBrowseUi();
    } else if (location.pathname === "/") {
      setSortFilterOpen(false);
    }
  }, [location.pathname, resetBrowseUi, setSortFilterOpen]);

  useEffect(() => {
    const hash = window.location.hash.replace(/^#\/?/, "");
    if (hash === "settings") navigate("/settings", { replace: true });
    else if (hash) navigate("/", { replace: true });
  }, [navigate]);

  useEffect(() => {
    if (
      location.pathname === "/settings" &&
      !stores.storeLocationsLoading &&
      !stores.showSettings
    ) {
      navigate("/", { replace: true });
    }
  }, [location.pathname, stores.storeLocationsLoading, stores.showSettings, navigate]);

  function openPhotoPicker() {
    photoInputRef.current?.click();
  }

  return (
    <div className="app">
      <AppHeader>
        <TopBar
          search={catalog.browseSearch}
          onSearchChange={catalog.setBrowseSearch}
          searchPlaceholder="Search products, brands, barcodes…"
          user={user!}
          onLogout={() => void logout()}
          photoInputRef={photoInputRef}
          onPhotosSelected={(files) => enqueueFiles(files)}
          showSortFilter={isBrowse}
          sortFilterOpen={catalog.sortFilterOpen}
          activeChipCount={catalog.activeChipCount}
          onToggleSortFilter={() => catalog.setSortFilterOpen(!catalog.sortFilterOpen)}
          browseStats={catalog.products.length > 0 ? catalog.browseStats : undefined}
          onShowOnboarding={() => catalog.setShowOnboarding(true)}
          showSettings={stores.showSettings}
        />
        <UploadStatusPanel />
      </AppHeader>

      <UploadStatusToasts />

      {catalog.error && (
        <p className="status error app-error">
          {catalog.error}
          <button
            type="button"
            className="app-error-dismiss"
            onClick={() => catalog.setError(null)}
          >
            Dismiss
          </button>
        </p>
      )}
      {catalog.productsLoading && <p className="status">Loading products…</p>}

      <Outlet context={{ openPhotoPicker }} />

      {catalog.bulkDeletePending && catalog.bulkDeleteImpact && (
        <BulkDeleteConfirmModal
          productCount={catalog.bulkDeleteImpact.productCount}
          photosRemoved={catalog.bulkDeleteImpact.photosRemoved}
          deleting={catalog.bulkDeleting}
          onCancel={() => catalog.setBulkDeletePending(null)}
          onConfirm={() => void catalog.handleDeleteProducts(catalog.bulkDeletePending!)}
        />
      )}

      {catalog.showOnboarding && (
        <OnboardingGuide
          onStartUpload={() => {
            void catalog.finishOnboarding();
            openPhotoPicker();
          }}
          onDismiss={() => void catalog.finishOnboarding()}
        />
      )}

      {pendingLabel && (
        <StoreLabelModal
          request={pendingLabel}
          onDone={() => {
            void stores.refreshStoreLocations();
            completeLabel();
          }}
          onDismiss={() => dismissLabel()}
        />
      )}
    </div>
  );
}

function AuthenticatedApp() {
  return (
    <Routes>
      <Route element={<AuthenticatedLayout />}>
        <Route index element={<BrowseRoute />} />
        <Route path="settings" element={<SettingsRoute />} />
        <Route path="*" element={<Navigate to="/" replace />} />
      </Route>
    </Routes>
  );
}

function AuthenticatedShell() {
  const { extractBackend, handleUploadSuccess } = useCatalog();

  return (
    <UploadQueueProvider extractBackend={extractBackend} onUploadSuccess={handleUploadSuccess}>
      <AuthenticatedApp />
    </UploadQueueProvider>
  );
}

function AppShell() {
  const { user, loading: authLoading, refresh } = useAuth();

  if (authLoading) {
    return <AuthLoadingScreen />;
  }

  if (!user) {
    return <SignInPage />;
  }

  return (
    <StoresProvider user={user}>
      <CatalogProvider user={user} refreshAuth={refresh}>
        <AuthenticatedShell />
      </CatalogProvider>
    </StoresProvider>
  );
}

export default function App() {
  return (
    <AuthProvider>
      <AppShell />
    </AuthProvider>
  );
}
