import { useRef } from "react";
import { AuthProvider, useAuth } from "./AuthContext";
import { CatalogProvider, useCatalog } from "./CatalogContext";
import { BrowsePage } from "./BrowsePage";
import { BrowseQueryChips } from "./BrowseQueryChips";
import { BrowseSelectionBar } from "./BrowseSelectionBar";
import { BrowseSortFilterPanel } from "./BrowseSortFilterPanel";
import { BulkDeleteConfirmModal } from "./BulkDeleteConfirmModal";
import { OnboardingGuide } from "./OnboardingGuide";
import { SettingsPage } from "./SettingsPage";
import { AuthLoadingScreen } from "./AuthLoadingScreen";
import { SignInPage } from "./SignInPage";
import { StoreLabelModal } from "./StoreLabelModal";
import { TopBar } from "./TopBar";
import { AppHeader } from "./AppHeader";
import { UploadQueueProvider, useUploadQueueActions } from "./UploadQueueContext";
import { UploadStatusPanel, UploadStatusToasts } from "./UploadStatusBar";
import { productImageUrl } from "./api";
import { useHashPage } from "./useHashPage";
import type { AppPage } from "./types";
import "./App.css";

function AuthenticatedApp() {
  const { user, logout } = useAuth();
  const { page, navigate: navigatePage } = useHashPage();
  const catalog = useCatalog();
  const { enqueueFiles, pendingLabel, requestLabel, dismissLabel, completeLabel } =
    useUploadQueueActions();
  const photoInputRef = useRef<HTMLInputElement>(null);

  function navigate(next: AppPage) {
    navigatePage(next);
    if (next !== "browse") {
      catalog.resetBrowseUi();
    } else {
      catalog.setSortFilterOpen(false);
    }
  }

  function openPhotoPicker() {
    photoInputRef.current?.click();
  }

  return (
    <div className="app">
      <AppHeader>
        <TopBar
          page={page}
          search={catalog.browseSearch}
          onSearchChange={catalog.setBrowseSearch}
          searchPlaceholder="Search products, brands, barcodes…"
          user={user!}
          onLogout={() => void logout()}
          onNavigate={navigate}
          photoInputRef={photoInputRef}
          onPhotosSelected={(files) => enqueueFiles(files)}
          showSortFilter={page === "browse"}
          sortFilterOpen={catalog.sortFilterOpen}
          activeChipCount={catalog.activeChipCount}
          onToggleSortFilter={() => catalog.setSortFilterOpen(!catalog.sortFilterOpen)}
          browseStats={catalog.products.length > 0 ? catalog.browseStats : undefined}
          onShowOnboarding={() => catalog.setShowOnboarding(true)}
        />
        <UploadStatusPanel />
      </AppHeader>

      <UploadStatusToasts />

      {page === "browse" && !catalog.selectionMode && (
        <BrowseQueryChips
          query={catalog.browseQuery}
          extents={catalog.priceExtentsForChips}
          onChange={catalog.setBrowseQuery}
        />
      )}

      {page === "browse" && catalog.selectionMode && (
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

      {page === "browse" && (catalog.products.length > 0 || !catalog.productsLoading) && (
        <BrowsePage
          products={catalog.browseDisplayed}
          catalogEmpty={catalog.products.length === 0}
          viewMode={catalog.browseQuery.viewMode}
          onStartUpload={openPhotoPicker}
          onDeleteProduct={(id) => void catalog.handleDeleteProduct(id)}
          deletingId={catalog.deletingId}
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
      {page === "settings" && <SettingsPage />}

      {page === "browse" && (
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
      )}

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
          onDone={() => completeLabel()}
          onDismiss={() => dismissLabel()}
        />
      )}
    </div>
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
    <CatalogProvider user={user} refreshAuth={refresh}>
      <AuthenticatedShell />
    </CatalogProvider>
  );
}

export default function App() {
  return (
    <AuthProvider>
      <AppShell />
    </AuthProvider>
  );
}
